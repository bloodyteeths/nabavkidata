"""
Operator focus API (Phase 4, Oct 2026) — NabavkiData port of BidFinder's
focus / hot_signal / lead_watch / shortlist system.

The system builds the morning list and writes drafts; a person presses Send.
Nothing here emails a lead or client on its own: the only sends are
POST /drafts/{key}/send and POST /shortlists/{id}/send, each one an explicit
admin click that sends exactly one email, at most once per dedupe key
(unique index on ops_sent_emails + claim-then-send, rolled back on failure).

Public endpoints: /sent (signed one-click "Готово" from the 06:30 focus
email; GET only renders a confirm form because link scanners prefetch) and
/calendar/{token}.ics (admin-only feed, token is the credential).
"""
from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import secrets
import uuid
from datetime import date, datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from db_pool import get_asyncpg_pool
from middleware.rbac import require_admin
from services import client_shortlist, lead_watch, ops_copy, ops_focus
from services.postmark import POSTMARK_API_URL, POSTMARK_FROM_EMAIL, postmark_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["Ops focus"])

KEY_RE = re.compile(r"^[a-z0-9:_\-]{3,200}$")
GROUPS = ("clients", "sales", "money", "reminders")
OPS_FROM_NAME = "Атилла Танрикулу, НабавкиДата"

# --- SQL (module constants so the tests' fake connection can match them) ----
SQL_STATE = "SELECT status FROM focus_item_state WHERE key = $1"
SQL_SUPPRESSED = "SELECT 1 FROM suppression_list WHERE lower(email) = $1 LIMIT 1"
SQL_ADMIN_EMAIL = ("SELECT 1 FROM users WHERE lower(email) = $1 "
                   "AND lower(COALESCE(role,'user')) = 'admin' LIMIT 1")
SQL_CLAIM = ("INSERT INTO ops_sent_emails (dedupe_key, kind, to_email, subject, body_text, channel, sent_by) "
             "VALUES ($1, $2, $3, $4, $5, 'postmark', $6) ON CONFLICT DO NOTHING RETURNING id")
SQL_UNCLAIM = "DELETE FROM ops_sent_emails WHERE id = $1"
SQL_SET_MSGID = "UPDATE ops_sent_emails SET message_id = $2 WHERE id = $1"
SQL_MANUAL_SENT = ops_focus.SQL_MANUAL_SENT   # written by ops_focus.mark_done (link / sent_manually)
SQL_CAL_TOKEN = "SELECT calendar_token FROM users WHERE user_id = $1"
SQL_CAL_SET = ("UPDATE users SET calendar_token = COALESCE(calendar_token, $2) "
               "WHERE user_id = $1 RETURNING calendar_token")
SQL_CAL_OWNER = ("SELECT user_id FROM users WHERE calendar_token = $1 "
                 "AND lower(COALESCE(role,'user')) = 'admin'")
SQL_SHORTLIST = "SELECT id, user_id, week_start, status FROM client_shortlists WHERE id = $1"
SQL_WATCH_BY_EMAIL = "SELECT id FROM lead_watches WHERE email = $1"


# --- helpers -----------------------------------------------------------------
def _check_key(key: str) -> str:
    if not KEY_RE.match(key or ""):
        raise HTTPException(status_code=400, detail="Невалиден клуч.")
    return key


def is_internal_email(email: str) -> bool:
    e = (email or "").strip().lower()
    return any(e.endswith("@" + d) for d in ops_copy.INTERNAL_DOMAINS)


async def recipient_blocked(conn, email: str) -> Optional[str]:
    """Reason the address must never receive an ops email, or None."""
    e = (email or "").strip().lower()
    if not e or "@" not in e:
        return "invalid"
    if is_internal_email(e):
        return "internal"
    if await conn.fetchval(SQL_ADMIN_EMAIL, e):
        return "internal"
    if await conn.fetchval(SQL_SUPPRESSED, e):
        return "suppressed"
    return None


class SendUncertain(Exception):
    """The request may have reached Postmark (timeout / dropped connection after
    sending): the e-mail may or may not have gone out. The claim must be KEPT."""


async def send_one(to: str, subject: str, body_text: str, body_html: str, tag: str) -> Optional[str]:
    """POST exactly one email to Postmark. Returns the MessageID, or None when the
    message was definitely NOT sent (no token, connection refused, Postmark
    rejected it with an HTTP error). Raises SendUncertain when it may have been
    sent (read timeout, connection dropped after the request was written)."""
    headers = postmark_service._get_headers()
    if not headers.get("X-Postmark-Server-Token"):
        logger.error("ops send_one: POSTMARK_API_TOKEN not configured")
        return None
    cc = ops_copy.ADMIN_EMAIL
    payload = {
        "From": f'"{OPS_FROM_NAME}" <{POSTMARK_FROM_EMAIL}>',
        "To": to,
        "Cc": cc,
        "ReplyTo": os.getenv("OPS_REPLY_TO", ops_copy.ADMIN_EMAIL),
        "Subject": subject,
        "TextBody": body_text,
        "HtmlBody": body_html,
        "MessageStream": "outbound",
        "Tag": tag,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(POSTMARK_API_URL, headers=headers, json=payload)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.UnsupportedProtocol,
            httpx.LocalProtocolError) as e:
        logger.error("ops send_one: not sent to %s: %s", to, e)   # never left this host
        return None
    except Exception as e:  # noqa: BLE001 - read timeout, dropped connection, ...
        logger.error("ops send_one: outcome unknown for %s: %s", to, e)
        raise SendUncertain(str(e)) from e
    if r.status_code == 200:
        try:
            return (r.json() or {}).get("MessageID") or "unknown"
        except ValueError:
            return "unknown"   # accepted (200) but unparsable body: it was sent
    logger.error("ops send_one: Postmark %s %s", r.status_code, r.text[:300])
    return None


async def claim_and_send(conn, *, dedupe_key: str, kind: str, to: str, subject: str,
                         body_text: str, body_html: str, sent_by, tag: str) -> str:
    """Claim the dedupe key, send, roll the claim back on failure. Returns MessageID."""
    claim_id = await conn.fetchval(SQL_CLAIM, dedupe_key, kind, to, subject, body_text, sent_by)
    if claim_id is None:
        raise HTTPException(status_code=409, detail="Оваа порака е веќе испратена.")
    try:
        message_id = await send_one(to, subject, body_text, body_html, tag)
    except SendUncertain:
        # Keep the claim: a retry could deliver a duplicate to the client.
        await conn.execute(SQL_SET_MSGID, claim_id, "unknown")
        raise HTTPException(status_code=502, detail=(
            "Не е јасно дали Postmark ја испрати пораката (истек на време). Проверете во "
            "Postmark Activity пред повторно да испратите; ако не е испратена, испратете ја "
            "рачно и означете „Испратив рачно“."))
    if not message_id:
        await conn.execute(SQL_UNCLAIM, claim_id)
        raise HTTPException(status_code=502, detail="Postmark не ја прифати пораката. Обидете се повторно.")
    await conn.execute(SQL_SET_MSGID, claim_id, message_id)
    return message_id


def _counts(items: list[dict]) -> dict:
    by_group = {g: 0 for g in GROUPS}
    for it in items:
        g = it.get("group")
        if g in by_group:
            by_group[g] += 1
    return {"total": len(items), "by_group": by_group}


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang=\"mk\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{html.escape(title)}</title></head>"
        "<body style=\"font-family:Arial,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;color:#111\">"
        f"<h2>{html.escape(title)}</h2>{body}</body></html>",
        status_code=status_code,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
    )


# --- focus -------------------------------------------------------------------
@router.get("/focus", dependencies=[Depends(require_admin)])
async def get_focus(include_done: bool = Query(False)):
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        try:
            await lead_watch.sync_watches(conn, today)
        except Exception as e:  # noqa: BLE001
            logger.exception("sync_watches failed: %s", e)
        data = await ops_focus.build_focus(conn, today, include_done=include_done)
    data = dict(data)
    data["counts"] = _counts(data.get("items") or [])
    return data


class DoneBody(BaseModel):
    # True = "Испратив рачно": the draft went out from Gmail / the mail app. Same
    # effect as the signed link: a manual ops_sent_emails row + record_contact.
    sent_manually: bool = False


@router.post("/focus/{key}/done")
async def focus_done(key: str, body: Optional[DoneBody] = None, admin=Depends(require_admin)):
    _check_key(key)
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await ops_focus.mark_done(conn, key, today, "ui", admin.user_id,
                                  sent_manually=bool(body and body.sent_manually))
    return {"key": key, "status": "done"}


class SnoozeBody(BaseModel):
    days: int = Field(1, ge=1, le=30)


@router.post("/focus/{key}/snooze", dependencies=[Depends(require_admin)])
async def focus_snooze(key: str, body: SnoozeBody = SnoozeBody()):
    _check_key(key)
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        until = await ops_focus.snooze(conn, key, today, body.days)
    return {"key": key, "status": "snoozed", "snoozed_until": until.isoformat() if until else None}


@router.post("/focus/{key}/reopen", dependencies=[Depends(require_admin)])
async def focus_reopen(key: str):
    _check_key(key)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await ops_focus.reopen(conn, key)
    return {"key": key, "status": "open"}


# --- draft send (one email, one click, once per key) -------------------------
class DraftSendBody(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    body_text: str = Field(..., min_length=1, max_length=8000)
    force: bool = False


@router.post("/drafts/{key}/send")
async def send_draft(key: str, body: DraftSendBody, admin=Depends(require_admin)):
    _check_key(key)
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        item = await ops_focus.get_item(conn, key, today)
        if not item or not item.get("draft"):
            raise HTTPException(status_code=404, detail="Ставката или нацртот не постои.")
        if await conn.fetchval(SQL_STATE, key) == "done":
            raise HTTPException(status_code=409, detail="Ставката е веќе завршена.")
        # Recipient comes from the server-side draft only; the client cannot change it.
        to = (item["draft"].get("to") or "").strip().lower()
        blocked = await recipient_blocked(conn, to)
        if blocked:
            raise HTTPException(status_code=409, detail=f"Примачот е блокиран ({blocked}).")
        violations = ops_copy.check_draft_copy(body.subject + "\n" + body.body_text)
        if violations and not body.force:
            raise HTTPException(status_code=422, detail={"violations": violations})
        message_id = await claim_and_send(
            conn, dedupe_key=key, kind=item.get("kind") or "draft", to=to,
            subject=body.subject, body_text=body.body_text,
            body_html=ops_copy.render_html(body.body_text), sent_by=admin.user_id,
            tag=f"ops_{item.get('kind') or 'draft'}")
        await ops_focus.mark_done(conn, key, today, "send", admin.user_id, item=item)
    return {"key": key, "sent": True, "message_id": message_id, "to": to}


# --- lead watches --------------------------------------------------------------
class StopWatchBody(BaseModel):
    reason: Literal["replied", "not_interested"]


@router.post("/watches/{watch_id}/stop", dependencies=[Depends(require_admin)])
async def stop_watch(watch_id: uuid.UUID, body: StopWatchBody):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await lead_watch.stop_watch(conn, watch_id, body.reason)
    return {"watch_id": str(watch_id), "stopped": True, "reason": body.reason}


# --- signed one-click "Готово" from the focus email ----------------------------
@router.get("/sent", response_class=HTMLResponse)
async def sent_confirm(k: str = "", e: int = 0, sig: str = ""):
    """Renders a confirm form only. GET never changes state (link scanners prefetch)."""
    if not KEY_RE.match(k or "") or not ops_copy.verify_ops_sig(k, e, sig):
        return _page("Невалиден или истечен линк", "<p>Отворете го фокусот во админ панелот.</p>", 403)
    title = k
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            item = await ops_focus.get_item(conn, k, ops_copy.today_skopje())
        if item and item.get("title"):
            title = item["title"]
    except Exception as ex:  # noqa: BLE001
        logger.warning("ops /sent GET: item lookup failed: %s", ex)
    form = (
        f"<p>{html.escape(title)}</p>"
        "<form method=\"post\" action=\"/api/ops/sent\">"
        f"<input type=\"hidden\" name=\"k\" value=\"{html.escape(k)}\">"
        f"<input type=\"hidden\" name=\"e\" value=\"{int(e)}\">"
        f"<input type=\"hidden\" name=\"sig\" value=\"{html.escape(sig)}\">"
        "<button type=\"submit\" style=\"font-size:16px;padding:10px 18px\">Потврди: завршено</button>"
        "</form>"
    )
    return _page("Означи како завршено", form)


@router.post("/sent", response_class=HTMLResponse)
async def sent_commit(k: str = Form(""), e: int = Form(0), sig: str = Form("")):
    if not KEY_RE.match(k or "") or not ops_copy.verify_ops_sig(k, e, sig):
        return _page("Невалиден или истечен линк", "<p>Отворете го фокусот во админ панелот.</p>", 403)
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        already = await conn.fetchval(SQL_STATE, k) == "done"
        # mark_done claims the key atomically; only the claiming call records the
        # manual send (ops_sent_emails channel='manual') and its side effects.
        item = await ops_focus.mark_done(conn, k, today, "link")
    title = (item or {}).get("title") or k
    when = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    msg = "Веќе беше означено како завршено." if already else f"Означено како завршено ({when})."
    return _page("Готово", f"<p>{html.escape(title)}</p><p>{msg}</p>")


# --- admin calendar feed -------------------------------------------------------
def _ics_escape(s: str) -> str:
    s = str(s or "")
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return s.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _ics_fold(line: str) -> str:
    """RFC 5545 §3.1: fold lines longer than 75 octets (UTF-8 safe)."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > 75:
            out.append(cur)
            cur, size = " " + ch, 1 + n
        else:
            cur += ch
            size += n
    out.append(cur)
    return "\r\n".join(out)


def build_focus_ics(items: list[dict], now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NabavkiData//Ops focus//MK",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:НабавкиДата фокус"]
    for it in items:
        try:
            d = date.fromisoformat(str(it.get("date"))[:10])
        except ValueError:
            continue
        uid = f"{hashlib.sha1(it['key'].encode()).hexdigest()[:24]}-{d.isoformat()}@nabavkidata.com"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{date.fromordinal(d.toordinal() + 1).strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_escape(it.get('title'))}",
            f"DESCRIPTION:{_ics_escape(it.get('detail'))}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"


@router.get("/calendar-url")
async def calendar_url(admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        token = await conn.fetchval(SQL_CAL_TOKEN, admin.user_id)
        if not token:
            token = await conn.fetchval(SQL_CAL_SET, admin.user_id, secrets.token_urlsafe(32))
    https_url = f"{ops_copy.PUBLIC_API}/api/ops/calendar/{token}.ics"
    return {"https_url": https_url, "webcal_url": re.sub(r"^https?://", "webcal://", https_url)}


@router.get("/calendar/{token}.ics")
async def calendar_feed(token: str):
    if not token or len(token) < 16 or len(token) > 128:
        raise HTTPException(status_code=404, detail="Не е пронајдено.")
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        if not await conn.fetchval(SQL_CAL_OWNER, token):
            raise HTTPException(status_code=404, detail="Не е пронајдено.")
        data = await ops_focus.build_focus(conn, today)
    body = build_focus_ics(data.get("items") or [], datetime.now(timezone.utc))
    return Response(content=body.encode("utf-8"), media_type="text/calendar; charset=utf-8",
                    headers={"Cache-Control": "no-cache"})


# --- weekly client shortlists --------------------------------------------------
def _week_of(week: Optional[str], today: date) -> date:
    if not week:
        return ops_copy.week_start(today)
    try:
        return ops_copy.week_start(date.fromisoformat(week))
    except ValueError:
        raise HTTPException(status_code=400, detail="Невалидна недела (YYYY-MM-DD).")


async def _load_shortlist(conn, shortlist_id: uuid.UUID, today: date) -> dict:
    sl = await client_shortlist.get_shortlist(conn, shortlist_id, today)
    if not sl:
        raise HTTPException(status_code=404, detail="Шортлистата не постои.")
    return sl


@router.get("/shortlists", dependencies=[Depends(require_admin)])
async def list_shortlists(week: Optional[str] = Query(None)):
    today = ops_copy.today_skopje()
    ws = _week_of(week, today)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await client_shortlist.list_week(conn, ws, today)
    return {"week_start": ws.isoformat(), "shortlists": rows}


class BuildBody(BaseModel):
    user_id: Optional[uuid.UUID] = None


@router.post("/shortlists/build", dependencies=[Depends(require_admin)])
async def build_shortlists(body: BuildBody = BuildBody()):
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        return await client_shortlist.build_week(conn, today, user_id=body.user_id)


class ShortlistUpdateBody(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    intro_text: Optional[str] = Field(None, min_length=1, max_length=4000)
    picked: list[str] = Field(default_factory=list, max_length=client_shortlist.MAX_PICK)
    notes: Optional[dict[str, str]] = None


@router.put("/shortlists/{shortlist_id}", dependencies=[Depends(require_admin)])
async def update_shortlist(shortlist_id: uuid.UUID, body: ShortlistUpdateBody):
    notes = body.notes or {}
    for tid, note in notes.items():
        if note is not None and len(note) > 300:
            raise HTTPException(status_code=422, detail=f"Белешката за {tid} е подолга од 300 знаци.")
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_SHORTLIST, shortlist_id)
        if not row:
            raise HTTPException(status_code=404, detail="Шортлистата не постои.")
        if row["status"] != "draft":
            raise HTTPException(status_code=409, detail="Шортлистата веќе не е нацрт.")
        try:
            await client_shortlist.update_shortlist(conn, shortlist_id, today, body.subject,
                                                    body.intro_text, body.picked, notes)
        except LookupError:
            raise HTTPException(status_code=404, detail="Шортлистата не постои.")
        except client_shortlist.ShortlistStateError:
            raise HTTPException(status_code=409, detail="Шортлистата веќе не е нацрт.")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return await _load_shortlist(conn, shortlist_id, today)


@router.get("/shortlists/{shortlist_id}/preview", dependencies=[Depends(require_admin)])
async def preview_shortlist(shortlist_id: uuid.UUID):
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        sl = await _load_shortlist(conn, shortlist_id, today)
    mail = client_shortlist.render_shortlist_email(sl, sl.get("items") or [])
    mail = dict(mail)
    mail["violations"] = ops_copy.check_draft_copy(mail["subject"] + "\n" + mail["body_text"])
    return mail


class ShortlistSendBody(BaseModel):
    force: bool = False


@router.post("/shortlists/{shortlist_id}/send")
async def send_shortlist(shortlist_id: uuid.UUID, body: ShortlistSendBody = ShortlistSendBody(),
                         admin=Depends(require_admin)):
    today = ops_copy.today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        sl = await _load_shortlist(conn, shortlist_id, today)
        if sl.get("status") != "draft":
            raise HTTPException(status_code=409, detail="Шортлистата веќе не е нацрт.")
        picked = [i for i in (sl.get("items") or []) if i.get("picked")]
        if not (client_shortlist.MIN_PICK <= len(picked) <= client_shortlist.MAX_PICK):
            raise HTTPException(status_code=422, detail=(
                f"Изберете {client_shortlist.MIN_PICK}–{client_shortlist.MAX_PICK} тендери."))
        if any(not i.get("open") for i in picked):
            raise HTTPException(status_code=422, detail="Избран е затворен тендер.")
        mail = client_shortlist.render_shortlist_email(sl, sl.get("items") or [])
        to = (mail.get("to") or sl.get("email") or "").strip().lower()
        blocked = await recipient_blocked(conn, to)
        if blocked:
            raise HTTPException(status_code=409, detail=f"Примачот е блокиран ({blocked}).")
        violations = ops_copy.check_draft_copy(mail["subject"] + "\n" + mail["body_text"])
        if violations and not body.force:
            raise HTTPException(status_code=422, detail={"violations": violations})
        message_id = await claim_and_send(
            conn, dedupe_key=f"shortlist:{shortlist_id}", kind="shortlist", to=to,
            subject=mail["subject"], body_text=mail["body_text"], body_html=mail["body_html"],
            sent_by=admin.user_id, tag="ops_shortlist")
        await client_shortlist.mark_sent(conn, shortlist_id, message_id, admin.user_id)
        watch_id = await conn.fetchval(SQL_WATCH_BY_EMAIL, to)
        if watch_id:
            await lead_watch.record_shown(conn, watch_id, [i["tender_id"] for i in picked])
        # Leads for this address -> contacted, go-back cadence restarts from this send.
        await ops_focus.record_contact(conn, to)
        await ops_focus.mark_done(conn, f"touch:{sl['user_id']}:{ops_copy.iso_week(today)}",
                                  today, "send", admin.user_id)
    return {"id": str(shortlist_id), "sent": True, "message_id": message_id, "to": to}


@router.post("/shortlists/{shortlist_id}/skip", dependencies=[Depends(require_admin)])
async def skip_shortlist(shortlist_id: uuid.UUID):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_SHORTLIST, shortlist_id)
        if not row:
            raise HTTPException(status_code=404, detail="Шортлистата не постои.")
        if row["status"] != "draft":
            raise HTTPException(status_code=409, detail="Шортлистата веќе не е нацрт.")
        await client_shortlist.skip(conn, shortlist_id)
    return {"id": str(shortlist_id), "status": "skipped"}
