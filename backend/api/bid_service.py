"""
Done-for-you bid-writing service API (14 Oct 2026).

NabavkiData is no longer a self-serve SaaS: it is the engine behind a service
where we write the bid for the client (prep fee per bid + 5% success fee,
paid by invoice). Ported from BidFinder (tenderuk/backend/api/bid_service.py),
see tenderuk/docs/PLATFORM_REPURPOSE_PLAYBOOK.md for the model.

- Public POST /bid-service/qualify            — the one front door (/usluga form,
                                                 tender-page card, paywall CTA);
                                                 auto-logs-in a brand-new identity
- Admin  GET  /bid-service/admin/leads        — triage list
- Admin  PATCH /bid-service/admin/leads/{id}  — status / notes
"""
from __future__ import annotations

import html
import ipaddress
import json
import logging
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from db_pool import get_asyncpg_pool
from middleware.rbac import require_admin
from api.auth import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    hash_token,
)
from api.bid_jobs import tender_open_for_begin, today_skopje
from services.postmark import postmark_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bid-service", tags=["Bid service"])

ADMIN_EMAIL = "atillatkulu@gmail.com"
# Every new lead alerts both the owner and the shared inbox: two October leads
# sat unanswered for days behind a single failed send.
ALERT_EMAILS = (ADMIN_EMAIL, "hello@nabavkidata.com")
SITE = "https://nabavkidata.com"
PREP_FEE_MKD = 30000
SUCCESS_FEE_PCT = 5

# Per-target-email cap (checked against bid_service_leads) so the public form
# cannot be used to flood one inbox with confirmation emails.
EMAIL_DAILY_LIMIT = 3

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TENDER_NO_RE = re.compile(r"\b\d{3,6}/\d{4}\b")
_KEYWORD_SPLIT_RE = re.compile(r"[,;\n\r]+|\s+или\s+|\s+и\s+", re.IGNORECASE)

# In-memory per-IP limiter for the public form (anti-spam).
_qualify_hits: dict[str, list[float]] = {}
_MAX_TRACKED_IPS = 10000


def _rate_limit_ok(ip: str, limit: int = 8, window: float = 3600.0) -> bool:
    now = time.time()
    if len(_qualify_hits) > _MAX_TRACKED_IPS:
        # Sweep expired keys so the dict cannot grow without bound.
        for k in [k for k, v in _qualify_hits.items() if not v or now - v[-1] >= window]:
            _qualify_hits.pop(k, None)
    hits = [t for t in _qualify_hits.get(ip, []) if now - t < window]
    if len(hits) >= limit:
        _qualify_hits[ip] = hits
        return False
    hits.append(now)
    _qualify_hits[ip] = hits
    return True


def _valid_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _client_ip(request: Request) -> str:
    """Real client IP behind nginx.

    nginx sets X-Real-IP from $remote_addr and APPENDS the real address to any
    client-supplied X-Forwarded-For, so only X-Real-IP or the right-most XFF
    entry can be trusted. The left-most XFF value is attacker-controlled.
    """
    ip = _valid_ip(request.headers.get("x-real-ip"))
    if not ip:
        xff = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        ip = _valid_ip(xff[-1]) if xff else None
    if not ip and request.client:
        ip = _valid_ip(request.client.host) or request.client.host
    return ip or "unknown"


def _extract_keywords(text: str) -> list[str]:
    """Split the free-text 'what do you want to win' into alert keywords.

    The alert matcher does a substring test per keyword, so one long phrase
    would never match anything. Tender numbers are dropped (kept on the lead).
    """
    out: list[str] = []
    seen: set[str] = set()
    for part in _KEYWORD_SPLIT_RE.split(text or ""):
        kw = part.strip(" .:-\t\"'„“”").strip()
        if len(kw) <= 3 or _TENDER_NO_RE.search(kw):
            continue
        kw = kw[:60].strip()
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(kw)
        if len(out) >= 10:
            break
    return out


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _token_user_id(request: Request) -> Optional[str]:
    """user_id from a valid Bearer access token, if the caller sent one."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer ") or not SECRET_KEY:
        return None
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def _esc(s: Optional[str]) -> str:
    return html.escape(s or "")


class QualifyRequest(BaseModel):
    company: str = Field(..., min_length=2, max_length=500)
    email: str = Field(..., max_length=255)
    lead_person: str = Field("", max_length=500)
    phone: str = Field("", max_length=100)
    wants_to_win: str = Field("", max_length=1000)
    sector: str = Field("", max_length=120)
    tender_id: Optional[str] = Field(None, max_length=100)
    source: str = Field("usluga", max_length=50)


async def _award_history(conn, company: str) -> dict:
    """What our award data already says about this company (best effort).

    Macedonia has no free company-registry API, so award history is how we
    profile a lead: wins, bids, typical value, who they sell to.
    """
    name = company.strip()
    # Wildcards are escaped below; require real characters so '%%%%' or '____'
    # cannot turn this into a full-table aggregate.
    if len(re.sub(r"[%_\\\s]", "", name)) < 4:
        return {}
    pattern = f"%{_like_escape(name)}%"
    async with conn.transaction():
        # Leading-% ILIKE is a sequential scan: bound it on this public path.
        await conn.execute("SET LOCAL statement_timeout = '2s'")
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)                                   AS bids,
                   COUNT(*) FILTER (WHERE b.is_winner)        AS wins,
                   MAX(t.publication_date)                    AS last_bid,
                   ROUND(AVG(b.bid_amount_mkd) FILTER (WHERE b.is_winner)) AS avg_win_mkd
            FROM tender_bidders b
            JOIN tenders t ON t.tender_id = b.tender_id
            WHERE b.company_name ILIKE $1 ESCAPE '\\'
            """,
            pattern,
        )
        if not row or not row["bids"]:
            return {"bids": 0, "wins": 0}
        buyers = await conn.fetch(
            """
            SELECT t.procuring_entity, COUNT(*) AS n
            FROM tender_bidders b
            JOIN tenders t ON t.tender_id = b.tender_id
            WHERE b.company_name ILIKE $1 ESCAPE '\\' AND b.is_winner
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
            """,
            pattern,
        )
    return {
        "bids": row["bids"],
        "wins": row["wins"],
        "last_bid": row["last_bid"].isoformat() if row["last_bid"] else None,
        "avg_win_mkd": float(row["avg_win_mkd"]) if row["avg_win_mkd"] is not None else None,
        "top_buyers": [{"buyer": b["procuring_entity"], "wins": b["n"]} for b in buyers],
    }


async def _send_admin_alert(subject: str, rows: list[tuple[str, str]]) -> None:
    body = "".join(
        f"<tr><td style='padding:6px 10px;color:#6b7280'>{_esc(k)}</td>"
        f"<td style='padding:6px 10px'>{_esc(v)}</td></tr>"
        for k, v in rows
    )
    html_content = (f"<table style='font-family:sans-serif;font-size:14px'>{body}</table>"
                    f"<p><a href='{SITE}/admin/leads'>Отвори ги барањата</a></p>")
    sent = 0
    for addr in ALERT_EMAILS:
        try:
            await postmark_service.send_email(
                to=addr,
                subject=subject,
                html_content=html_content,
                tag="bid-service-lead",
            )
            sent += 1
        except Exception:
            logger.exception("bid-service admin alert to %s failed: %s", addr, subject)
    if not sent:
        # Nobody was told. Make it loud in the log so it is findable later.
        logger.error("bid-service lead alert reached NOBODY: %s", subject)


async def _send_confirmation(email: str, first_name: str, tender_title: Optional[str],
                             set_password_url: Optional[str]) -> None:
    """Instant confirmation to the lead: a person is on it. No pricing (outreach rule)."""
    about = (f"<p>Го добивме вашето барање за тендерот <strong>{_esc(tender_title)}</strong>.</p>"
             if tender_title else "<p>Го добивме вашето барање.</p>")
    pw = (f"<p>Ви отворивме профил на НабавкиДата. Веќе сте најавени на овој уред. "
          f"За најава од други уреди <a href='{_esc(set_password_url)}'>поставете лозинка</a>. "
          f"Линкот важи една недела.</p>"
          f"<p style='color:#6b7280;font-size:13px'>Ако не сте го испратиле ова барање, "
          f"слободно игнорирајте ја пораката.</p>"
          if set_password_url else "")
    greeting = f"Почитуван/а {_esc(first_name)}," if first_name else "Почитувани,"
    html_body = f"""
    <div style="font-family:sans-serif;font-size:15px;line-height:1.6;color:#1a1a1a;max-width:560px">
      <p>{greeting}</p>
      {about}
      <p>Во рок од <strong>еден работен ден</strong> ќе ви одговориме со искрена проценка
      дали вреди да се понуди и што е потребно.</p>
      {pw}
      <p>Поздрав,<br>Тимот на НабавкиДата<br>Фактурино ДООЕЛ</p>
    </div>"""
    try:
        await postmark_service.send_email(
            to=email,
            subject="Го добивме вашето барање",
            html_content=html_body,
            tag="qualify-confirm",
            reply_to="hello@nabavkidata.com",
        )
    except Exception:
        logger.exception("qualify confirmation failed for %s", email)


@router.post("/qualify")
async def qualify(body: QualifyRequest, request: Request, background: BackgroundTasks):
    """The single front door. Public, no auth.

    Security model (BidFinder §4.2): tokens + a user_sessions row are returned
    ONLY when this request created a brand-new account (case-insensitive email
    pre-check plus INSERT ... ON CONFLICT DO NOTHING RETURNING). An existing
    email never gets tokens (auth=None), so the form cannot be used to take
    over an account. The new account stays email_verified=FALSE until the
    emailed set-password link is used (services.auth_service.reset_password);
    it is a prospect, so it has no paid perks until a prep fee is paid, and
    alert emails go only to verified clients. token.sub is the id returned by
    our own INSERT, never anything from the request.
    """
    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        raise HTTPException(status_code=429, detail="Премногу барања. Обидете се подоцна.")

    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Внесете валидна е-пошта.")
    company = body.company.strip()
    wants = (body.wants_to_win or "").strip()
    sector = (body.sector or "").strip()

    # A request tied to a specific tender already says what they want to win.
    # A general enquiry does not, so both fields are required there: two Google
    # leads arrived in October with every one of these blank and could not be
    # answered at all.
    if not body.tender_id:
        if len(wants) < 10:
            raise HTTPException(
                status_code=400,
                detail="Напишете што сакате да освоите, со неколку збора.",
            )
        if len(sector) < 2:
            raise HTTPException(status_code=400, detail="Изберете ја вашата дејност.")

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        recent = await conn.fetchval(
            "SELECT COUNT(*) FROM bid_service_leads "
            "WHERE email = $1 AND created_at > NOW() - INTERVAL '1 day'",
            email,
        )
        if (recent or 0) >= EMAIL_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Веќе го примивме вашето барање. Ќе ви одговориме во рок од еден работен ден.",
            )

        tender = None
        if body.tender_id:
            tender = await conn.fetchrow(
                "SELECT tender_id, title, procuring_entity, closing_date, estimated_value_mkd, "
                "status FROM tenders WHERE tender_id = $1",
                body.tender_id,
            )

        try:
            history = await _award_history(conn, company)
        except Exception:
            logger.exception("award history lookup failed for %s", company)
            history = {}

        set_password_url = None
        created = False
        auth = None
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT user_id, account_type FROM users WHERE LOWER(email) = $1", email
            )
            uid = existing["user_id"] if existing else None
            if not existing:
                reset_token = secrets.token_urlsafe(32)
                # ON CONFLICT: two concurrent submits of the same new address must not 500.
                uid = await conn.fetchval(
                    """
                    INSERT INTO users (email, password_hash, full_name, company_name,
                                       subscription_tier, account_type, email_verified,
                                       password_reset_token, password_reset_token_expires_at)
                    VALUES ($1,'',$2,$3,'free','prospect',FALSE,$4,$5)
                    ON CONFLICT (email) DO NOTHING
                    RETURNING user_id
                    """,
                    email, body.lead_person or None, company, reset_token,
                    datetime.utcnow() + timedelta(days=7),
                )
                if uid is None:
                    existing = await conn.fetchrow(
                        "SELECT user_id, account_type FROM users WHERE LOWER(email) = $1", email
                    )
                    uid = existing["user_id"] if existing else None
                else:
                    created = True
                    set_password_url = f"{SITE}/auth/reset-password?token={reset_token}"
                    # Auto-login for the brand-new identity only (BidFinder §4.2).
                    # Access token ONLY, never a refresh token: whoever typed the
                    # address may not own the mailbox, and /auth/refresh rebinds the
                    # active session without any session check, so a 30-day refresh
                    # token would let them take over the account after the real
                    # owner sets a password and logs in. The access token is tied
                    # to this session row and dies when the owner logs in
                    # (single-session enforcement) or after 7 days at the latest.
                    access = create_access_token({"sub": str(uid)})
                    ua = request.headers.get("user-agent", "") or ""
                    fp = request.headers.get("x-device-fingerprint", "") or ""
                    await conn.execute(
                        "INSERT INTO user_sessions (session_id, user_id, token_hash, device_info, "
                        "ip_address, is_active, created_at, last_activity) "
                        "VALUES (gen_random_uuid(), $1, $2, $3, $4::inet, TRUE, NOW(), NOW())",
                        uid, hash_token(access), f"{ua[:200]}|fp:{fp[:100]}|qualify",
                        _valid_ip(ip),
                    )
                    auth = {"access_token": access, "refresh_token": None,
                            "token_type": "bearer"}
                    keywords = _extract_keywords(wants)
                    if keywords:
                        # Prospects get in-app matches (portal hook); alert
                        # EMAILS need client perks + a verified address.
                        await conn.execute(
                            """INSERT INTO tender_alerts (user_id, name, alert_type, criteria)
                               VALUES ($1, $2, 'keyword', $3::jsonb)""",
                            uid, f"Следење — {company}"[:255], json.dumps({"keywords": keywords}),
                        )

            insert_args = (
                email, company, body.lead_person or None, body.phone or None,
                wants or None, tender["tender_id"] if tender else None,
                body.source, uid, json.dumps(history),
            )
            try:
                lead_id = await conn.fetchval(
                    """
                    INSERT INTO bid_service_leads
                        (email, company_name, lead_person, phone, wants_to_win, tender_id, source,
                         user_id, history, sector)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)
                    RETURNING id
                    """,
                    *insert_args, sector or None,
                )
            except asyncpg.UndefinedColumnError:
                # add_bid_service_lead_sector.sql has not been applied yet: keep
                # taking leads rather than dropping them, and carry the sector in
                # the free-text field so nothing the visitor typed is lost.
                logger.warning("bid_service_leads.sector missing; run add_bid_service_lead_sector.sql")
                lead_id = await conn.fetchval(
                    """
                    INSERT INTO bid_service_leads
                        (email, company_name, lead_person, phone, wants_to_win, tender_id, source,
                         user_id, history)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
                    RETURNING id
                    """,
                    *insert_args[:4],
                    f"[{sector}] {wants}".strip() if sector else (wants or None),
                    *insert_args[5:],
                )

            # Only the signed-in owner of an existing account may change it; an
            # anonymous submit just records the lead against that user.
            if (existing and existing["account_type"] == "free"
                    and _token_user_id(request) == str(existing["user_id"])):
                await conn.execute(
                    "UPDATE users SET account_type='prospect', company_name=COALESCE(company_name,$2), "
                    "updated_at=NOW() WHERE user_id=$1",
                    existing["user_id"], company,
                )

    hist_line = (f"{history.get('wins', 0)} победи / {history.get('bids', 0)} понуди"
                 if history else "нема податоци")
    background.add_task(
        _send_admin_alert,
        f"БАРАЊЕ за понуда: {company} ({email}) — одговори денес",
        [
            ("Компанија", company),
            ("Контакт", f"{body.lead_person or '-'} <{email}> {body.phone or ''}"),
            ("Тендер", f"{tender['tender_id']} — {tender['title']}" if tender else "-"),
            ("Рок", str(tender["closing_date"]) if tender and tender["closing_date"] else "-"),
            ("Дејност", sector or "-"),
            ("Што сака да добие", wants or "-"),
            ("Историја (наши податоци)", hist_line),
            ("Извор", body.source),
            ("Постоечки корисник", "не (нов профил, автоматски најавен, неверификуван)" if created else "да"),
        ],
    )
    background.add_task(
        _send_confirmation,
        email,
        (body.lead_person or "").strip().split(" ")[0],
        tender["title"] if tender else None,
        set_password_url,
    )

    message = "Го добивме вашето барање. Ќе ви одговориме во рок од еден работен ден."
    nxt = None
    if created:
        message += " Ви испративме е-пошта со линк за поставување лозинка."
        nxt = ("tender"
               if tender and tender_open_for_begin(tender["status"], tender["closing_date"],
                                                   today_skopje())
               else "portal")
    return {
        "lead_id": str(lead_id),
        "message": message,
        # Tokens only for a brand-new identity created by this request.
        "auth": auth if created else None,
        "next": nxt,
        "tender_id": tender["tender_id"] if tender else None,
    }


@router.get("/terms")
async def service_terms():
    """Public numbers the site shows. Never used in outreach emails."""
    return {"prep_fee_mkd": PREP_FEE_MKD, "success_fee_pct": SUCCESS_FEE_PCT}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@router.get("/admin/leads", dependencies=[Depends(require_admin)])
async def list_leads(status: Optional[str] = Query(None), limit: int = Query(100, le=500)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.*, t.title AS tender_title, t.closing_date
            FROM bid_service_leads l
            LEFT JOIN tenders t ON t.tender_id = l.tender_id
            WHERE ($1::text IS NULL OR l.status = $1)
            ORDER BY (l.status = 'new') DESC, l.created_at DESC
            LIMIT $2
            """,
            status, limit,
        )
    out = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["user_id"] = str(d["user_id"]) if d["user_id"] else None
        if isinstance(d.get("history"), str):
            d["history"] = json.loads(d["history"])
        out.append(d)
    return {"leads": out}


class LeadUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(new|contacted|qualified|client|rejected)$")
    admin_notes: Optional[str] = Field(None, max_length=5000)


@router.patch("/admin/leads/{lead_id}", dependencies=[Depends(require_admin)])
async def update_lead(lead_id: uuid.UUID, body: LeadUpdate):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE bid_service_leads
            SET status = COALESCE($2, status),
                admin_notes = COALESCE($3, admin_notes),
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, status, user_id
            """,
            lead_id, body.status, body.admin_notes,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Lead not found")
        # Invoice paid / client signed: promote the linked account.
        if body.status == "client" and row["user_id"]:
            await conn.execute(
                "UPDATE users SET account_type='managed_client', updated_at=NOW() WHERE user_id=$1",
                row["user_id"],
            )
    out = {"id": str(row["id"]), "status": row["status"]}
    if body.status == "client" and not row["user_id"]:
        out["warning"] = "Барањето нема поврзан профил: ниту еден корисник не е унапреден во клиент."
    return out
