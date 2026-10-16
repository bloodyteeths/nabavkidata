"""
Shared copy + link helpers for the operator focus system (Phase 4, Oct 2026).

Port of BidFinder's draft rules to NabavkiData. Everything a lead or client
would receive is drafted here or checked here:

  * Macedonian Cyrillic, formal Вие
  * no prices or amounts of any kind (not even the tender's estimated value)
  * no "free" wording, no promise to call, no emojis
  * ends with SIGNATURE; names come from our data, never invented

check_draft_copy() is the gate: every template in ops_focus / hot_signal /
lead_watch / client_shortlist must return [] from it (tests assert this), and
the admin "Испрати" endpoint refuses (422) when a hand-edited draft fails it.

Pure module: no DB, no FastAPI.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

SKOPJE = ZoneInfo("Europe/Skopje")
SITE = "https://nabavkidata.com"
PUBLIC_API = os.getenv("PUBLIC_API_URL", "https://api.nabavkidata.com")
ADMIN_EMAIL = "atillatkulu@gmail.com"
INTERNAL_DOMAINS = ("nabavkidata.com", "facturino.mk")
OPS_LINK_TTL_S = 3 * 86400

SIGNATURE = ("\n\nСо почит,\nАтилла Танрикулу\nНабавкиДата · Фактурино ДООЕЛ\n"
             "hello@nabavkidata.com · +389 70 253 467")


# ---------------------------------------------------------------------------
# Dates, keys, links
# ---------------------------------------------------------------------------
def today_skopje() -> date:
    return datetime.now(SKOPJE).date()


def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-w{w:02d}"


def week_start(d: date) -> date:
    """Monday of d's ISO week."""
    return d - timedelta(days=d.weekday())


def key_part(s) -> str:
    """Tender ids and other free text inside a focus key: '17400/2026' -> '17400-2026'."""
    s = str(s or "").strip().lower().replace("/", "-")
    return re.sub(r"[^a-z0-9:_\-]", "-", s)


def fmt_date(d) -> str:
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return d
    return d.strftime("%d.%m.%Y")


def display_title(t: Optional[str]) -> str:
    """Whitespace-normalised title; ALL-CAPS ESJN titles become sentence case so
    client subjects and bodies do not read as shouting."""
    t = " ".join((t or "").split())
    letters = [c for c in t if c.isalpha()]
    if len(letters) > 10 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
        t = t[0] + t[1:].lower()
    return t


# Function words a cut title must not end on („… ЗА ЕЛЕКТРОНСКО ПОДНЕСУВАЊЕ НА“).
_DANGLING = frozenset({"на", "за", "и", "во", "од", "со", "до", "по", "или", "како", "кон",
                       "при", "низ", "без", "a", "the", "of", "and", "for"})


def short_title(t: Optional[str], limit: int = 70) -> str:
    """At most `limit` chars (+ '…' when cut), cut at a word boundary, no dangling
    function word at the end, ALL-CAPS converted to sentence case."""
    t = display_title(t)
    if len(t) <= limit:
        return t
    cut = t[:limit - 1]           # room for the ellipsis
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    words = cut.rstrip(" ,;:-–").split(" ")
    while len(words) > 1 and words[-1].lower().strip(" ,;:-–") in _DANGLING:
        words.pop()
    return " ".join(words).rstrip(" ,;:-–") + "…"


def tender_link(tid: str) -> str:
    return f"{SITE}/tenders/{str(tid).replace('/', '-')}"


def is_internal_email(email: Optional[str]) -> bool:
    e = (email or "").strip().lower()
    return any(e.endswith("@" + d) for d in INTERNAL_DOMAINS)


# ---------------------------------------------------------------------------
# Manual file + off-days (shared by hot_signal, lead_watch and ops_focus;
# ops_focus re-exports them)
# ---------------------------------------------------------------------------
FOCUS_MANUAL_PATH = os.getenv(
    "FOCUS_MANUAL_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "focus_manual.json"))


def load_manual(path: Optional[str] = None) -> list:
    """JSON list of {"date","title","detail"} or {"holiday_until"}; missing/invalid -> []."""
    try:
        with open(path or FOCUS_MANUAL_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def holiday_until(manual) -> Optional[date]:
    """A {"holiday_until": "YYYY-MM-DD"} entry in the manual file marks
    Atilla off until that date inclusive (latest one wins)."""
    out = None
    for m in manual or []:
        if isinstance(m, dict) and "holiday_until" in m:
            try:
                d = date.fromisoformat(str(m["holiday_until"])[:10])
            except (TypeError, ValueError):
                continue
            out = d if out is None or d > out else out
    return out


def off_day(day: date, manual) -> bool:
    """Saturday/Sunday, or any day up to and including holiday_until."""
    if day.weekday() >= 5:
        return True
    h = holiday_until(manual)
    return h is not None and day <= h


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------
_NOT_A_PERSON = re.compile(
    r"(?i)\b(доо|дооел|ад|тп|јп|јзу|оу|ltd|llc|doo|dooel|компанија|фирма)\b")


def plausible_person(name: Optional[str]) -> bool:
    """1-4 alphabetic words, no company marker, not SHOUTED (company names)."""
    raw = " ".join((name or "").split())
    if not raw:
        return False
    words = raw.split(" ")
    if not 1 <= len(words) <= 4:
        return False
    for w in words:
        core = w.replace("-", "")
        if not core or not core.isalpha():
            return False
        if w.isupper() and len(w) > 3:
            return False
    if _NOT_A_PERSON.search(raw):
        return False
    if raw.isupper() and len(raw) > 3:
        return False
    return True


_LAT_MULTI = (("dzh", "џ"), ("dž", "џ"), ("gj", "ѓ"), ("kj", "ќ"), ("lj", "љ"), ("nj", "њ"),
              ("dz", "ѕ"), ("zh", "ж"), ("ch", "ч"), ("sh", "ш"))
_LAT_SINGLE = dict(zip("abvgdezijklmnoprstufhcčšžćđ", "абвгдезијклмнопрстуфхцчшжќѓ"))


def _is_cyrillic_word(w: str) -> bool:
    return bool(w) and all("Ѐ" <= c <= "ӿ" for c in w if c.isalpha())


def to_cyrillic_name(word: str) -> str:
    """Latin-typed first name -> Macedonian Cyrillic ('marija' -> 'Марија').
    Returns '' when the result would still contain non-Cyrillic letters
    (q/w/x/y, foreign spellings): better a plain „Добар ден,“ than a mangled name."""
    if _is_cyrillic_word(word):
        return word
    s = word.lower()
    for lat, cyr in _LAT_MULTI:
        s = s.replace(lat, cyr)
    s = "".join(_LAT_SINGLE.get(c, c) for c in s)
    return s if _is_cyrillic_word(s) else ""


def first_name(name: Optional[str]) -> str:
    """Cyrillic first name for the greeting, or '' (company names, unusable Latin)."""
    if not plausible_person(name):
        return ""
    first = to_cyrillic_name(" ".join((name or "").split()).split(" ")[0])
    if not first:
        return ""
    return first[0].upper() + first[1:]


def greeting(name: Optional[str]) -> str:
    fn = first_name(name)
    return f"Добар ден, {fn}," if fn else "Добар ден,"


# ---------------------------------------------------------------------------
# Copy checker
# ---------------------------------------------------------------------------
# Unit must stand alone: "денес"/"дена" are not "ден" (deviation from the bare
# contract regex, which flagged "22.10.2026.\nДенес" and "5 дена").
_RE_PRICE = re.compile(
    r"\d[\d.,\s]*\s*(?:(?:денари|ден|мкд|mkd|eur|евра)(?![^\W\d_])|€|%)", re.I)
_RE_FREE = re.compile(r"бесплатн|гратис|без надоместок|free", re.I)
_RE_CALL = re.compile(
    r"ќе (ве|Ве|ви|Ви) (повикам|се јавам)|ќе (ве|Ве) контактирам телефонски", re.I)
_RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_RE_INFORMAL = re.compile(r"\b(ти|те|твој|твоја|твоето)\b", re.I)
_RE_URLISH = re.compile(r"https?://\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _cyrillic_share(text: str) -> float:
    # URLs and e-mail addresses are Latin by nature; they do not make a body Latin.
    letters = [c for c in _RE_URLISH.sub(" ", text) if c.isalpha()]
    if not letters:
        return 1.0
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    return cyr / len(letters)


def check_draft_copy(text: Optional[str]) -> list[str]:
    t = text or ""
    out: list[str] = []
    if _RE_PRICE.search(t):
        out.append("price")
    if _RE_FREE.search(t):
        out.append("free")
    if _RE_CALL.search(t):
        out.append("call_promise")
    if _RE_EMOJI.search(t):
        out.append("emoji")
    if _RE_INFORMAL.search(t):
        out.append("informal")
    if _cyrillic_share(t) < 0.5:
        out.append("latin_body")
    return out


def render_html(body_text: str) -> str:
    """Plain wrapper: escaped text, newlines -> <br>. No tracking pixels or links rewriting."""
    inner = html.escape(body_text or "").replace("\r\n", "\n").replace("\n", "<br>\n")
    return ("<!doctype html><html><body style=\"font-family:Arial,Helvetica,sans-serif;"
            "font-size:14px;line-height:1.5;color:#111\">"
            f"<div style=\"max-width:640px\">{inner}</div></body></html>")


# ---------------------------------------------------------------------------
# Signed one-click "Готово/испратено" links (from the 06:30 focus email)
# ---------------------------------------------------------------------------
def _secret() -> str:
    return os.getenv("SECRET_KEY") or ""


def sign_key(key: str, exp: int) -> str:
    return hmac.new(_secret().encode(), f"ops-done:{key}:{int(exp)}".encode(),
                    hashlib.sha256).hexdigest()[:40]


def ops_done_link(key: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    exp = int(now.timestamp()) + OPS_LINK_TTL_S
    sig = sign_key(key, exp)
    return f"{PUBLIC_API}/api/ops/sent?k={quote(key)}&e={exp}&sig={sig}"


def verify_ops_sig(key: str, exp, sig: str, now: Optional[datetime] = None) -> bool:
    if not _secret() or not key or not sig:
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if not hmac.compare_digest(sign_key(key, exp_i), str(sig)):
        return False
    now = now or datetime.now(timezone.utc)
    return int(now.timestamp()) <= exp_i


def lower_emails(emails: Iterable[Optional[str]]) -> list[str]:
    return [e.strip().lower() for e in emails if e]
