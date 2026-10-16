"""
Daily operator focus: the one morning list Atilla runs NabavkiData from.

NabavkiData port of BidFinder's services/focus.py (Phase 4, Oct 2026).

Doctrine: the system builds the list and writes drafts; a human presses Send.
Items are derived from LIVE state on every call, so they disappear when reality
changes (lead triaged, job paid, tender closed). build_focus() never writes.
focus_item_state only holds human decisions (done / snoozed) keyed by a
deterministic item key.

BidFinder's bid_nudges misfire (57 e-mails to one client about a closed
tender) is why: every item is idempotent, keyed, drops off on its own once
resolved or once the tender closes, and closed tenders are never offered.

Used by api/ops.py (/admin/focus, signed "Готово" links, .ics feed) and
crons/daily_focus.py (06:30 Europe/Skopje e-mail to Atilla only).
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from services import hot_signal, lead_watch, ops_copy
from services.ops_copy import (SIGNATURE, SITE, SKOPJE, display_title, fmt_date, greeting,
                               iso_week, key_part, short_title, tender_link, week_start)

log = logging.getLogger(__name__)

FOCUS_MANUAL_PATH = ops_copy.FOCUS_MANUAL_PATH
STALE_PREPARING_DAYS = 3
LEAD_LOOKBACK_DAYS = 60

KIND_PRIORITY = {
    "manual_today": 5,
    "hot_signal": 10,
    "client_message": 20,
    "job_approved_deadline": 30,
    "job_ready_deadline": 30,
    "job_changes": 31,
    "job_preparing_deadline": 32,
    "job_preparing": 33,
    "job_requested": 34,
    "job_invoice": 35,
    "job_payment_check": 36,
    "job_checkout_abandoned": 37,
    "win_review": 40,
    "lead_untriaged": 50,
    "goback": 60,
    "shortlist_curate": 70,
    "client_touch": 71,
    "manual": 80,
}

KIND_GROUP = {
    "manual": "reminders",
    "hot_signal": "sales",
    "client_message": "clients",
    "job_approved_deadline": "clients",
    "job_ready_deadline": "clients",
    "job_changes": "clients",
    "job_preparing_deadline": "clients",
    "job_preparing": "clients",
    "job_requested": "money",
    "job_invoice": "money",
    "job_payment_check": "money",
    "job_checkout_abandoned": "money",
    "win_review": "money",
    "lead_untriaged": "sales",
    "goback": "sales",
    "shortlist_curate": "sales",
    "client_touch": "clients",
}

CAPS = {"hot_signal": 10, "lead_untriaged": 15, "goback": 4}

OFF_DAY_KINDS = frozenset({"hot_signal", "client_message", "job_approved_deadline",
                           "job_ready_deadline", "job_preparing_deadline", "manual"})

COLLAPSE_KINDS = ("hot_signal", "lead_untriaged", "goback")
SALES_KINDS = frozenset({"hot_signal", "lead_untriaged", "goback"})

KEY_PREFIX_KIND = {
    "hot": "hot_signal", "msg": "client_message", "win": "win_review",
    "lead": "lead_untriaged", "goback": "goback", "shortlist": "shortlist_curate",
    "touch": "client_touch", "manual": "manual",
}
JOB_SUFFIX_KIND = {
    "approved": "job_approved_deadline", "ready-deadline": "job_ready_deadline",
    "changes": "job_changes",
    "preparing-deadline": "job_preparing_deadline", "preparing": "job_preparing",
    "requested": "job_requested", "invoice": "job_invoice",
    "paycheck": "job_payment_check", "checkout": "job_checkout_abandoned",
}


# ---------------------------------------------------------------------------
# Manual file / off-days
# ---------------------------------------------------------------------------
def load_manual(path: Optional[str] = None) -> list:
    return ops_copy.load_manual(path or FOCUS_MANUAL_PATH)


def holiday_until(manual) -> Optional[date]:
    return ops_copy.holiday_until(manual)


def is_off_day(day: date, manual: Optional[list] = None) -> bool:
    return ops_copy.off_day(day, load_manual() if manual is None else manual)


def kind_of_key(key: str) -> str:
    head, _, rest = key.partition(":")
    if head == "job":
        parts = rest.split(":")
        return JOB_SUFFIX_KIND.get(parts[1] if len(parts) > 1 else "", "job")
    return KEY_PREFIX_KIND.get(head, "manual")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _iso(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _num(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def tender_obj(r: dict) -> Optional[dict]:
    if not r or not r.get("tender_id"):
        return None
    return {
        "tender_id": r.get("tender_id"),
        "title": r.get("title"),
        "procuring_entity": r.get("procuring_entity"),
        "closing_date": _iso(_as_date(r.get("closing_date"))),
        "estimated_value_mkd": _num(r.get("estimated_value_mkd")),
    }


def tender_is_open(r: dict, today: date, status_field: str = "t_status") -> bool:
    cd = _as_date(r.get("closing_date"))
    st = r.get(status_field)
    return cd is not None and cd >= today and (st is None or str(st).lower() in ("open", "active"))


def _item(kind: str, key: str, today: date, title: str, detail: str, *, email=None,
          tender=None, links=None, draft=None, meta=None, priority=None) -> dict:
    return {
        "key": key,
        "kind": kind,
        "group": KIND_GROUP[kind],
        "priority": priority if priority is not None else KIND_PRIORITY[kind],
        "date": today.isoformat(),
        "title": title,
        "detail": detail,
        "email": (email or "").strip().lower() or None,
        "tender": tender,
        "links": links or [],
        "draft": draft,
        "meta": meta or {},
    }


def _link(label: str, path_or_url: str) -> dict:
    href = path_or_url if path_or_url.startswith("http") else f"{SITE}{path_or_url}"
    return {"label": label, "href": href}


def _who(r: dict) -> str:
    return (r.get("company_name") or r.get("full_name") or r.get("email") or "").strip()


# ---------------------------------------------------------------------------
# Draft builders (all must pass ops_copy.check_draft_copy)
# ---------------------------------------------------------------------------
def draft_lead_reply(lead: dict, tender_open: bool) -> dict:
    company = (lead.get("company_name") or "").strip()
    lines = [greeting(lead.get("lead_person")), ""]
    lines.append(f"Ви благодариме за барањето што го испративте{f' за {company}' if company else ''}.")
    if tender_open and lead.get("title"):
        lines += ["", f"Го погледнавме тендерот „{display_title(lead['title'])}“ на "
                      f"{(lead.get('procuring_entity') or 'договорниот орган').strip()}, "
                      f"со рок за поднесување {fmt_date(lead.get('closing_date'))}."]
    lines += [
        "",
        "За да проценимо како најдобро да Ви помогнеме, Ве молиме одговорете ни на две прашања:",
        "1. Дали досега сте учествувале на слични тендери, односно дали имате референци од слични договори?",
        "2. Дали Ви се подготвени основните документи (тековна состојба, даночно уверение)?",
    ]
    if tender_open and lead.get("tender_id"):
        lines += ["", tender_link(lead["tender_id"])]
    subject = (f"Тендер: {short_title(lead['title'])}" if tender_open and lead.get("title")
               else "Вашето барање до НабавкиДата")
    return {"to": (lead.get("email") or "").strip().lower(), "subject": subject,
            "body_text": "\n".join(lines) + SIGNATURE}


def draft_payment_check(job: dict) -> dict:
    inv = (job.get("invoice_number") or "").strip()
    inv_txt = f"бр. {inv} " if inv else ""
    lines = [
        greeting(job.get("full_name")), "",
        f"Ви пишуваме во врска со фактурата {inv_txt}за подготовка на понудата за тендерот "
        f"„{display_title(job.get('title'))}“.",
        "",
        "Дали уплатата е извршена? Ако веќе сте платиле, Ве молиме испратете ни потврда за "
        "уплата како одговор на оваа порака, за да продолжиме со подготовката без застој.",
    ]
    if job.get("closing_date"):
        lines += ["", f"Рокот за поднесување на понудата е {fmt_date(job.get('closing_date'))}."]
    lines += ["", f"{SITE}/portal/bid/{job['id']}"]
    return {"to": (job.get("email") or "").strip().lower(),
            "subject": f"Фактура {inv}".strip() + " — подготовка на понуда",
            "body_text": "\n".join(lines) + SIGNATURE}


def draft_checkout_help(job: dict) -> dict:
    lines = [
        greeting(job.get("full_name")), "",
        f"Видовме дека започнавте плаќање со картичка за подготовка на понудата за тендерот "
        f"„{display_title(job.get('title'))}“, но плаќањето не е завршено.",
        "",
        "Ако имате проблем со картичката, во порталот можете да побарате фактура и да платите "
        "со уплатница, или едноставно одговорете на оваа порака и ќе Ви помогнеме.",
    ]
    if job.get("closing_date"):
        lines += ["", f"Рокот за поднесување е {fmt_date(job.get('closing_date'))}."]
    lines += ["", f"{SITE}/portal/bid/{job['id']}"]
    return {"to": (job.get("email") or "").strip().lower(),
            "subject": f"Плаќање за понудата: {short_title(job.get('title'))}",
            "body_text": "\n".join(lines) + SIGNATURE}


def draft_submit_reminder(job: dict) -> dict:
    lines = [
        greeting(job.get("full_name")), "",
        f"Потсетник: рокот за поднесување на понудата за тендерот „{display_title(job.get('title'))}“ "
        f"на {(job.get('procuring_entity') or 'договорниот орган').strip()} е "
        f"{fmt_date(job.get('closing_date'))}.",
        "",
        "Понудата е одобрена и подготвена. Ве молиме поднесете ја преку ЕСЈН со Вашиот "
        "сертификат пред истекот на рокот, а потоа кликнете „Поднесено“ во порталот.",
        "",
        "Ако Ви треба помош при поднесувањето, одговорете на оваа порака.",
        "",
        f"{SITE}/portal/bid/{job['id']}",
    ]
    return {"to": (job.get("email") or "").strip().lower(),
            "subject": f"Рок за поднесување: {short_title(job.get('title'))}",
            "body_text": "\n".join(lines) + SIGNATURE}


def draft_review_reminder(job: dict) -> dict:
    """status='ready' close to the deadline: the client has not reviewed the offer yet."""
    lines = [
        greeting(job.get("full_name")), "",
        f"Понудата за тендерот „{display_title(job.get('title'))}“ на "
        f"{(job.get('procuring_entity') or 'договорниот орган').strip()} е подготвена и Ве чека "
        f"во порталот. Рокот за поднесување е {fmt_date(job.get('closing_date'))}.",
        "",
        "Ве молиме прегледајте ги документите и одобрете ги („Одобри сè“) или побарајте измени, "
        "за да ја финализираме навреме пред рокот.",
        "",
        "Ако имате прашања, одговорете на оваа порака.",
        "",
        f"{SITE}/portal/bid/{job['id']}",
    ]
    return {"to": (job.get("email") or "").strip().lower(),
            "subject": f"Понудата е подготвена за преглед: {short_title(job.get('title'))}",
            "body_text": "\n".join(lines) + SIGNATURE}


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
# t_status / t_exists: client-facing job drafts are attached only while the
# tender row exists and is open (a cancelled tender keeps the internal item).
SQL_JOBS = """
SELECT j.*, u.email, u.company_name, u.full_name, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd,
       t.status AS t_status, (t.tender_id IS NOT NULL) AS t_exists
FROM bid_jobs j JOIN users u ON u.user_id = j.user_id LEFT JOIN tenders t ON t.tender_id = j.tender_id
WHERE j.status IN ('requested','payment_required','preparing','ready','changes_requested','approved')
  AND (t.closing_date IS NULL OR t.closing_date >= $1)
  AND COALESCE(u.role,'user') <> 'admin'
"""

SQL_CLIENT_MESSAGES = """
SELECT m.user_id, m.job_id, lower(u.email) AS email, u.company_name, u.full_name,
       COUNT(*) AS n,
       (array_agg(m.id ORDER BY m.created_at DESC))[1] AS last_id,
       MAX(m.created_at) AS last_at,
       (array_agg(m.body ORDER BY m.created_at DESC))[1] AS last_body,
       j.tender_id, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd
FROM bid_messages m
JOIN users u ON u.user_id = m.user_id AND COALESCE(u.role,'user') <> 'admin'
LEFT JOIN bid_jobs j ON j.id = m.job_id
LEFT JOIN tenders t ON t.tender_id = j.tender_id
WHERE m.sender_role = 'client' AND m.read_by_admin_at IS NULL
GROUP BY m.user_id, m.job_id, u.email, u.company_name, u.full_name,
         j.tender_id, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd
ORDER BY MAX(m.created_at) DESC
"""

SQL_WINS = """
SELECT w.id, w.user_id, w.job_id, w.tender_id, w.tender_title, w.procuring_entity, w.matched_name,
       w.match_score, w.detected_at, lower(u.email) AS email, u.company_name, u.full_name
FROM client_wins w JOIN users u ON u.user_id = w.user_id
WHERE w.status = 'suspected'
ORDER BY w.detected_at DESC
"""

# Fetches more than CAPS["lead_untriaged"]: the cap is applied after done/snooze
# filtering. A lead we already e-mailed after it came in (any kind of send) is
# not offered again; record_contact() normally moves it to 'contacted' anyway.
SQL_LEADS = """
SELECT l.*, t.title, t.procuring_entity, t.closing_date, t.status AS t_status
FROM bid_service_leads l LEFT JOIN tenders t ON t.tender_id = l.tender_id
WHERE l.status = 'new' AND l.created_at > NOW() - interval '60 days'
  AND NOT EXISTS (SELECT 1 FROM ops_sent_emails e
                  WHERE e.to_email = lower(l.email) AND e.sent_at > l.created_at)
ORDER BY l.created_at DESC LIMIT 40
"""

SQL_SHORTLIST_DRAFTS = """
SELECT COUNT(*) FILTER (WHERE status = 'draft') AS drafts, COUNT(*) AS total
FROM client_shortlists WHERE week_start = $1
"""

SQL_CLIENT_TOUCH = """
SELECT u.user_id, lower(u.email) AS email, u.company_name, u.full_name
FROM users u
WHERE u.account_type = 'managed_client' AND COALESCE(u.role,'user') <> 'admin'
  AND NOT EXISTS (SELECT 1 FROM bid_messages b WHERE b.user_id = u.user_id
                  AND b.sender_role = 'admin' AND b.created_at >= $1)
  AND NOT EXISTS (SELECT 1 FROM ops_sent_emails e WHERE e.to_email = lower(u.email) AND e.sent_at >= $1)
  AND NOT EXISTS (SELECT 1 FROM client_shortlists s WHERE s.user_id = u.user_id
                  AND s.status = 'sent' AND s.week_start = $2)
ORDER BY u.company_name NULLS LAST
"""

# Suppressed addresses plus admin accounts (contract: role='admin' is internal everywhere).
SQL_SUPPRESSED = """
SELECT lower(email) AS email FROM suppression_list WHERE lower(email) = ANY($1::text[])
UNION
SELECT lower(email) FROM users WHERE lower(email) = ANY($1::text[]) AND lower(COALESCE(role,'user')) = 'admin'
"""

SQL_STATES = """
SELECT key, kind, status, done_at, done_via, snoozed_until, title_snapshot
FROM focus_item_state WHERE key = ANY($1::text[])
"""

SQL_DONE_TODAY = """
SELECT key, kind, status, done_at, done_via, snoozed_until, title_snapshot
FROM focus_item_state WHERE status = 'done' AND done_at >= $1
"""

SQL_STATE_ONE = "SELECT key, kind, status, done_at, snoozed_until FROM focus_item_state WHERE key = $1"

# Claim-style: returns the key only when THIS call moved it to done, so two
# concurrent "done" requests (UI + e-mailed link, double submit) apply the side
# effects exactly once.
SQL_MARK_DONE = """
INSERT INTO focus_item_state (key, kind, status, done_at, done_via, done_by, snoozed_until, title_snapshot)
VALUES ($1, $2, 'done', NOW(), $3, $4, NULL, $5)
ON CONFLICT (key) DO UPDATE SET
  status = 'done', done_at = NOW(), done_via = EXCLUDED.done_via, done_by = EXCLUDED.done_by,
  snoozed_until = NULL,
  title_snapshot = COALESCE(EXCLUDED.title_snapshot, focus_item_state.title_snapshot),
  updated_at = NOW()
WHERE focus_item_state.status <> 'done'
RETURNING key
"""

SQL_HIDDEN_GOBACK = """
SELECT key FROM focus_item_state
WHERE key LIKE 'goback:%' AND (status = 'done' OR (status = 'snoozed' AND snoozed_until > $1))
"""

SQL_MANUAL_SENT = ("INSERT INTO ops_sent_emails (dedupe_key, kind, to_email, subject, channel) "
                   "VALUES ($1, $2, $3, $4, 'manual')")

SQL_LEADS_CONTACTED_BY_EMAIL = ("UPDATE bid_service_leads SET status='contacted', updated_at=NOW() "
                                "WHERE lower(email) = $1 AND status='new'")

SQL_SNOOZE = """
INSERT INTO focus_item_state (key, kind, status, snoozed_until, title_snapshot)
VALUES ($1, $2, 'snoozed', $3, $4)
ON CONFLICT (key) DO UPDATE SET
  status = 'snoozed', snoozed_until = EXCLUDED.snoozed_until, done_at = NULL, done_via = NULL,
  done_by = NULL,
  title_snapshot = COALESCE(EXCLUDED.title_snapshot, focus_item_state.title_snapshot),
  updated_at = NOW()
"""

SQL_REOPEN = """
UPDATE focus_item_state SET status = 'open', done_at = NULL, done_via = NULL, done_by = NULL,
       snoozed_until = NULL, updated_at = NOW()
 WHERE key = $1
"""

SQL_LEAD_CONTACTED = ("UPDATE bid_service_leads SET status='contacted', updated_at=NOW() "
                      "WHERE id=$1 AND status='new'")


# ---------------------------------------------------------------------------
# Item sources
# ---------------------------------------------------------------------------
def manual_items(manual: list, today: date) -> list[dict]:
    out = []
    for m in manual or []:
        if not isinstance(m, dict) or "date" not in m or not m.get("title"):
            continue
        d = _as_date(m.get("date"))
        if d is None or not (d - timedelta(days=3) <= today <= d):
            continue
        title = str(m["title"]).strip()
        n = (d - today).days
        prefix = "[ДЕНЕС]" if n == 0 else f"[за {n} дена]"
        key = f"manual:{d.isoformat()}:{hashlib.sha1(title.encode('utf-8')).hexdigest()[:10]}"
        out.append(_item("manual", key, today, f"{prefix} {title}", str(m.get("detail") or ""),
                         meta={"manual_date": d.isoformat()},
                         priority=KIND_PRIORITY["manual_today"] if n == 0 else KIND_PRIORITY["manual"]))
    return out


async def hot_items(conn, today: date, manual: list) -> list[dict]:
    rows = await hot_signal.find_hot_signals(conn, today, hot_signal.lookback_hours(today, manual))
    out = []
    for r in rows:              # CAPS applied in build_focus, after done/snooze
        tid = r["tender_id"]
        out.append(_item(
            "hot_signal", f"hot:{r['user_id']}:{key_part(tid)}", today,
            f"ВРЕДНО: {_who(r)} гледа „{short_title(r.get('title'))}“",
            hot_signal.signal_detail(r, today),
            email=r.get("email"), tender=tender_obj(r),
            links=[_link("Отвори тендер", tender_link(tid)), _link("Корисници", "/admin/users")],
            draft=hot_signal.signal_draft(r),
            meta={"user_id": str(r["user_id"]), "account_type": r.get("account_type"),
                  "n_views": int(r.get("n_views") or 0), "n_asks": int(r.get("n_asks") or 0),
                  "first_at": _iso(r.get("first_at")), "last_at": _iso(r.get("last_at"))}))
    return out


async def message_items(conn, today: date) -> list[dict]:
    out = []
    for r in [dict(x) for x in await conn.fetch(SQL_CLIENT_MESSAGES)]:
        job = str(r["job_id"]) if r.get("job_id") else "general"
        body = " ".join((r.get("last_body") or "").split())
        snippet = body[:160] + ("…" if len(body) > 160 else "")
        n = int(r.get("n") or 1)
        href = f"/admin/bids/{r['job_id']}" if r.get("job_id") else "/admin/bids"
        about = f" за „{short_title(r.get('title'))}“" if r.get("title") else ""
        out.append(_item(
            "client_message", f"msg:{r['user_id']}:{job}:{r['last_id']}", today,
            f"Порака од {_who(r)}{about} ({n} непрочитан{'а' if n == 1 else 'и'})",
            f"„{snippet}“", tender=tender_obj(r),
            links=[_link("Отвори", href)],
            meta={"user_id": str(r["user_id"]), "job_id": r.get("job_id") and str(r["job_id"]),
                  "client_email": r.get("email")}))
    return out


def classify_job(j: dict, today: date, now: datetime) -> list[dict]:
    """Every rule that matches a job becomes one item (a job may yield several)."""
    out: list[dict] = []
    jid = str(j["id"])
    st = j.get("status")
    cd = _as_date(j.get("closing_date"))
    days_left = (cd - today).days if cd else None
    who = _who(j)
    t = short_title(j.get("title")) or j.get("tender_id") or ""
    rok = f"Рок {fmt_date(cd)} (за {days_left} дена)." if cd else "Без рок во базата."
    # Client-facing drafts only while the tender exists and is open (contract §0);
    # otherwise the internal item stays, without a draft.
    t_ok = bool(j.get("t_exists", j.get("title") is not None)) and tender_is_open(j, today)

    def add(kind, suffix, title, detail, draft=None):
        if draft is not None and not t_ok:
            draft = None
            detail += " Тендерот е затворен/поништен или го нема во базата: без нацрт до клиентот."
        out.append(_item(kind, f"job:{jid}:{suffix}", today, title, detail,
                         email=(draft or {}).get("to"), draft=draft, tender=tender_obj(j),
                         links=[_link("Отвори", f"/admin/bids/{jid}")],
                         meta={"job_id": jid, "user_id": str(j.get("user_id")), "status": st,
                               "client_email": (j.get("email") or "").lower() or None}))

    if st == "approved" and days_left is not None and days_left <= 3:
        add("job_approved_deadline", "approved",
            f"Поднесување: {who} — „{t}“",
            f"Понудата е одобрена, но не е означена како поднесена. {rok}",
            draft_submit_reminder(j))
    if st == "ready" and days_left is not None and days_left <= 3:
        add("job_ready_deadline", "ready-deadline",
            f"Клиентот не ја прегледал понудата: {who} — „{t}“",
            f"Понудата е објавена, а клиентот сè уште не ја одобрил ниту побарал измени. {rok}",
            draft_review_reminder(j))
    if st == "changes_requested":
        add("job_changes", f"changes:{int(j.get('reopen_count') or 0)}",
            f"Измени побарани: {who} — „{t}“",
            f"Клиентот побара измени на понудата. {rok}")
    if st == "preparing" and j.get("published_at") is None and days_left is not None and days_left <= 5:
        add("job_preparing_deadline", "preparing-deadline",
            f"Рок близу, понуда необјавена: {who} — „{t}“",
            f"Понудата е во подготовка и сè уште не е објавена на клиентот. {rok}")
    if st == "preparing":
        anchor = _aware(j.get("paid_at")) or _aware(j.get("created_at"))
        upd = _aware(j.get("updated_at"))
        last = max([x for x in (anchor, upd) if x is not None], default=None)
        if last is not None and last < now - timedelta(days=STALE_PREPARING_DAYS):
            idle = (now - last).days
            add("job_preparing", "preparing",
                f"Подготовка застанала: {who} — „{t}“",
                f"Нема промена {idle} дена. {rok}")
    if st == "requested":
        add("job_requested", "requested",
            f"Ново барање за понуда: {who} — „{t}“",
            f"Поставете надомест, означете платено или бесплатно. {rok}")
    if st == "payment_required":
        paid = j.get("paid_at") is not None
        inv_req = j.get("invoice_requested_at")
        inv_iss = _aware(j.get("invoice_issued_at"))
        if inv_req is not None and inv_iss is None and not paid:
            add("job_invoice", "invoice",
                f"Издај фактура: {who} — „{t}“",
                f"Клиентот побара фактура. {rok}")
        if inv_iss is not None and inv_iss < now - timedelta(days=2) and not paid:
            add("job_payment_check", "paycheck",
                f"Провери уплата: {who} — „{t}“",
                f"Фактура {j.get('invoice_number') or ''} издадена пред {(now - inv_iss).days} дена, "
                f"нема уплата. {rok}",
                draft_payment_check(j))
        upd = _aware(j.get("updated_at"))
        if (j.get("stripe_checkout_session_id") and inv_req is None and not paid
                and upd is not None and upd < now - timedelta(hours=24)):
            add("job_checkout_abandoned", "checkout",
                f"Прекинато плаќање со картичка: {who} — „{t}“",
                f"Започнато плаќање со картичка, незавршено повеќе од 24 часа. {rok}",
                draft_checkout_help(j))
    return out


async def job_items(conn, today: date, now: datetime) -> list[dict]:
    out = []
    for j in [dict(x) for x in await conn.fetch(SQL_JOBS, today)]:
        out.extend(classify_job(j, today, now))
    return out


async def win_items(conn, today: date) -> list[dict]:
    out = []
    for w in [dict(x) for x in await conn.fetch(SQL_WINS)]:
        score = _num(w.get("match_score"))
        out.append(_item(
            "win_review", f"win:{w['id']}", today,
            f"Можна победа: {_who(w)} — „{short_title(w.get('tender_title'))}“",
            f"Победник во податоците: {w.get('matched_name') or '?'}"
            + (f" (совпаѓање {score:.2f})" if score is not None else "")
            + ". Потврди или отфрли.",
            tender={"tender_id": w.get("tender_id"), "title": w.get("tender_title"),
                    "procuring_entity": w.get("procuring_entity"), "closing_date": None,
                    "estimated_value_mkd": None} if w.get("tender_id") else None,
            links=[_link("Победи", "/admin/wins")],
            meta={"win_id": str(w["id"]), "user_id": str(w["user_id"]),
                  "client_email": w.get("email")}))
    return out


async def lead_items(conn, today: date) -> list[dict]:
    out = []
    for l in [dict(x) for x in await conn.fetch(SQL_LEADS)]:   # CAPS applied in build_focus
        email = (l.get("email") or "").strip().lower()
        has_tender = bool(l.get("tender_id"))
        t_open = has_tender and tender_is_open(l, today)
        who = (l.get("company_name") or email).strip()
        detail = f"Ново барање од /usluga ({l.get('source') or 'форма'})"
        if l.get("lead_person"):
            detail += f", лице: {l['lead_person']}"
        if l.get("wants_to_win"):
            detail += f". Сака: {' '.join(str(l['wants_to_win']).split())[:160]}"
        if has_tender and not t_open:
            detail += ". Тендерот е затворен."
        elif t_open:
            detail += f". Тендер {l['tender_id']}, рок {fmt_date(l.get('closing_date'))}."
        links = [_link("Лидови", "/admin/leads")]
        if t_open:
            links.insert(0, _link("Отвори тендер", tender_link(l["tender_id"])))
        out.append(_item(
            "lead_untriaged", f"lead:{l['id']}", today,
            f"Нов лид: {who}", detail, email=email,
            tender=tender_obj(l) if t_open else None, links=links,
            draft=draft_lead_reply(l, t_open),
            meta={"lead_id": str(l["id"]), "user_id": l.get("user_id") and str(l["user_id"]),
                  "tender_open": t_open}))
    return out


async def shortlist_items(conn, today: date) -> list[dict]:
    ws = week_start(today)
    row = await conn.fetchrow(SQL_SHORTLIST_DRAFTS, ws)
    r = dict(row) if row else {}
    drafts = int(r.get("drafts") or 0)
    if drafts <= 0:
        return []
    total = int(r.get("total") or drafts)
    return [_item("shortlist_curate", f"shortlist:{iso_week(today)}", today,
                  f"Шортлисти за неделата: {drafts} нацрт(и) чекаат избор",
                  f"Изберете 2–4 тендери по клиент, додадете белешка и испратете ({drafts}/{total} нацрти).",
                  links=[_link("Шортлисти", "/admin/shortlists")],
                  meta={"week_start": ws.isoformat(), "drafts": drafts, "total": total})]


async def touch_items(conn, today: date) -> list[dict]:
    if today.weekday() != 0:
        return []
    ws = week_start(today)
    since = datetime.combine(ws, dtime(0, 0), tzinfo=SKOPJE)
    out = []
    for u in [dict(x) for x in await conn.fetch(SQL_CLIENT_TOUCH, since, ws)]:
        out.append(_item(
            "client_touch", f"touch:{u['user_id']}:{iso_week(today)}", today,
            f"Неделен допир: {_who(u)}",
            "Клиент без порака од нас оваа недела. Напишете кратко лично ажурирање во порталот.",
            email=u.get("email"), links=[_link("Понуди", "/admin/bids")],
            meta={"user_id": str(u["user_id"])}))
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def collapse_per_recipient(items: list[dict]) -> list[dict]:
    """Among hot_signal / lead_untriaged / goback keep one item per e-mail:
    the lowest priority number. Dropped keys go to the survivor's meta."""
    best: dict = {}
    for it in items:
        if it["kind"] not in COLLAPSE_KINDS or not it.get("email"):
            continue
        cur = best.get(it["email"])
        if cur is None or (it["priority"], it["key"]) < (cur["priority"], cur["key"]):
            best[it["email"]] = it
    out = []
    for it in items:
        if it["kind"] in COLLAPSE_KINDS and it.get("email"):
            surv = best[it["email"]]
            if surv is not it:
                surv["meta"].setdefault("collapsed_keys", []).append(it["key"])
                continue
        out.append(it)
    return out


def sort_items(items: list[dict]) -> list[dict]:
    def k(it):
        cd = (it.get("tender") or {}).get("closing_date")
        return (it["priority"], 0 if cd else 1, cd or "", it.get("title") or "")
    return sorted(items, key=k)


def _recipient(it: dict) -> Optional[str]:
    return it.get("email") or (it.get("meta") or {}).get("client_email")


async def _filter_recipients(conn, items: list[dict]) -> list[dict]:
    """Drop internal recipients everywhere. A suppressed address loses sales
    items entirely; client/money items stay (work still has to happen) but
    lose their draft."""
    items = [it for it in items if not ops_copy.is_internal_email(_recipient(it))]
    emails = sorted({e for e in (_recipient(it) for it in items) if e})
    suppressed: set = set()
    if emails:
        suppressed = {r["email"] for r in await conn.fetch(SQL_SUPPRESSED, emails)}
    out = []
    for it in items:
        rec = _recipient(it)
        if rec and rec in suppressed:
            if it["kind"] in SALES_KINDS or it["kind"] == "client_touch":
                continue
            if it.get("draft"):
                it["draft"] = None
                it["email"] = None
                it["detail"] += " (Адресата е одјавена, без нацрт.)"
        out.append(it)
    return out


async def _collect(conn, today: date, manual: list, *, off: bool,
                   goback_skip: Optional[set] = None) -> tuple[list[dict], list[str]]:
    """Every live item (no state filter, no caps, no collapse). off=True applies the off-day kinds."""
    now = datetime.now(timezone.utc)
    notes: list[str] = []
    items: list[dict] = []
    items += manual_items(manual, today)

    async def safe(name, coro):
        try:
            return await coro
        except Exception as e:  # one broken source must not blank the morning list
            log.exception("focus source %s failed", name)
            notes.append(f"Изворот „{name}“ не успеа: {e.__class__.__name__}")
            return []

    items += await safe("hot_signal", hot_items(conn, today, manual))
    items += await safe("client_message", message_items(conn, today))
    items += await safe("jobs", job_items(conn, today, now))
    if not off:
        items += await safe("win_review", win_items(conn, today))
        items += await safe("lead_untriaged", lead_items(conn, today))
        gb_stats: dict = {}
        gb = await safe("goback", lead_watch.build_follow_ups(
            conn, today, False, limit=CAPS["goback"], skip_keys=goback_skip, stats=gb_stats))
        if isinstance(gb, tuple):
            gb_items, nothing_new = gb
            items += gb_items
            if nothing_new:
                notes.append(f"{nothing_new} го-бек лидови на ред, нема нов тендер")
        if gb_stats.get("no_keywords"):
            notes.append(f"{gb_stats['no_keywords']} го-бек лидови на ред без клучни зборови "
                         "(никогаш нема да добијат го-бек додека не им се додадат)")
        items += await safe("shortlist_curate", shortlist_items(conn, today))
        items += await safe("client_touch", touch_items(conn, today))
    else:
        items = [it for it in items if it["kind"] in OFF_DAY_KINDS]
    items = await _filter_recipients(conn, items)
    return items, notes


def _stub_from_state(s: dict, today: date) -> dict:
    kind = s.get("kind") if s.get("kind") in KIND_GROUP else kind_of_key(s["key"])
    if kind not in KIND_GROUP:
        kind = "manual"
    return {"key": s["key"], "kind": kind, "group": KIND_GROUP[kind],
            "priority": KIND_PRIORITY.get(kind, 90), "date": today.isoformat(),
            "title": s.get("title_snapshot") or s["key"], "detail": "", "email": None,
            "tender": None, "links": [], "draft": None,
            "meta": {"done_at": _iso(s.get("done_at")), "done_via": s.get("done_via"), "stub": True}}


def apply_caps(items: list[dict]) -> list[dict]:
    """CAPS per kind, in source order (hot: newest activity, leads: newest, goback:
    oldest due). Applied AFTER done/snooze filtering so hidden items never use a slot."""
    seen: dict = {}
    out = []
    for it in items:
        cap = CAPS.get(it["kind"])
        if cap is not None:
            seen[it["kind"]] = seen.get(it["kind"], 0) + 1
            if seen[it["kind"]] > cap:
                continue
        out.append(it)
    return out


async def build_focus(conn, today: date, *, include_done: bool = False,
                      manual: Optional[list] = None) -> dict:
    """The morning list. Read-only."""
    manual = load_manual() if manual is None else manual
    off = is_off_day(today, manual)
    goback_skip: set = set()
    if not off:
        try:
            goback_skip = {r["key"] for r in await conn.fetch(SQL_HIDDEN_GOBACK, today)}
        except Exception:  # noqa: BLE001 - only an optimisation for the goback cap
            log.exception("focus: hidden goback keys lookup failed")
    items, notes = await _collect(conn, today, manual, off=off, goback_skip=goback_skip)

    keys = [it["key"] for it in items]
    states = {}
    if keys:
        states = {r["key"]: dict(r) for r in await conn.fetch(SQL_STATES, keys)}

    live, done = [], []
    for it in items:
        s = states.get(it["key"])
        if s and s["status"] == "done":
            if include_done:
                da = _aware(s.get("done_at"))
                if da is not None and da.astimezone(SKOPJE).date() == today:
                    it["meta"]["done_at"] = _iso(da)
                    it["meta"]["done_via"] = s.get("done_via")
                    done.append(it)
            continue
        if s and s["status"] == "snoozed":
            su = _as_date(s.get("snoozed_until"))
            if su is not None and su > today:
                continue
        live.append(it)

    if include_done:
        # Done today but no longer derivable (e.g. lead now 'contacted'): show from snapshot.
        start = datetime.combine(today, dtime(0, 0), tzinfo=SKOPJE)
        have = {it["key"] for it in done} | set(keys)
        for r in await conn.fetch(SQL_DONE_TODAY, start):
            r = dict(r)
            if r["key"] not in have:
                done.append(_stub_from_state(r, today))

    live = collapse_per_recipient(sort_items(apply_caps(live)))
    return {"date": today.isoformat(), "off_day": off, "items": sort_items(live),
            "done": sort_items(done), "notes": notes,
            "meta": {"off_day": off}}


async def _source_for_key(conn, key: str, today: date) -> list[dict]:
    """Only the source that can produce `key` (a click must not rebuild the whole list)."""
    kind = kind_of_key(key)
    now = datetime.now(timezone.utc)
    if kind == "manual":
        return manual_items(load_manual(), today)
    if kind == "hot_signal":
        return await hot_items(conn, today, load_manual())
    if kind == "client_message":
        return await message_items(conn, today)
    if kind in JOB_SUFFIX_KIND.values() or kind == "job":
        return await job_items(conn, today, now)
    if kind == "win_review":
        return await win_items(conn, today)
    if kind == "lead_untriaged":
        return await lead_items(conn, today)
    if kind == "goback":
        parts = key.split(":")
        if len(parts) != 3:
            return []
        try:
            watch_id = str(uuid.UUID(parts[1]))
        except ValueError:
            return []
        it = await lead_watch.follow_up_for_watch(conn, watch_id, today)
        return [it] if it else []
    if kind == "shortlist_curate":
        return await shortlist_items(conn, today)
    if kind == "client_touch":
        return await touch_items(conn, today)
    return []


async def get_item(conn, key: str, today: date) -> Optional[dict]:
    """Find a live item by key, whatever its state and whatever the day."""
    items = await _filter_recipients(conn, await _source_for_key(conn, key, today))
    for it in items:
        if it["key"] == key:
            return it
    return None


def _is_off_fn(manual: list):
    return lambda d: ops_copy.off_day(d, manual)


async def record_contact(conn, email: Optional[str], *, skip_watch_id=None, when=None) -> None:
    """We just wrote to `email` (any kind: hot signal, lead reply, shortlist, go-back,
    or a confirmed manual send). Resolve everything else that would write to the
    same person again:

      * every 'new' bid_service_leads row for that address -> 'contacted'
        (so lead:{id} drops off and sync_watches starts the go-back cadence)
      * the active lead_watch for that address is touched, so the go-back
        cadence restarts from this e-mail (skip_watch_id: already touched).

    hot_signal needs nothing: it drops off on the ops_sent_emails row itself.
    """
    e = (email or "").strip().lower()
    if not e:
        return
    await conn.execute(SQL_LEADS_CONTACTED_BY_EMAIL, e)
    w = await lead_watch.watch_for_email(conn, e)
    if (w and w.get("active") and w.get("replied_at") is None
            and str(w["id"]) != str(skip_watch_id or "")):
        await lead_watch.mark_touched(conn, w["id"], _is_off_fn(load_manual()), when)


async def mark_done(conn, key: str, today: date, via: str, actor_user_id=None, *,
                    item: Optional[dict] = None, sent_manually: bool = False) -> Optional[dict]:
    """Record the key as done and, only if THIS call did so, apply its side effects.

    Side effects:
      * lead_untriaged -> lead 'contacted' (any via: a „Готово“ after sending from
        Gmail must not strand the lead as 'new' with no go-back cadence)
      * goback -> record_shown + mark_touched
      * a real e-mail went out (via send / link, or sent_manually from the UI):
        record_contact() for the recipient, and for link / sent_manually a
        channel='manual' ops_sent_emails row (dedupe_key = key) so hot signals,
        client_touch and the go-back cooldown see it.
    `item` may be passed when the caller already resolved it. The state row is
    written even when the item can no longer be derived.
    """
    if via not in ("ui", "link", "send"):
        raise ValueError("via must be ui|link|send")
    if item is None:
        item = await get_item(conn, key, today)
    kind = item["kind"] if item else kind_of_key(key)
    claimed = await conn.fetchval(SQL_MARK_DONE, key, kind, via, actor_user_id,
                                  (item or {}).get("title"))
    if not claimed or not item:
        return item
    meta = item.get("meta") or {}
    touched_watch = None
    if kind == "lead_untriaged" and meta.get("lead_id"):
        await conn.execute(SQL_LEAD_CONTACTED, meta["lead_id"])
    elif kind == "goback" and meta.get("watch_id"):
        await lead_watch.record_shown(conn, meta["watch_id"], meta.get("tender_ids") or [])
        await lead_watch.mark_touched(conn, meta["watch_id"], _is_off_fn(load_manual()))
        touched_watch = meta["watch_id"]
    email = (item.get("email") or "").strip().lower()
    emailed = via in ("send", "link") or sent_manually
    if emailed and email:
        if via == "link" or sent_manually:
            await conn.execute(SQL_MANUAL_SENT, key, kind, email,
                               (item.get("draft") or {}).get("subject"))
        await record_contact(conn, email, skip_watch_id=touched_watch)
    return item


async def snooze(conn, key: str, today: date, days: int) -> date:
    days = max(1, min(int(days), 30))
    until = today + timedelta(days=days)
    await conn.execute(SQL_SNOOZE, key, kind_of_key(key), until, None)
    return until


async def reopen(conn, key: str) -> None:
    await conn.execute(SQL_REOPEN, key)
