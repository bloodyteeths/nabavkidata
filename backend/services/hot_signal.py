"""
Hot signal (NabavkiData port of BidFinder's "Fred signal", Phase 4 Oct 2026).

A known user opened (or asked the concierge about) a LIVE tender whose deadline
is 3-45 days out, and nobody has written to them since. BidFinder's first paying
client converted exactly like that: behaviour, not profile, was the signal, and
a reply naming that tender the next day closed it.

Sources (both already recorded, no new tracking):
  * user_behavior(action='view')  — TenderDetailClient.tsx POSTs
    /api/personalization/behavior for logged-in users (created_at naive UTC)
  * concierge_log                 — questions asked about a tender

Suppression is derived from live state, no bookkeeping: a signal disappears once
the tender leaves the 3-45 day window or closes, once a bid_job exists for that
(user, tender), or once any ops_sent_emails row went to that address after the
first event. Focus-item done/snooze state is applied by ops_focus.

Deliberately NOT ported: BidFinder's instant admin alert on view. The one
automatic email in this system is the 06:30 focus digest to Atilla.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from services.ops_copy import (SIGNATURE, display_title, fmt_date, greeting, off_day,
                               short_title, tender_link)

log = logging.getLogger(__name__)

MIN_DAYS_OUT = 3     # closer than this and we cannot do the work properly
MAX_DAYS_OUT = 45    # further out and the view is research, not intent
BASE_LOOKBACK_H = 48
MAX_EXTRA_LOOKBACK_H = 240
LIMIT = 40           # fetched; ops_focus applies CAPS["hot_signal"] AFTER done/snooze filtering

SQL_HAS_USER_BEHAVIOR = "SELECT to_regclass('public.user_behavior') IS NOT NULL"

_EV_VIEWS = """
    SELECT ub.user_id, ub.tender_id, (ub.created_at AT TIME ZONE 'UTC') AS at, 'view' AS src
    FROM user_behavior ub WHERE ub.action = 'view' AND ub.created_at > ($1::timestamptz AT TIME ZONE 'UTC')
    UNION ALL"""

_SQL_TEMPLATE = """
WITH ev AS ({views}
  SELECT cl.user_id, cl.tender_id, cl.created_at AS at, 'ask' AS src FROM concierge_log cl
  WHERE cl.user_id IS NOT NULL AND cl.tender_id IS NOT NULL AND cl.created_at > $1
), agg AS (
  SELECT user_id, tender_id, MIN(at) first_at, MAX(at) last_at,
         COUNT(*) FILTER (WHERE src='view') n_views, COUNT(*) FILTER (WHERE src='ask') n_asks
  FROM ev GROUP BY 1,2)
SELECT u.user_id, u.email, u.full_name, u.company_name, u.account_type,
       t.tender_id, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd, t.procedure_type,
       agg.first_at, agg.last_at, agg.n_views, agg.n_asks
FROM agg JOIN users u ON u.user_id = agg.user_id
 AND COALESCE(u.role,'user') <> 'admin' AND u.account_type IN ('free','prospect','managed_client')
 AND u.email NOT ILIKE '%@nabavkidata.com' AND u.email NOT ILIKE '%@facturino.mk'
JOIN tenders t ON t.tender_id = agg.tender_id
 AND (t.status IS NULL OR lower(t.status) IN ('open','active'))
 AND t.closing_date BETWEEN $2::date + 3 AND $2::date + 45
WHERE NOT EXISTS (SELECT 1 FROM bid_jobs j WHERE j.user_id = u.user_id AND j.tender_id = t.tender_id)
  AND NOT EXISTS (SELECT 1 FROM suppression_list s WHERE lower(s.email) = lower(u.email))
  AND NOT EXISTS (SELECT 1 FROM ops_sent_emails e WHERE e.to_email = lower(u.email) AND e.sent_at > agg.first_at)
ORDER BY agg.last_at DESC LIMIT 40
"""

# The ev CTE starts with "WITH ev AS (" and each branch is a full SELECT.
SQL_SIGNALS = _SQL_TEMPLATE.replace("{views}", _EV_VIEWS)
SQL_SIGNALS_NO_VIEWS = _SQL_TEMPLATE.replace("{views}", "")


def lookback_hours(today: date, manual) -> int:
    """48h, plus 24h for every consecutive off-day right before today.

    Monday after a normal weekend looks back 96h, so Saturday/Sunday views are
    not lost (off-day digests may be empty and never sent). Capped at 48+240.
    """
    extra = 0
    d = today - timedelta(days=1)
    while off_day(d, manual) and extra < MAX_EXTRA_LOOKBACK_H:
        extra += 24
        d -= timedelta(days=1)
    return BASE_LOOKBACK_H + min(extra, MAX_EXTRA_LOOKBACK_H)


async def find_hot_signals(conn, today: date, since_hours: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=int(since_hours))
    try:
        has_views = bool(await conn.fetchval(SQL_HAS_USER_BEHAVIOR))
    except Exception as e:  # pragma: no cover - defensive
        log.warning("hot_signal: user_behavior check failed: %s", e)
        has_views = False
    sql = SQL_SIGNALS if has_views else SQL_SIGNALS_NO_VIEWS
    rows = await conn.fetch(sql, since, today)
    return [dict(r) for r in rows]


def _ago(at, now: datetime | None = None) -> str:
    if at is None:
        return ""
    now = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    h = max(int((now - at).total_seconds() // 3600), 0)
    if h < 1:
        return "пред помалку од час"
    if h < 48:
        return f"пред {h} ч"
    return f"пред {h // 24} дена"


def signal_detail(row: dict, today: date) -> str:
    """Admin-facing: how many views/questions and how long ago."""
    parts = []
    nv, na = int(row.get("n_views") or 0), int(row.get("n_asks") or 0)
    if nv:
        parts.append(f"{nv}× прегледан")
    if na:
        parts.append(f"{na}× прашање до асистентот")
    who = row.get("company_name") or row.get("full_name") or row.get("email")
    acct = row.get("account_type") or ""
    close = row.get("closing_date")
    days = (close - today).days if close else None
    s = f"{who} ({acct}): {', '.join(parts) or 'активност'}, последно {_ago(row.get('last_at'))}."
    if days is not None:
        s += f" Рок {fmt_date(close)} (за {days} дена)."
    return s


def signal_draft(row: dict) -> dict:
    """Reply naming the exact tender they opened. Two variants by account_type."""
    title = display_title(row.get("title"))
    entity = (row.get("procuring_entity") or "Договорниот орган").strip()
    close = row.get("closing_date")
    tid = row.get("tender_id")
    company = (row.get("company_name") or "").strip()
    lines = [greeting(row.get("full_name")), ""]
    if (row.get("account_type") or "") == "managed_client":
        lines += [
            f"Видовме дека го разгледувате тендерот „{title}“ на {entity}, "
            f"со рок за поднесување {fmt_date(close)}.",
            "",
            "Дали да ја подготвиме понудата? Кликнете „Започни понуда“ на страницата на "
            "тендерот или одговорете на оваа порака.",
        ]
    else:
        about = f" за {company}" if company else ""
        lines += [
            f"Видовме дека Ве интересира тендерот „{title}“ на {entity}, "
            f"со рок за поднесување {fmt_date(close)}.",
            "",
            f"Ние ја подготвуваме целата понуда{about}: ја читаме тендерската документација, "
            "ги подготвуваме документите и Ви ја предаваме готова за потпис.",
            "",
            "Дали сакате да учествувате? Ако да, ќе ја прегледаме документацијата и ќе Ви "
            "кажеме точно што бара договорниот орган.",
        ]
    if tid:
        # managed_client: ?ponuda=1&start=1 scrolls to WriteMyBidCard and opens
        # the „Започни понуда“ dialog (StartBidButton autoStart).
        link = tender_link(tid)
        if (row.get("account_type") or "") == "managed_client":
            link += "?ponuda=1&start=1"
        lines += ["", link]
    body = "\n".join(lines) + SIGNATURE
    return {
        "to": (row.get("email") or "").strip().lower(),
        "subject": f"Тендер: {short_title(title)}",
        "body_text": body,
    }
