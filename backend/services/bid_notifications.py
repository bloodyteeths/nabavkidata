"""
Bid-job email notifications (Phase 2 of the done-for-you bid service, Oct 2026).

One email per state transition, never a loop (BidFinder's 57-email incident):
every notification claims a unique (job_id, key) row in bid_job_events before
sending, where key = f"{kind}:{reopen_count}:{publish_count}" plus, for the
kinds that can legitimately repeat inside one publish cycle, a discriminator
(see notification_extra). A second call for the same transition finds the row
and sends nothing.

Emails never contain prices, fees or percentages and never contain emojis.
Client emails never carry message bodies (admins could type prices there).
"""
from __future__ import annotations

import html
import json
import logging
import uuid
from datetime import date, datetime
from typing import Any, Optional

from db_pool import get_asyncpg_pool
from services.postmark import postmark_service

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "atillatkulu@gmail.com"
SITE = "https://nabavkidata.com"
REPLY_TO = "hello@nabavkidata.com"

KINDS: dict[str, str] = {  # kind -> recipient 'client' | 'admin'
    "job_requested": "admin",
    "invoice_issued": "client",
    "preparing": "client",
    "ready": "client",
    "changes_requested": "admin",
    "approved": "admin",
    "submitted": "admin",
    "won": "client",
    "lost": "client",
    "tender_cancelled": "client",
    "cancelled_by_client": "admin",
    "cancelled_by_admin": "client",
    # Phase 2b (card payments, success fee)
    "invoice_requested": "admin",
    "paid_online": "admin",
    "win_detected": "admin",
    "success_fee_notice": "client",
    # A payment that needs a human (duplicate, cancelled/free job, amount
    # mismatch). Keyed by the caller's discriminator, so each case mails once.
    "payment_alert": "admin",
}

PAYMENT_ALERT_TEXT = {
    "duplicate": "Втора уплата со картичка за веќе платена понуда. Потребно е враќање на средствата.",
    "paid_while_cancelled": ("Уплата со картичка за откажано барање. Повторно отворете го "
                             "барањето или вратете ги средствата."),
    "free": "Уплата со картичка за понуда што е означена како бесплатна. Потребно е враќање на средствата.",
    "wrong_status": "Уплата со картичка во статус кога плаќање не се очекува. Проверете ја понудата.",
    "amount_mismatch": ("Платената сума не одговара на договорената за оваа понуда. Уплатата "
                        "не е евидентирана; проверете ја во Stripe."),
}

_WRAP_OPEN = ('<div style="font-family:sans-serif;font-size:15px;line-height:1.6;'
              'color:#1a1a1a;max-width:560px">')
_SIGNOFF = "<p>Поздрав,<br>Тимот на НабавкиДата<br>Фактурино ДООЕЛ</p>"
_ADMIN_TEAM_NAME = "Тимот на НабавкиДата"


def notification_key(kind: str, reopen_count: int, publish_count: int,
                     extra: Optional[str] = None) -> str:
    key = f"{kind}:{int(reopen_count or 0)}:{int(publish_count or 0)}"
    return f"{key}:{extra}" if extra else key


def notification_extra(kind: str, ctx: dict) -> Optional[str]:
    """Discriminator for transitions that can repeat within one publish cycle.

    - changes_requested / approved: the number of times the job has entered that
      status (audit rows), so approved -> changes_requested -> approved ->
      changes_requested emails each real transition once;
    - invoice_issued: the invoice number, so a corrected invoice is announced
      once more while re-issuing the same number stays silent.
    """
    if kind == "changes_requested":
        return f"c{int(ctx.get('changes_cycles') or 0)}"
    if kind == "approved":
        return f"a{int(ctx.get('approved_cycles') or 0)}"
    if kind == "invoice_issued":
        return str(ctx.get("invoice_number") or "")[:50] or None
    if kind == "payment_alert":
        return str(ctx.get("extra") or "alert")[:80]
    if kind == "success_fee_notice":
        # One notice per win (the caller passes the win id).
        return str(ctx.get("extra") or "")[:80] or None
    return None


# Kinds whose dedupe claim is released when the send fails, so the caller can
# retry (the success-fee notice starts the 7-day clock; it must really go out).
RETRYABLE_KINDS = {"success_fee_notice"}


async def release_notification(job_id: str, key: str) -> None:
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM bid_job_events WHERE job_id = $1 AND kind = 'notify' AND event = $2",
                _as_uuid(job_id), key)
    except Exception:
        logger.exception("could not release notify claim: job=%s key=%s", job_id, key)


def _e(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def _fmt_date(d: Any) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime("%d.%m.%Y")
    try:
        return date.fromisoformat(str(d)[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return None


def _as_uuid(v: Any) -> uuid.UUID:
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
async def load_context(conn, job_id: str) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT j.id AS job_id, j.status, j.outcome, j.reopen_count, j.publish_count,
               j.tender_id, t.title AS tender_title, t.procuring_entity, t.closing_date,
               j.invoice_number, u.email AS client_email, u.full_name AS client_name,
               u.company_name,
               (SELECT COUNT(*) FROM bid_job_events e WHERE e.job_id = j.id
                  AND e.kind = 'audit' AND e.event = 'changes_requested') AS changes_cycles,
               (SELECT COUNT(*) FROM bid_job_events e WHERE e.job_id = j.id
                  AND e.kind = 'audit' AND e.event = 'approved') AS approved_cycles,
               COALESCE((
                   SELECT json_agg(json_build_object('title', f.title, 'comment', f.client_comment)
                                   ORDER BY f.reviewed_at NULLS LAST, f.created_at)
                   FROM bid_job_files f
                   WHERE f.job_id = j.id AND f.approval_status = 'changes_requested'
               ), '[]'::json) AS change_comments
        FROM bid_jobs j
        JOIN users u ON u.user_id = j.user_id
        LEFT JOIN tenders t ON t.tender_id = j.tender_id
        WHERE j.id = $1
        """,
        _as_uuid(job_id),
    )
    if not row:
        return None
    ctx = dict(row)
    comments = ctx.get("change_comments")
    if isinstance(comments, str):
        try:
            comments = json.loads(comments)
        except ValueError:
            comments = []
    ctx["change_comments"] = comments or []
    ctx["job_id"] = str(ctx["job_id"])
    return ctx


async def claim_notification(conn, job_id: str, key: str) -> bool:
    val = await conn.fetchval(
        "INSERT INTO bid_job_events (job_id, kind, event, actor_role) "
        "VALUES ($1,'notify',$2,'system') "
        "ON CONFLICT (job_id, event) WHERE kind = 'notify' DO NOTHING RETURNING id",
        _as_uuid(job_id), key,
    )
    return val is not None


async def load_message_context(conn, message_id: str) -> dict | None:
    # earlier_unread counts only messages created BEFORE this one, so two quick
    # messages cannot suppress each other's email (both would see the other).
    row = await conn.fetchrow(
        """
        SELECT m.id AS message_id, m.user_id, m.job_id, m.sender_role, m.body,
               u.email AS client_email, u.full_name AS client_name, u.company_name,
               j.tender_id, t.title AS tender_title,
               (SELECT COUNT(*) FROM bid_messages o
                 WHERE o.user_id = m.user_id
                   AND o.job_id IS NOT DISTINCT FROM m.job_id
                   AND o.id <> m.id
                   AND o.sender_role = m.sender_role
                   AND (o.created_at < m.created_at
                        OR (o.created_at = m.created_at AND o.id < m.id))
                   AND ((m.sender_role = 'admin' AND o.read_by_client_at IS NULL)
                        OR (m.sender_role = 'client' AND o.read_by_admin_at IS NULL))
               ) AS earlier_unread
        FROM bid_messages m
        JOIN users u ON u.user_id = m.user_id
        LEFT JOIN bid_jobs j ON j.id = m.job_id
        LEFT JOIN tenders t ON t.tender_id = j.tender_id
        WHERE m.id = $1
        """,
        _as_uuid(message_id),
    )
    if not row:
        return None
    ctx = dict(row)
    for k in ("message_id", "user_id", "job_id"):
        if ctx.get(k) is not None:
            ctx[k] = str(ctx[k])
    ctx["earlier_unread"] = int(ctx.get("earlier_unread") or 0)
    return ctx


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _link(url: str, label: str) -> str:
    return f'<p><a href="{_e(url)}">{_e(label)}</a></p>'


def _client_html(paragraphs: list[str], url: str, label: str = "Отвори во порталот") -> str:
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f"{_WRAP_OPEN}<p>Почитувани,</p>{body}{_link(url, label)}{_SIGNOFF}</div>"


def _admin_html(rows: list[tuple[str, Any]], url: str, extra: str = "") -> str:
    table = "".join(
        f"<tr><td style='padding:4px 10px;color:#6b7280'>{_e(k)}</td>"
        f"<td style='padding:4px 10px'>{_e(v if v not in (None, '') else '-')}</td></tr>"
        for k, v in rows
    )
    return (f"{_WRAP_OPEN}<table style='font-size:14px'>{table}</table>{extra}"
            f"{_link(url, 'Отвори ја понудата')}</div>")


def render_email(kind: str, ctx: dict) -> tuple[str, str]:
    """(subject, html). Never includes amounts, currency, percentages or emojis."""
    job_id = ctx.get("job_id")
    tender_id = ctx.get("tender_id") or ""
    title = ctx.get("tender_title") or tender_id
    company = ctx.get("company_name") or ctx.get("client_email") or ""
    closing = _fmt_date(ctx.get("closing_date"))
    client_url = f"{SITE}/portal/bid/{job_id}"
    admin_url = f"{SITE}/admin/bids/{job_id}"
    t = _e(title)

    def admin_rows() -> list[tuple[str, Any]]:
        return [
            ("Клиент", company),
            ("Е-пошта", ctx.get("client_email")),
            ("Тендер", f"{tender_id} — {title}"),
            ("Договорен орган", ctx.get("procuring_entity")),
            ("Рок", closing),
        ]

    if kind == "job_requested":
        return (f"Ново барање за понуда: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url))
    if kind == "invoice_issued":
        return (f"Фактура за подготовка на понудата — {tender_id}",
                _client_html([
                    f"Ја издадовме фактурата бр. {_e(ctx.get('invoice_number'))} за подготовка на "
                    f"понудата за „{t}“. Со подготовката започнуваме штом ја евидентираме уплатата. "
                    f"Статусот го следите во порталот."
                ], client_url))
    if kind == "preparing":
        return ("Започнавме со подготовка на вашата понуда",
                _client_html([
                    f"Започнавме со подготовка на понудата за „{t}“. Ќе ве известиме кога "
                    f"документите ќе бидат подготвени за преглед."
                ], client_url))
    if kind == "ready":
        text = (f"Документите за понудата за „{t}“ се подготвени. Прегледајте ги и одобрете ги "
                f"или побарајте измени.")
        if closing:
            text += f" Рок за поднесување: {_e(closing)}."
        return ("Вашата понуда е подготвена за преглед", _client_html([text], client_url))
    if kind == "changes_requested":
        items = "".join(
            f"<li><strong>{_e(c.get('title'))}</strong>: {_e(c.get('comment'))}</li>"
            for c in (ctx.get("change_comments") or []) if isinstance(c, dict)
        )
        extra = f"<p>Забелешки:</p><ul>{items}</ul>" if items else ""
        return (f"Клиентот бара измени: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url, extra))
    if kind == "approved":
        return (f"Клиентот ја одобри понудата: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url))
    if kind == "submitted":
        return (f"Понудата е поднесена: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url))
    if kind == "won":
        return ("Честитки за доделената набавка",
                _client_html([
                    f"Договорниот орган ја додели набавката „{t}“ на вашата компанија. "
                    f"Ќе ви пишеме во порталот за следните чекори."
                ], client_url))
    if kind == "lost":
        return (f"Исход од набавката {tender_id}",
                _client_html([
                    f"Набавката „{t}“ е доделена на друг понудувач. Ако сакате, заедно можеме "
                    f"да ја прегледаме одлуката: пишете ни во порталот."
                ], client_url))
    if kind == "tender_cancelled":
        return (f"Постапката {tender_id} е поништена",
                _client_html([f"Договорниот орган ја поништи постапката „{t}“."], client_url))
    if kind == "cancelled_by_client":
        return (f"Клиентот го откажа барањето: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url))
    if kind == "invoice_requested":
        return (f"Клиентот бара фактура: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url))
    if kind == "paid_online":
        return (f"Платено со картичка: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url))
    if kind == "win_detected":
        extra = _link(f"{SITE}/admin/wins", "Прегледај ги победите")
        return (f"Можна победа на клиент: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url, extra))
    if kind == "success_fee_notice":
        # States no amount: the amount and details are in the portal.
        return ("Известување за надоместот за успех",
                _client_html([
                    f"Ви честитаме за доделената набавка „{t}“. Согласно условите, надоместот "
                    f"за успех ќе биде наплатен најрано седум дена од оваа порака. Износот и "
                    f"деталите се во порталот. Ако имате забелешка, одговорете ни во тој рок."
                ], client_url))
    if kind == "payment_alert":
        reason = str(ctx.get("extra") or "").split(":", 1)[0]
        text = PAYMENT_ALERT_TEXT.get(reason, "Уплата со картичка што бара проверка.")
        return (f"Проверка на уплата: {company} — {tender_id}",
                _admin_html(admin_rows(), admin_url, f"<p>{_e(text)}</p>"))
    if kind == "cancelled_by_admin":
        return ("Барањето за понуда е откажано",
                _client_html([
                    f"Барањето за понудата за „{t}“ е откажано. Деталите се во порталот."
                ], client_url))
    raise ValueError(f"unknown notification kind: {kind}")


def render_message_email(ctx: dict) -> tuple[str, str, str]:
    """(to, subject, html) for a new message. Client copies never carry the body."""
    job_id = ctx.get("job_id")
    tender_id = ctx.get("tender_id")
    title = ctx.get("tender_title") or tender_id
    if ctx.get("sender_role") == "admin":
        url = f"{SITE}/portal/bid/{job_id}" if job_id else f"{SITE}/portal/messages"
        about = f" за „{_e(title)}“" if job_id and title else ""
        html_body = _client_html([f"Имате нова порака{about}."], url, "Прочитајте ја пораката")
        return (ctx.get("client_email") or "", "Нова порака од тимот на НабавкиДата", html_body)

    company = ctx.get("company_name") or ctx.get("client_email") or ""
    subject = f"Порака од {company}" + (f" — {tender_id}" if job_id and tender_id else "")
    url = f"{SITE}/admin/bids/{job_id}" if job_id else f"{SITE}/admin/bids"
    body = _e(ctx.get("body")).replace("\r\n", "\n").replace("\n", "<br>")
    rows = [("Клиент", company), ("Е-пошта", ctx.get("client_email"))]
    if job_id:
        rows.append(("Тендер", f"{tender_id or ''} — {title or ''}"))
    table = "".join(
        f"<tr><td style='padding:4px 10px;color:#6b7280'>{_e(k)}</td>"
        f"<td style='padding:4px 10px'>{_e(v or '-')}</td></tr>" for k, v in rows
    )
    html_body = (f"{_WRAP_OPEN}<table style='font-size:14px'>{table}</table>"
                 f"<blockquote style='border-left:3px solid #d1d5db;margin:12px 0;padding:4px 12px'>"
                 f"{body}</blockquote>{_link(url, 'Одговори')}</div>")
    return (ADMIN_EMAIL, subject, html_body)


# ---------------------------------------------------------------------------
# Senders (never raise)
# ---------------------------------------------------------------------------
async def _record_failure(job_id: str, key: str) -> None:
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bid_job_events (job_id, kind, event, actor_role, detail) "
                "VALUES ($1,'audit','notify_failed','system',$2::jsonb)",
                _as_uuid(job_id), json.dumps({"key": key}),
            )
    except Exception:
        logger.exception("could not record notify failure: job=%s key=%s", job_id, key)


async def notify(job_id: str, kind: str, extra: Optional[str] = None) -> bool:
    """extra: caller discriminator (payment_alert: part of the dedupe key and the
    email text; success_fee_notice: the win id, part of the dedupe key)."""
    if kind not in KINDS:
        return False
    claimed = None
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            ctx = await load_context(conn, str(job_id))
            if ctx is None:
                return False
            if extra is not None:
                ctx["extra"] = extra
            key = notification_key(kind, ctx.get("reopen_count") or 0,
                                   ctx.get("publish_count") or 0, notification_extra(kind, ctx))
            if not await claim_notification(conn, str(job_id), key):
                return False
            claimed = key
        subject, html_body = render_email(kind, ctx)
        to = ADMIN_EMAIL if KINDS[kind] == "admin" else ctx.get("client_email")
        if not to:
            if kind in RETRYABLE_KINDS:
                await release_notification(str(job_id), key)
            return False
        ok = await postmark_service.send_email(
            to=to, subject=subject, html_content=html_body,
            tag=f"bid-job-{kind}", reply_to=REPLY_TO,
        )
        if ok is False:
            # The claim row stays (no automated retry loop); record the failure so
            # the admin event log shows it and someone can follow up by hand.
            logger.warning("bid-job email not sent: job=%s kind=%s key=%s", job_id, kind, key)
            await _record_failure(str(job_id), key)
            if kind in RETRYABLE_KINDS:
                await release_notification(str(job_id), key)
            return False
        return True
    except Exception:
        logger.exception("bid-job notify failed: job=%s kind=%s", job_id, kind)
        if claimed is not None and kind in RETRYABLE_KINDS:
            await release_notification(str(job_id), claimed)
        return False


async def notify_message(message_id: str) -> bool:
    """Email only on the 'no unread' -> 'unread' transition of a thread."""
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            ctx = await load_message_context(conn, str(message_id))
        if ctx is None or ctx.get("earlier_unread", 0) != 0:
            return False
        to, subject, html_body = render_message_email(ctx)
        if not to:
            return False
        ok = await postmark_service.send_email(
            to=to, subject=subject, html_content=html_body,
            tag="bid-message", reply_to=REPLY_TO,
        )
        if ok is False:
            logger.warning("bid message email not sent: message=%s to_role=%s", message_id,
                           "client" if ctx.get("sender_role") == "admin" else "admin")
            if ctx.get("job_id"):
                await _record_failure(ctx["job_id"], f"message:{message_id}")
            return False
        return True
    except Exception:
        logger.exception("bid message notify failed: message=%s", message_id)
        return False
