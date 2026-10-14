"""
Client-win detection helpers (Phase 2b of the done-for-you bid service, Oct 2026).

Pure functions only — no database, no FastAPI, no api.* imports — shared by
crons/detect_client_wins.py and api/bid_jobs.py (admin outcome=won).

Success fee (terms 4.4, mirrors BidFinder service_agreement.py clause 2(b)):
    fee = round(first_year_value * pct / 100) - prep fee already paid for that bid
with NO cap (owner decision 14.10.2026; BidFinder caps, we do not).
"""
from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional

WIN_MATCH_THRESHOLD = 0.6

# Latin -> Macedonian Cyrillic. Digraphs first (longest match wins).
_DIGRAPHS = (
    ("dž", "џ"), ("dzh", "џ"), ("gj", "ѓ"), ("kj", "ќ"), ("lj", "љ"), ("nj", "њ"),
    ("zh", "ж"), ("ch", "ч"), ("sh", "ш"), ("dz", "ѕ"),
)
_SINGLE = {
    "a": "а", "b": "б", "c": "ц", "č": "ч", "ć": "ќ", "d": "д", "đ": "ѓ", "e": "е", "f": "ф",
    "g": "г", "h": "х", "i": "и", "j": "ј", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "к", "r": "р", "s": "с", "š": "ш", "t": "т", "u": "у", "v": "в", "w": "в",
    "x": "кс", "y": "и", "z": "з", "ž": "ж", "ǵ": "ѓ", "ḱ": "ќ",
}
_STOP_TOKENS = frozenset({
    "друштво", "за", "дооел", "доо", "ад", "тп", "увоз-извоз", "експорт-импорт", "скопје",
    "dooel", "doo", "ad", "skopje",
})
_QUOTES_RE = re.compile(r"[\"'„“”‘’«»`]")
_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def _translit(s: str) -> str:
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        for lat, cyr in _DIGRAPHS:
            if s.startswith(lat, i):
                out.append(cyr)
                i += len(lat)
                break
        else:
            ch = s[i]
            out.append(_SINGLE.get(ch, ch))
            i += 1
    return "".join(out)


def normalize_company(name: Optional[str]) -> str:
    """Comparable form of a company name: lowercase Cyrillic, no quotes,
    punctuation or legal-form / city tokens, single spaces."""
    s = (name or "").lower()
    s = _translit(s)
    s = _QUOTES_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    tokens: list[str] = []
    for tok in s.split():
        tok = tok.strip("-")
        if not tok or tok in _STOP_TOKENS:
            continue
        for part in tok.split("-"):
            if part and part not in _STOP_TOKENS:
                tokens.append(part)
    return " ".join(tokens)


def _trigrams(s: str) -> set[str]:
    grams: set[str] = set()
    for word in re.split(r"[^\w]+", (s or "").lower()):
        if not word:
            continue
        padded = "  " + word + " "
        for i in range(len(padded) - 2):
            grams.add(padded[i:i + 3])
    return grams


def trigram_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Pure-Python pg_trgm similarity(): |A∩B| / |A∪B| over padded word trigrams."""
    ta, tb = _trigrams(a or ""), _trigrams(b or "")
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


_MONTHS_RE = re.compile(r"(\d+)\s*(?:месеци|месец)\b", re.IGNORECASE)
_YEARS_RE = re.compile(r"(\d+)\s*(?:години|година|год\.?)(?=\W|$)", re.IGNORECASE)
_DAYS_RE = re.compile(r"(\d+)\s*(?:денови|дена|ден)\b", re.IGNORECASE)


def parse_contract_months(text: Optional[str]) -> Optional[int]:
    """„12 месеци“ -> 12, „2 години“ -> 24, „90 дена“ -> 3 (ceiling). None if unknown."""
    if not text:
        return None
    s = str(text)
    m = _MONTHS_RE.search(s)
    if m:
        v = int(m.group(1))
        return v if v > 0 else None
    m = _YEARS_RE.search(s)
    if m:
        v = int(m.group(1)) * 12
        return v if v > 0 else None
    m = _DAYS_RE.search(s)
    if m:
        v = math.ceil(int(m.group(1)) / 30)
        return v if v > 0 else None
    return None


def _dec(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def first_year_value(total: Any, months: Optional[int]) -> Optional[Decimal]:
    """Value of the first 12 months: total * 12 / months for contracts over a year."""
    t = _dec(total)
    if t is None:
        return None
    if months and months > 12:
        return (t * 12 / Decimal(months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return t


def compute_success_fee(first_year: Any, pct: Any, prep_credit: Any = 0) -> int:
    """max(round(first_year * pct / 100) - prep_credit, 0) in whole MKD. No cap."""
    fy = _dec(first_year) or Decimal(0)
    p = _dec(pct) or Decimal(0)
    credit = int(_dec(prep_credit) or 0)
    gross = int((fy * p / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(gross - credit, 0)


def _g(row: Optional[Mapping], key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        v = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if v is None else v


def build_win_row(job: Mapping, user: Optional[Mapping], tender: Optional[Mapping],
                  matched_name: Optional[str], score: Any, bid_amount: Any) -> dict:
    """Columns for an INSERT into client_wins (see INSERT_WIN_SQL)."""
    if bid_amount is not None:
        value, source = _dec(bid_amount), "bid"
    elif _g(tender, "actual_value_mkd") is not None:
        value, source = _dec(_g(tender, "actual_value_mkd")), "actual"
    elif _g(tender, "estimated_value_mkd") is not None:
        value, source = _dec(_g(tender, "estimated_value_mkd")), "estimated"
    else:
        value, source = None, None
    months = parse_contract_months(_g(tender, "contract_duration"))
    fy = first_year_value(value, months)
    pct = _g(job, "success_fee_pct")
    if pct is None:
        pct = _g(user, "success_fee_pct")
    pct_d = _dec(pct)
    # BidFinder clause 2(b): the prep fee paid for this bid is credited.
    prep_credit = int(_g(job, "prep_fee_mkd", 0) or 0) \
        if (_g(job, "paid_at") is not None and not _g(job, "free", False)) else 0
    fee = compute_success_fee(fy, pct_d, prep_credit) if (fy is not None and pct_d is not None) \
        else None
    sc = _dec(score)
    return {
        "user_id": _g(job, "user_id"),
        "job_id": _g(job, "id"),
        "tender_id": _g(job, "tender_id"),
        "tender_title": _g(tender, "title"),
        "procuring_entity": _g(tender, "procuring_entity"),
        "matched_name": (matched_name or "")[:500] or None,
        "match_score": sc.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) if sc is not None
        else None,
        "contract_value_mkd": value,
        "value_source": source,
        "contract_months": months,
        "first_year_value_mkd": fy,
        "success_fee_pct": pct_d,
        "prep_fee_credit_mkd": prep_credit,
        "success_fee_mkd": fee,
    }


WIN_COLUMNS = ("user_id", "job_id", "tender_id", "tender_title", "procuring_entity",
               "matched_name", "match_score", "contract_value_mkd", "value_source",
               "contract_months", "first_year_value_mkd", "success_fee_pct",
               "prep_fee_credit_mkd", "success_fee_mkd")

INSERT_WIN_SQL = (
    "INSERT INTO client_wins (" + ", ".join(WIN_COLUMNS) + ") VALUES ("
    + ", ".join(f"${i + 1}" for i in range(len(WIN_COLUMNS)))
    + ") ON CONFLICT (user_id, tender_id) DO NOTHING RETURNING id"
)


def win_insert_args(row: Mapping) -> tuple:
    return tuple(row.get(c) for c in WIN_COLUMNS)


def split_winner_names(winner: Optional[str]) -> list[str]:
    """tenders.winner may list several companies separated by ; , or newlines."""
    if not winner:
        return []
    return [p.strip() for p in re.split(r"[;,\n]+", winner) if p.strip()]


def best_match(names: list[tuple[str, Any]], company_name: str) -> tuple[Optional[str], float, Any]:
    """(best_name, score, bid_amount) of names [(name, bid_amount)] against the client."""
    target = normalize_company(company_name)
    best: tuple[Optional[str], float, Any] = (None, 0.0, None)
    if not target:
        return best
    for name, amount in names:
        sc = trigram_similarity(normalize_company(name), target)
        if sc > best[1]:
            best = (name, sc, amount)
    return best
