"""Per-person tender watches and the go-back cadence built on them.

NabavkiData port of BidFinder's lead_watch (Phase 4, Oct 2026).

The problem this solves: a day-3/7/14 timer has nothing to say, so it produces
"just circling back", and that reads worse than silence. So the two halves are
separated:

  * The CADENCE decides when we are allowed to write to someone.
  * The WATCH decides whether there is anything worth writing about.

A go-back only becomes a focus item when a live tender matching the person's
keywords has landed that they have not already been SENT. With nothing new the
watch stays due, is re-checked daily, and the focus response only carries a
note. Nothing in this module sends anything: it produces drafts.

Must not import services.ops_focus (ops_focus imports this module).
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, Optional, Union

from services import ops_copy
from services.ops_copy import (SIGNATURE, SITE, display_title, first_name, fmt_date,
                               greeting, off_day, short_title, tender_link)

log = logging.getLogger(__name__)

DEFAULT_CADENCE = (3, 7, 14)
DEFAULT_REPEAT = 21
MAX_KEYWORDS = 10
MAX_ALERT_KEYWORDS = 20
STOP_REASONS = ("replied", "not_interested")
CONTACT_COOLDOWN_DAYS = 3   # no go-back to an address we e-mailed this recently (any kind)
MAX_SCANS = 200             # due watches regex-scanned per build (each is one tenders query)
NO_MATCH_TTL_S = 600        # a watch with nothing new is not re-scanned for 10 minutes
_NO_MATCH: dict = {}        # (watch_id, touch_count, today) -> monotonic expiry

IsOff = Union[Callable[[date], bool], bool, None]


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------
_TENDER_NO = re.compile(r"\d+/\d{4}")
_SPLIT = re.compile(r"[,;/\n]| и | или ")


def split_keywords(text: Optional[str]) -> list[str]:
    """Free text from the /usluga form ("wants_to_win") -> keywords.

    Tender numbers are removed BEFORE splitting on "/", else '17400/2026'
    would survive as '17400' and '2026'. Items of 3 chars or fewer and pure
    numbers are dropped; at most 10, de-duplicated case-insensitively.
    """
    t = _TENDER_NO.sub(" ", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for part in _SPLIT.split(t):
        kw = " ".join(part.split()).strip(" .:-–\"'„“()")
        if len(kw) <= 3 or kw.replace(" ", "").isdigit():
            continue
        k = kw.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
        if len(out) >= MAX_KEYWORDS:
            break
    return out


_PG_SPECIAL = re.compile(r"([.^$|?*+()\[\]{}\\])")


def pg_regex_escape(s: str) -> str:
    """Escape a literal for a PostgreSQL ARE (~*)."""
    return _PG_SPECIAL.sub(r"\\\1", s or "")


_LEFT = "(^|[^[:alnum:]])"
_RIGHT = "($|[^[:alnum:]])"


def keyword_pattern(kw: str) -> str:
    """Left-bounded prefix for >3 chars (Macedonian inflects: 'софтвер' must
    hit 'софтверско'); both ends bounded for short ones ('ИТ', 'ГИС')."""
    k = kw.strip()
    esc = pg_regex_escape(k)
    if len(k) > 3:
        return _LEFT + esc
    return _LEFT + esc + _RIGHT


def keyword_patterns(kws: Iterable[str]) -> list[str]:
    out, seen = [], set()
    for kw in kws or []:
        if not kw or not str(kw).strip():
            continue
        p = keyword_pattern(str(kw))
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _union_keywords(*lists: Iterable[str]) -> list[str]:
    out, seen = [], set()
    for lst in lists:
        for k in lst or []:
            k2 = " ".join(str(k).split()).lower()
            if k2 and k2 not in seen:
                seen.add(k2)
                out.append(k2)
    return out


# ---------------------------------------------------------------------------
# Cadence (ported verbatim from BidFinder; pure functions)
# ---------------------------------------------------------------------------
def next_due(anchor: datetime, cadence: Iterable[int], repeat: int,
             touch_count: int) -> date:
    """The date the next touch becomes allowed.

    Walks the cadence by how many times we have already written, then repeats
    on a fixed interval. Deliberately a pure function so the schedule can be
    reasoned about without a database.
    """
    steps = list(cadence or [])
    base = anchor.date()
    if touch_count < len(steps):
        return base + timedelta(days=int(steps[touch_count]))
    return base + timedelta(days=int(repeat or 21))


def shift_to_working_day(d: date, is_off: Callable[[date], bool],
                         limit: int = 14) -> date:
    """Push a due date off weekends and declared holidays."""
    out, moved = d, 0
    while is_off(out) and moved < limit:
        out += timedelta(days=1)
        moved += 1
    return out


def _off_fn(is_off: IsOff) -> Callable[[date], bool]:
    if callable(is_off):
        return is_off
    manual = ops_copy.load_manual()
    return lambda d: off_day(d, manual)


def _as_utc(dt) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Sync (idempotent upserts keyed on lower(email))
# ---------------------------------------------------------------------------
SQL_LEAD_SOURCES = """
SELECT DISTINCT ON (lower(l.email))
       l.id AS lead_id, lower(l.email) AS email, l.lead_person, l.company_name,
       COALESCE(l.user_id, (SELECT u.user_id FROM users u WHERE lower(u.email) = lower(l.email)
                            ORDER BY u.created_at LIMIT 1)) AS user_id,
       l.wants_to_win, l.updated_at
FROM bid_service_leads l
WHERE l.status IN ('contacted','qualified') AND l.created_at > NOW() - interval '180 days'
  AND lower(l.email) NOT LIKE '%@nabavkidata.com' AND lower(l.email) NOT LIKE '%@facturino.mk'
  AND NOT EXISTS (SELECT 1 FROM suppression_list s WHERE lower(s.email) = lower(l.email))
ORDER BY lower(l.email), l.updated_at DESC
"""

SQL_PROSPECT_SOURCES = """
SELECT u.user_id, lower(u.email) AS email, u.full_name, u.company_name, u.created_at
FROM users u
WHERE u.account_type = 'prospect' AND u.email_verified
  AND u.created_at < NOW() - interval '3 days'
  AND COALESCE(u.role,'user') <> 'admin'
  AND lower(u.email) NOT LIKE '%@nabavkidata.com' AND lower(u.email) NOT LIKE '%@facturino.mk'
  AND NOT EXISTS (SELECT 1 FROM suppression_list s WHERE lower(s.email) = lower(u.email))
  AND NOT EXISTS (SELECT 1 FROM bid_service_leads l
                  WHERE lower(l.email) = lower(u.email) OR l.user_id = u.user_id)
"""

SQL_ALERT_KEYWORDS = """
SELECT a.user_id, kw
FROM tender_alerts a,
     jsonb_array_elements_text(CASE WHEN jsonb_typeof(a.criteria->'keywords') = 'array'
                                    THEN a.criteria->'keywords' ELSE '[]'::jsonb END) kw
WHERE a.is_active AND a.user_id = ANY($1::uuid[]) AND char_length(trim(kw)) >= 3
ORDER BY a.user_id, a.created_at
"""

# The keyword union keeps first-seen order; admin-added keywords are never removed.
SQL_UPSERT_WATCH = """
INSERT INTO lead_watches (email, person_name, company_name, user_id, lead_id, source,
                          keywords, anchor_at, follow_up_due)
VALUES ($1, $2, $3, $4, $5, $6, $7::text[], $8, $9)
ON CONFLICT (email) DO UPDATE SET
  keywords = ARRAY(SELECT k FROM unnest(lead_watches.keywords || EXCLUDED.keywords)
                   WITH ORDINALITY x(k, o) GROUP BY k ORDER BY min(o)),
  person_name = COALESCE(lead_watches.person_name, EXCLUDED.person_name),
  company_name = COALESCE(lead_watches.company_name, EXCLUDED.company_name),
  user_id = COALESCE(lead_watches.user_id, EXCLUDED.user_id),
  lead_id = COALESCE(lead_watches.lead_id, EXCLUDED.lead_id),
  source = CASE WHEN lead_watches.source = 'prospect' AND EXCLUDED.source = 'lead'
                THEN 'lead' ELSE lead_watches.source END,
  updated_at = NOW()
WHERE NOT (lead_watches.keywords @> EXCLUDED.keywords)
   OR (lead_watches.user_id IS NULL AND EXCLUDED.user_id IS NOT NULL)
   OR (lead_watches.lead_id IS NULL AND EXCLUDED.lead_id IS NOT NULL)
   OR (lead_watches.source = 'prospect' AND EXCLUDED.source = 'lead')
RETURNING (xmax = 0) AS inserted
"""

_DEACTIVATE = """
UPDATE lead_watches w
   SET active = false, updated_at = NOW(),
       notes = concat_ws(E'\\n', w.notes, $1::text)
 WHERE w.active AND ({cond})
"""

DEACTIVATE_RULES = (
    ("auto: managed_client",
     "EXISTS (SELECT 1 FROM users u WHERE (u.user_id = w.user_id OR lower(u.email) = w.email)"
     " AND u.account_type = 'managed_client')"),
    ("auto: paid bid job",
     "EXISTS (SELECT 1 FROM bid_jobs j JOIN users u ON u.user_id = j.user_id"
     " WHERE (u.user_id = w.user_id OR lower(u.email) = w.email) AND j.paid_at IS NOT NULL)"),
    ("auto: lead closed (client/rejected)",
     "EXISTS (SELECT 1 FROM bid_service_leads l WHERE lower(l.email) = w.email)"
     " AND NOT EXISTS (SELECT 1 FROM bid_service_leads l WHERE lower(l.email) = w.email"
     " AND l.status NOT IN ('client','rejected'))"),
    ("auto: suppressed or internal",
     "EXISTS (SELECT 1 FROM suppression_list s WHERE lower(s.email) = w.email)"
     " OR w.email LIKE '%@nabavkidata.com' OR w.email LIKE '%@facturino.mk'"
     " OR EXISTS (SELECT 1 FROM users u WHERE (u.user_id = w.user_id OR lower(u.email) = w.email)"
     " AND u.role = 'admin')"),
)
SQL_DEACTIVATE = [(reason, _DEACTIVATE.replace("{cond}", cond)) for reason, cond in DEACTIVATE_RULES]

SQL_MARK_REPLIED = """
UPDATE lead_watches w SET replied_at = m.first_reply, updated_at = NOW()
FROM (SELECT w2.id, MIN(b.created_at) AS first_reply
        FROM lead_watches w2
        JOIN users u ON (u.user_id = w2.user_id OR lower(u.email) = w2.email)
        JOIN bid_messages b ON b.user_id = u.user_id AND b.sender_role = 'client'
                           AND b.created_at > w2.anchor_at
       WHERE w2.replied_at IS NULL
       GROUP BY w2.id) m
WHERE w.id = m.id AND w.replied_at IS NULL
"""


def _rowcount(status) -> int:
    try:
        return int(str(status).rsplit(" ", 1)[-1])
    except (ValueError, IndexError):
        return 0


async def _alert_keywords(conn, user_ids: list) -> dict:
    ids = [u for u in user_ids if u is not None]
    if not ids:
        return {}
    out: dict = {}
    for r in await conn.fetch(SQL_ALERT_KEYWORDS, ids):
        lst = out.setdefault(r["user_id"], [])
        kw = " ".join(str(r["kw"]).split()).lower()
        if kw and kw not in lst and len(lst) < MAX_ALERT_KEYWORDS:
            lst.append(kw)
    return out


async def sync_watches(conn, today: date, is_off: IsOff = None) -> dict:
    """Create/refresh watches from leads and prospects; deactivate and mark replies.

    Idempotent: re-running changes nothing unless the sources changed.
    """
    off = _off_fn(is_off)
    stats = {"created": 0, "updated": 0, "deactivated": 0, "replied": 0}

    leads = [dict(r) for r in await conn.fetch(SQL_LEAD_SOURCES)]
    prospects = [dict(r) for r in await conn.fetch(SQL_PROSPECT_SOURCES)]
    alert_kws = await _alert_keywords(
        conn, [l.get("user_id") for l in leads] + [p.get("user_id") for p in prospects])

    async def upsert(email, person, company, user_id, lead_id, source, kws, anchor):
        anchor = _as_utc(anchor)
        due = shift_to_working_day(next_due(anchor, DEFAULT_CADENCE, DEFAULT_REPEAT, 0), off)
        row = await conn.fetchrow(SQL_UPSERT_WATCH, email, person, company, user_id, lead_id,
                                  source, kws, anchor, due)
        if row is None:
            return
        stats["created" if row["inserted"] else "updated"] += 1

    for l in leads:
        if ops_copy.is_internal_email(l["email"]):
            continue
        kws = _union_keywords(split_keywords(l.get("wants_to_win")),
                              alert_kws.get(l.get("user_id"), []))
        await upsert(l["email"], l.get("lead_person"), l.get("company_name"), l.get("user_id"),
                     l.get("lead_id"), "lead", kws, l.get("updated_at"))
    for p in prospects:
        if ops_copy.is_internal_email(p["email"]):
            continue
        kws = _union_keywords(alert_kws.get(p.get("user_id"), []))
        await upsert(p["email"], p.get("full_name"), p.get("company_name"), p.get("user_id"),
                     None, "prospect", kws, p.get("created_at"))

    for reason, sql in SQL_DEACTIVATE:
        stats["deactivated"] += _rowcount(await conn.execute(sql, reason))
    stats["replied"] = _rowcount(await conn.execute(SQL_MARK_REPLIED))
    return stats


# ---------------------------------------------------------------------------
# Due watches and their new matches
# ---------------------------------------------------------------------------
SQL_DUE = """
SELECT * FROM lead_watches w
 WHERE w.active AND w.replied_at IS NULL AND w.follow_up_due <= $1
   AND (w.paused_until IS NULL OR w.paused_until < $1)
   AND NOT EXISTS (SELECT 1 FROM ops_sent_emails e WHERE e.to_email = w.email
                   AND e.sent_at > NOW() - make_interval(days => $2::int))
 ORDER BY w.follow_up_due, w.touch_count
"""

SQL_WATCH_ONE = "SELECT * FROM lead_watches WHERE id = $1"
SQL_WATCH_BY_EMAIL = "SELECT * FROM lead_watches WHERE email = $1"

# Wrapped in a sub-select: ORDER BY cannot use the output alias "hits" inside
# an expression (cardinality(hits)) at the same query level.
SQL_NEW_MATCHES = """
SELECT * FROM (
  SELECT t.tender_id, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd, t.cpv_code,
         (SELECT array_agg(k) FROM unnest($2::text[]) k WHERE t.title ~* k) AS hits
  FROM tenders t
  WHERE (t.status IS NULL OR lower(t.status) IN ('open','active'))
    AND t.closing_date >= $1::date + $3::int
    AND COALESCE(t.publication_date, t.created_at::date) >= ($4::timestamptz AT TIME ZONE 'Europe/Skopje')::date - 7
    AND t.title ~* ANY($2::text[])
    AND NOT EXISTS (SELECT 1 FROM lead_watch_shown s WHERE s.watch_id = $5 AND s.tender_id = t.tender_id)
    AND NOT EXISTS (SELECT 1 FROM bid_jobs j WHERE j.user_id = $6 AND j.tender_id = t.tender_id)
    AND ($7::numeric IS NULL OR t.estimated_value_mkd IS NULL OR t.estimated_value_mkd >= $7)
    AND ($8::numeric IS NULL OR t.estimated_value_mkd IS NULL OR t.estimated_value_mkd <= $8)
) m
ORDER BY cardinality(m.hits) DESC NULLS LAST, m.closing_date ASC LIMIT $9
"""


async def due_watches(conn, today: date) -> list[dict]:
    """Everyone whose go-back is due, still silent, not paused, and not e-mailed by
    us in the last CONTACT_COOLDOWN_DAYS (limit applied by caller)."""
    return [dict(r) for r in await conn.fetch(SQL_DUE, today, CONTACT_COOLDOWN_DAYS)]


async def get_watch(conn, watch_id) -> Optional[dict]:
    r = await conn.fetchrow(SQL_WATCH_ONE, watch_id)
    return dict(r) if r else None


async def watch_for_email(conn, email: Optional[str]) -> Optional[dict]:
    e = (email or "").strip().lower()
    if not e:
        return None
    r = await conn.fetchrow(SQL_WATCH_BY_EMAIL, e)
    return dict(r) if r else None


def clear_match_cache() -> None:
    _NO_MATCH.clear()


async def new_matches(conn, watch: dict, today: date, limit: int = 3) -> list[dict]:
    kws = [k for k in (watch.get("keywords") or []) if k and str(k).strip()]
    if not kws:
        return []
    by_pattern = {}
    for k in kws:
        by_pattern.setdefault(keyword_pattern(str(k)), str(k).strip())
    patterns = list(by_pattern)
    since = watch.get("last_touched_at") or watch.get("anchor_at")
    rows = await conn.fetch(
        SQL_NEW_MATCHES, today, patterns, int(watch.get("min_days_to_close") or 5),
        _as_utc(since), watch["id"], watch.get("user_id"),
        watch.get("min_value_mkd"), watch.get("max_value_mkd"), int(limit))
    out = []
    for r in rows:
        d = dict(r)
        d["hit_keywords"] = [by_pattern.get(p, p) for p in (d.get("hits") or [])]
        out.append(d)
    return out


async def record_shown(conn, watch_id, tender_ids) -> None:
    """Remember what was SENT to someone; only sent tenders suppress a re-show."""
    tids = [t for t in (tender_ids or []) if t]
    if not watch_id or not tids:
        return
    await conn.executemany(
        "INSERT INTO lead_watch_shown (watch_id, tender_id, channel) VALUES ($1, $2, 'sent') "
        "ON CONFLICT (watch_id, tender_id) DO NOTHING",
        [(watch_id, t) for t in tids])


SQL_TOUCH = """UPDATE lead_watches
      SET anchor_at = $2, last_touched_at = $2,
          touch_count = touch_count + 1, updated_at = NOW()
    WHERE id = $1
RETURNING cadence_days, cadence_repeat_days, touch_count"""


async def mark_touched(conn, watch_id, is_off: IsOff, when: Optional[datetime] = None) -> date:
    """Record that we wrote to this person and schedule the next allowed touch.

    Call when an email actually goes out (send / confirmed link / admin "Готово"),
    never when a draft is generated: a skipped draft must not advance the cadence.
    """
    now = _as_utc(when)
    row = await conn.fetchrow(SQL_TOUCH, watch_id, now)
    if not row:
        raise LookupError(f"no lead_watch {watch_id}")
    due = shift_to_working_day(
        next_due(now, row["cadence_days"], row["cadence_repeat_days"], row["touch_count"]),
        _off_fn(is_off))
    await conn.execute("UPDATE lead_watches SET follow_up_due = $2 WHERE id = $1", watch_id, due)
    return due


SQL_STOP_REPLIED = ("UPDATE lead_watches SET replied_at = COALESCE(replied_at, NOW()), "
                    "updated_at = NOW() WHERE id = $1")
SQL_STOP_NOT_INTERESTED = ("UPDATE lead_watches SET active = false, updated_at = NOW(), "
                           "notes = concat_ws(E'\\n', notes, 'stop: not_interested') WHERE id = $1")


async def stop_watch(conn, watch_id, reason: str) -> bool:
    if reason not in STOP_REASONS:
        raise ValueError(f"reason must be one of {STOP_REASONS}")
    sql = SQL_STOP_REPLIED if reason == "replied" else SQL_STOP_NOT_INTERESTED
    return _rowcount(await conn.execute(sql, watch_id)) > 0


# ---------------------------------------------------------------------------
# Draft + focus items
# ---------------------------------------------------------------------------
def follow_up_draft(watch: dict, matches: list[dict]) -> Optional[dict]:
    """The go-back e-mail, or None when there is nothing new to say."""
    if not matches:
        return None
    top = matches[0]
    lines = [greeting(watch.get("person_name")), ""]
    lines.append(f"{(top.get('procuring_entity') or 'Договорен орган').strip()} објави тендер "
                 f"„{display_title(top.get('title'))}“, со рок за поднесување "
                 f"{fmt_date(top.get('closing_date'))}.")
    if len(matches) > 1:
        lines += ["", "Има уште:"]
        for m in matches[1:]:
            lines.append(f"• „{display_title(m.get('title'))}“, "
                         f"{(m.get('procuring_entity') or '').strip()}, рок {fmt_date(m.get('closing_date'))}")
    hit = next((h for m in matches for h in (m.get("hit_keywords") or []) if h), None)
    if hit:
        lines.append("")
        if (watch.get("source") or "") == "lead":
            lines.append(f"Ова одговара на она што ни напишавте дека Ве интересира ({hit}).")
        else:
            lines.append(f"Ова одговара на клучните зборови што ги следите кај нас ({hit}).")
    # No usable person name: name the company so the go-back is not anonymous.
    company = (watch.get("company_name") or "").strip()
    for_whom = f"за {company}" if company and not first_name(watch.get("person_name")) else "за Вас"
    lines += [
        "",
        f"Ако сакате да учествувате, ние ја подготвуваме целата понуда {for_whom}: ја читаме "
        "тендерската документација, ги подготвуваме документите и Ви ја предаваме готова за потпис.",
        "",
        "Дали да ја погледнеме документацијата и да Ви кажеме што бара?",
        "",
    ]
    lines += [tender_link(m["tender_id"]) for m in matches if m.get("tender_id")]
    return {
        "to": (watch.get("email") or "").strip().lower(),
        "subject": f"Нов тендер: {short_title(top.get('title'))}",
        "body_text": "\n".join(lines) + SIGNATURE,
    }


def _tender_of(m: dict) -> dict:
    cd = m.get("closing_date")
    v = m.get("estimated_value_mkd")
    return {
        "tender_id": m.get("tender_id"),
        "title": m.get("title"),
        "procuring_entity": m.get("procuring_entity"),
        "closing_date": cd.isoformat() if hasattr(cd, "isoformat") else cd,
        "estimated_value_mkd": float(v) if v is not None else None,
    }


def follow_up_item(watch: dict, matches: list[dict], today: date) -> Optional[dict]:
    draft = follow_up_draft(watch, matches)
    if draft is None:
        return None
    who = watch.get("company_name") or watch.get("person_name") or watch.get("email")
    tc = int(watch.get("touch_count") or 0)
    anchor = watch.get("last_touched_at") or watch.get("anchor_at")
    silent = (today - _as_utc(anchor).date()).days if anchor else None
    n = len(matches)
    links = [{"label": "Отвори тендер", "href": tender_link(m["tender_id"])}
             for m in matches if m.get("tender_id")]
    links.append({"label": "Лидови", "href": f"{SITE}/admin/leads"})
    return {
        "key": goback_key(watch),
        "kind": "goback",
        "group": "sales",
        "priority": 60,
        "date": today.isoformat(),
        "title": f"Го-бек: {who} — {n} {'нов тендер' if n == 1 else 'нови тендери'}",
        "detail": (f"Допир {tc + 1}"
                   + (f", {silent} дена тишина" if silent is not None else "")
                   + f". Најблизок: {matches[0].get('procuring_entity') or ''}, рок "
                   f"{fmt_date(matches[0].get('closing_date'))}. Почнете со тендерот, без извинување."),
        "email": draft["to"] or None,
        "tender": _tender_of(matches[0]),
        "links": links,
        "draft": draft,
        "meta": {"watch_id": str(watch["id"]),
                 "tender_ids": [m["tender_id"] for m in matches if m.get("tender_id")],
                 "touch_count": tc,
                 "source": watch.get("source")},
    }


def goback_key(watch: dict) -> str:
    return f"goback:{watch['id']}:{int(watch.get('touch_count') or 0)}"


async def build_follow_ups(conn, today: date, is_off: IsOff, limit: int = 4, *,
                           skip_keys: Optional[set] = None,
                           stats: Optional[dict] = None) -> tuple[list[dict], int]:
    """(goback items, number of due watches with nothing new). Never writes.

    skip_keys: goback keys the admin marked done / snoozed. They are skipped
    BEFORE counting toward `limit`, so snoozed go-backs cannot hide other due
    ones. stats (optional dict) receives {"no_keywords": n}: due watches that
    can never produce a go-back until someone gives them keywords.
    At most MAX_SCANS watches are regex-scanned per call, and a watch that had
    nothing new is not re-scanned for NO_MATCH_TTL_S (process-local cache).
    """
    off_today = is_off(today) if callable(is_off) else bool(is_off)
    if off_today:
        return [], 0
    skip = skip_keys or set()
    items: list[dict] = []
    nothing_new = no_keywords = scans = 0
    now = time.monotonic()
    for w in await due_watches(conn, today):
        if len(items) >= limit:
            break
        if not w.get("keywords"):
            no_keywords += 1
            continue          # nothing to watch for; admin can add keywords
        if goback_key(w) in skip:
            continue
        ck = (str(w["id"]), int(w.get("touch_count") or 0), today)
        if _NO_MATCH.get(ck, 0) > now:
            nothing_new += 1
            continue
        if scans >= MAX_SCANS:
            continue
        scans += 1
        matches = await new_matches(conn, w, today)
        item = follow_up_item(w, matches, today)
        if item is None:
            nothing_new += 1
            if NO_MATCH_TTL_S > 0:
                _NO_MATCH[ck] = now + NO_MATCH_TTL_S
            continue
        items.append(item)
    if stats is not None:
        stats["no_keywords"] = no_keywords
    return items, nothing_new


async def follow_up_for_watch(conn, watch_id, today: date) -> Optional[dict]:
    """The one go-back item for a watch (used to resolve a single focus key)."""
    w = await get_watch(conn, watch_id)
    if not w or not w.get("active") or w.get("replied_at") is not None or not w.get("keywords"):
        return None
    return follow_up_item(w, await new_matches(conn, w, today), today)
