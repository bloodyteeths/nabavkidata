"""Weekly hand-picked client shortlists (Phase 4, Oct 2026).

Port of BidFinder's weekly_shortlist_draft: Tuesday's cron builds a DRAFT list
of 2-8 candidate tenders per client / warm prospect; Atilla picks 2-4, adds a
note per pick, previews and presses Send in /admin/shortlists. Nothing here
sends: the cron's only "notification" is the shortlist_curate focus item.

BidFinder lesson (feedback_no_spam_weekly_handpicked): automatic weekly lists
read as spam; a short hand-picked list with one human line per tender converts.
Amounts are never put in the e-mail (estimated_value_mkd is admin-only).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from services.lead_watch import SQL_ALERT_KEYWORDS, keyword_pattern
from services.ops_copy import (SIGNATURE, display_title, fmt_date, greeting, render_html,
                               tender_link, week_start)

log = logging.getLogger(__name__)

MAX_CANDIDATES = 8
MIN_PICK = 2
MAX_PICK = 4
MIN_DAYS_TO_CLOSE = 5
MAX_NOTE = 300

CLOSING_LINE = ("Ако сакате да учествувате на некој од нив, одговорете на оваа порака "
                "и ние ја подготвуваме понудата.")
INTRO_TAIL = ("\n\nГи прегледавме новите тендери и ги издвоивме овие што одговараат "
              "на Вашата дејност:")


class ShortlistStateError(ValueError):
    """The shortlist is not a draft any more (API: 409). Other ValueErrors: 422."""


_TARGET_BASE = """
SELECT u.user_id, lower(u.email) AS email, u.full_name, u.company_name, u.account_type
FROM users u
WHERE COALESCE(u.role,'user') <> 'admin'
  AND lower(u.email) NOT LIKE '%@nabavkidata.com' AND lower(u.email) NOT LIKE '%@facturino.mk'
  AND NOT EXISTS (SELECT 1 FROM suppression_list s WHERE lower(s.email) = lower(u.email))
"""

SQL_TARGETS = _TARGET_BASE + """
  AND (u.account_type = 'managed_client'
       OR (u.account_type = 'prospect' AND (
            EXISTS (SELECT 1 FROM bid_service_leads l
                     WHERE (l.user_id = u.user_id OR lower(l.email) = lower(u.email))
                       AND l.status IN ('new','contacted','qualified')
                       AND l.created_at > NOW() - interval '60 days')
            OR EXISTS (SELECT 1 FROM user_sessions s
                        WHERE s.user_id = u.user_id AND s.last_activity > NOW() - interval '30 days'))))
ORDER BY u.account_type DESC, u.company_name NULLS LAST
"""

# An explicit admin "build for this user" skips the activity test but keeps the
# account-type, internal and suppression filters.
SQL_TARGET_ONE = _TARGET_BASE + """
  AND u.user_id = $1 AND u.account_type IN ('managed_client','prospect')
"""

SQL_CANDIDATES = """
WITH am AS (
  SELECT m.tender_id, MAX(m.match_score)::float AS score, NULL::text AS kw
  FROM alert_matches m JOIN tender_alerts a ON a.alert_id = m.alert_id
  WHERE a.user_id = $1 AND a.is_active
  GROUP BY m.tender_id
), kwm AS (
  SELECT t.tender_id, 50::float AS score,
         (SELECT k FROM unnest($3::text[]) WITH ORDINALITY x(k, o) WHERE t.title ~* k ORDER BY o LIMIT 1) AS kw
  FROM tenders t
  WHERE cardinality($3::text[]) > 0 AND t.title ~* ANY($3::text[])
    AND (t.status IS NULL OR lower(t.status) IN ('open','active'))
    AND t.closing_date >= $2::date + 5
    AND COALESCE(t.publication_date, t.created_at::date) >= $2::date - 14
), c AS (
  SELECT tender_id, MAX(score) AS score, MAX(kw) AS kw
  FROM (SELECT * FROM am UNION ALL SELECT * FROM kwm) u GROUP BY tender_id
)
SELECT t.tender_id, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd, c.score, c.kw
FROM c JOIN tenders t ON t.tender_id = c.tender_id
WHERE (t.status IS NULL OR lower(t.status) IN ('open','active'))
  AND t.closing_date >= $2::date + 5
  AND NOT EXISTS (SELECT 1 FROM bid_jobs j WHERE j.user_id = $1 AND j.tender_id = t.tender_id)
  AND NOT EXISTS (SELECT 1 FROM client_shortlist_items i JOIN client_shortlists s ON s.id = i.shortlist_id
                  WHERE s.user_id = $1 AND s.status = 'sent' AND i.picked AND i.tender_id = t.tender_id)
  AND NOT EXISTS (SELECT 1 FROM lead_watch_shown ws JOIN lead_watches w ON w.id = ws.watch_id
                  WHERE w.email = $4 AND ws.tender_id = t.tender_id)
  -- already a candidate in one of the previous two weeks' lists: Atilla saw it
  AND NOT EXISTS (SELECT 1 FROM client_shortlist_items i JOIN client_shortlists s ON s.id = i.shortlist_id
                  WHERE s.user_id = $1 AND i.tender_id = t.tender_id
                    AND s.week_start < date_trunc('week', $2::date)::date
                    AND s.week_start >= date_trunc('week', $2::date)::date - 14)
ORDER BY c.score DESC, t.closing_date ASC
LIMIT $5
"""

SQL_EXISTING = "SELECT id, status FROM client_shortlists WHERE user_id = $1 AND week_start = $2"

SQL_INSERT_SHORTLIST = """
INSERT INTO client_shortlists (user_id, week_start, subject, intro_text)
VALUES ($1, $2, $3, $4)
ON CONFLICT (user_id, week_start) DO NOTHING
RETURNING id
"""

SQL_INSERT_ITEM = """
INSERT INTO client_shortlist_items (shortlist_id, tender_id, rank, reason)
VALUES ($1, $2, $3, $4)
ON CONFLICT (shortlist_id, tender_id) DO NOTHING
"""

SQL_LIST_WEEK = """
SELECT s.id, s.user_id, s.week_start, s.status, s.subject, s.intro_text, s.built_at, s.sent_at,
       s.sent_message_id, lower(u.email) AS email, u.full_name, u.company_name, u.account_type
FROM client_shortlists s JOIN users u ON u.user_id = s.user_id
WHERE s.week_start = $1
ORDER BY CASE s.status WHEN 'draft' THEN 0 WHEN 'sent' THEN 1 ELSE 2 END, u.company_name NULLS LAST
"""

SQL_GET_ONE = """
SELECT s.id, s.user_id, s.week_start, s.status, s.subject, s.intro_text, s.built_at, s.sent_at,
       s.sent_message_id, lower(u.email) AS email, u.full_name, u.company_name, u.account_type
FROM client_shortlists s JOIN users u ON u.user_id = s.user_id
WHERE s.id = $1
"""

SQL_ITEMS = """
SELECT i.shortlist_id, i.tender_id, i.rank, i.reason, i.picked, i.note,
       t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd, t.status AS t_status
FROM client_shortlist_items i LEFT JOIN tenders t ON t.tender_id = i.tender_id
WHERE i.shortlist_id = ANY($1::uuid[])
ORDER BY i.rank
"""

SQL_UPDATE_HEAD = """
UPDATE client_shortlists
   SET subject = COALESCE($2, subject), intro_text = COALESCE($3, intro_text), updated_at = NOW()
 WHERE id = $1 AND status = 'draft'
"""
SQL_SET_PICKED = ("UPDATE client_shortlist_items SET picked = (tender_id = ANY($2::text[])) "
                  "WHERE shortlist_id = $1")
SQL_SET_NOTE = "UPDATE client_shortlist_items SET note = $3 WHERE shortlist_id = $1 AND tender_id = $2"
SQL_MARK_SENT = """
UPDATE client_shortlists
   SET status = 'sent', sent_at = NOW(), sent_message_id = $2, sent_by = $3, updated_at = NOW()
 WHERE id = $1 AND status = 'draft'
"""
SQL_SKIP = ("UPDATE client_shortlists SET status = 'skipped', updated_at = NOW() "
            "WHERE id = $1 AND status = 'draft'")


def _rowcount(status) -> int:
    try:
        return int(str(status).rsplit(" ", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if v is not None and type(v).__name__ == "UUID":
        return str(v)
    return v


def _is_open(row: dict, today: date) -> bool:
    cd = row.get("closing_date")
    st = row.get("t_status")
    return (cd is not None and cd >= today
            and (st is None or str(st).lower() in ("open", "active")))


# ---------------------------------------------------------------------------
# Targets and candidates
# ---------------------------------------------------------------------------
async def shortlist_targets(conn, today: date) -> list[dict]:
    return [dict(r) for r in await conn.fetch(SQL_TARGETS)]


async def _keywords_for(conn, user_id) -> list[str]:
    out: list[str] = []
    for r in await conn.fetch(SQL_ALERT_KEYWORDS, [user_id]):
        kw = " ".join(str(r["kw"]).split()).lower()
        if kw and kw not in out:
            out.append(kw)
    return out[:20]


async def candidates_for(conn, user_id, email: str, today: date,
                         limit: int = MAX_CANDIDATES) -> list[dict]:
    kws = await _keywords_for(conn, user_id)
    by_pattern: dict = {}
    for k in kws:
        by_pattern.setdefault(keyword_pattern(k), k)
    rows = await conn.fetch(SQL_CANDIDATES, user_id, today, list(by_pattern),
                            (email or "").lower(), int(limit))
    out = []
    for r in rows:
        d = dict(r)
        kw = by_pattern.get(d.get("kw")) if d.get("kw") else None
        d["reason"] = f"Клучен збор: {kw}" if kw else "Совпаѓање со следење"
        out.append(d)
    return out


def default_subject(target: dict) -> str:
    who = (target.get("company_name") or "").strip() or "Вас"
    return f"Тендери избрани за {who}"


def default_intro(target: dict) -> str:
    return greeting(target.get("full_name")) + INTRO_TAIL


async def build_week(conn, today: date, user_id=None) -> dict:
    """Idempotent: one draft per (user, week). No row when nothing fits."""
    ws = week_start(today)
    stats = {"built": 0, "existing": 0, "no_candidates": 0}
    if user_id is not None:
        targets = [dict(r) for r in await conn.fetch(SQL_TARGET_ONE, user_id)]
    else:
        targets = await shortlist_targets(conn, today)
    for t in targets:
        if await conn.fetchrow(SQL_EXISTING, t["user_id"], ws):
            stats["existing"] += 1
            continue
        cands = await candidates_for(conn, t["user_id"], t["email"], today)
        if not cands:
            stats["no_candidates"] += 1
            continue
        row = await conn.fetchrow(SQL_INSERT_SHORTLIST, t["user_id"], ws,
                                  default_subject(t), default_intro(t))
        if row is None:
            stats["existing"] += 1
            continue
        for rank, c in enumerate(cands, 1):
            await conn.execute(SQL_INSERT_ITEM, row["id"], c["tender_id"], rank, c["reason"])
        stats["built"] += 1
    return stats


# ---------------------------------------------------------------------------
# Read / edit
# ---------------------------------------------------------------------------
def _shape(sl: dict, items: list[dict], today: date) -> dict:
    out = {k: _jsonable(sl.get(k)) for k in (
        "id", "user_id", "email", "full_name", "company_name", "account_type", "week_start",
        "status", "subject", "intro_text", "built_at", "sent_at", "sent_message_id")}
    out["items"] = [{
        "tender_id": i["tender_id"],
        "title": i.get("title"),
        "procuring_entity": i.get("procuring_entity"),
        "closing_date": _jsonable(i.get("closing_date")),
        "estimated_value_mkd": _jsonable(i.get("estimated_value_mkd")),  # admin eyes only
        "reason": i.get("reason"),
        "rank": i.get("rank"),
        "picked": bool(i.get("picked")),
        "note": i.get("note"),
        "open": _is_open(i, today),
    } for i in items]
    return out


async def list_week(conn, week_start_d: date, today: date) -> list[dict]:
    heads = [dict(r) for r in await conn.fetch(SQL_LIST_WEEK, week_start_d)]
    if not heads:
        return []
    items_by: dict = {}
    for r in await conn.fetch(SQL_ITEMS, [h["id"] for h in heads]):
        items_by.setdefault(r["shortlist_id"], []).append(dict(r))
    return [_shape(h, items_by.get(h["id"], []), today) for h in heads]


async def get_shortlist(conn, shortlist_id, today: date) -> Optional[dict]:
    head = await conn.fetchrow(SQL_GET_ONE, shortlist_id)
    if not head:
        return None
    items = [dict(r) for r in await conn.fetch(SQL_ITEMS, [shortlist_id])]
    return _shape(dict(head), items, today)


async def update_shortlist(conn, shortlist_id, today: date, subject: Optional[str] = None,
                           intro_text: Optional[str] = None, picked: Optional[list] = None,
                           notes: Optional[dict] = None) -> dict:
    """Raises LookupError (missing), ShortlistStateError (not draft),
    ValueError (>4 picks, closed or foreign tender, note too long)."""
    sl = await get_shortlist(conn, shortlist_id, today)
    if sl is None:
        raise LookupError("shortlist not found")
    if sl["status"] != "draft":
        raise ShortlistStateError("shortlist is not a draft")
    by_tid = {i["tender_id"]: i for i in sl["items"]}
    picked = list(dict.fromkeys(picked or []))
    if len(picked) > MAX_PICK:
        raise ValueError(f"at most {MAX_PICK} tenders can be picked")
    for tid in picked:
        if tid not in by_tid:
            raise ValueError(f"tender {tid} is not in this shortlist")
        if not by_tid[tid]["open"]:
            raise ValueError(f"tender {tid} is closed")
    clean_notes: dict = {}
    for tid, note in (notes or {}).items():
        if tid not in by_tid:
            raise ValueError(f"tender {tid} is not in this shortlist")
        n = (note or "").strip()
        if len(n) > MAX_NOTE:
            raise ValueError(f"note for {tid} is longer than {MAX_NOTE} characters")
        clean_notes[tid] = n or None
    subj = subject.strip() if subject and subject.strip() else None
    intro = intro_text.strip() if intro_text and intro_text.strip() else None
    if _rowcount(await conn.execute(SQL_UPDATE_HEAD, shortlist_id, subj, intro)) == 0:
        raise ShortlistStateError("shortlist is not a draft")
    await conn.execute(SQL_SET_PICKED, shortlist_id, picked)
    for tid, n in clean_notes.items():
        await conn.execute(SQL_SET_NOTE, shortlist_id, tid, n)
    return await get_shortlist(conn, shortlist_id, today)


def render_shortlist_email(sl: dict, items: list[dict]) -> dict:
    """Picked items only. No amounts of any kind."""
    blocks = []
    for i in items:
        if not i.get("picked"):
            continue
        lines = [f"• {display_title(i.get('title'))}",
                 f"  {(i.get('procuring_entity') or '').strip()}, рок {fmt_date(i.get('closing_date'))}"]
        if (i.get("note") or "").strip():
            lines.append(f"  {i['note'].strip()}")
        lines.append(f"  {tender_link(i['tender_id'])}")
        blocks.append("\n".join(lines))
    body = ((sl.get("intro_text") or "").strip() + "\n\n" + "\n\n".join(blocks)
            + "\n\n" + CLOSING_LINE + SIGNATURE)
    return {
        "to": (sl.get("email") or "").strip().lower(),
        "subject": (sl.get("subject") or "").strip(),
        "body_text": body,
        "body_html": render_html(body),
    }


async def mark_sent(conn, shortlist_id, message_id: Optional[str], sent_by=None) -> bool:
    return _rowcount(await conn.execute(SQL_MARK_SENT, shortlist_id, message_id, sent_by)) > 0


async def skip(conn, shortlist_id) -> bool:
    return _rowcount(await conn.execute(SQL_SKIP, shortlist_id)) > 0
