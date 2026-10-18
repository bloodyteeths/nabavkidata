"""
Upwork OAuth 2.0 connection for Фактурино's own client account (Oct 2026).

Used only to hire freelancers for our tender teams (Upwork API key
"Fakturino Tender Team Hiring"). One admin connects once; tokens are kept
in system_config.

- Admin  GET /api/upwork/oauth/start     -> redirect to Upwork authorize page
- Public GET /api/upwork/oauth/callback  -> Upwork redirects here with ?code&state
- Admin  GET /api/upwork/oauth/status    -> connected or not (no secrets returned)

Env: UPWORK_CLIENT_ID, UPWORK_CLIENT_SECRET (from upwork.com/developer/keys).
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import secrets
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import urlencode

from db_pool import get_asyncpg_pool
from middleware.rbac import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upwork/oauth", tags=["Upwork"])

AUTHORIZE_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
CALLBACK_URL = os.getenv(
    "UPWORK_CALLBACK_URL", "https://api.nabavkidata.com/api/upwork/oauth/callback"
)
TOKENS_KEY = "upwork_oauth_tokens"
STATE_TTL_S = 15 * 60


def _client_id() -> str:
    return os.getenv("UPWORK_CLIENT_ID", "")


def _client_secret() -> str:
    return os.getenv("UPWORK_CLIENT_SECRET", "")


def _state_secret() -> bytes:
    return (os.getenv("SECRET_KEY") or "").encode()


def make_state(now: Optional[int] = None) -> str:
    ts = str(now or int(time.time()))
    nonce = secrets.token_urlsafe(12)
    sig = hmac.new(_state_secret(), f"{ts}.{nonce}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{ts}.{nonce}.{sig}"


def verify_state(state: str, now: Optional[int] = None) -> bool:
    try:
        ts, nonce, sig = state.split(".", 2)
        age = (now or int(time.time())) - int(ts)
    except (ValueError, AttributeError):
        return False
    if not _state_secret() or age < 0 or age > STATE_TTL_S:
        return False
    want = hmac.new(_state_secret(), f"{ts}.{nonce}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(want, sig)


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        status_code=status,
        content=(
            "<!doctype html><html lang='mk'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title></head>"
            "<body style='font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:48px auto;"
            "padding:0 16px;line-height:1.6;color:#1e293b'>"
            f"<h1 style='font-size:20px'>{html.escape(title)}</h1>{body}"
            "<p style='color:#64748b;font-size:13px'>НабавкиДата · Фактурино ДООЕЛ · "
            "<a href='https://nabavkidata.com'>nabavkidata.com</a></p></body></html>"
        ),
    )


@router.get("/start", dependencies=[Depends(require_admin)])
async def start():
    if not _client_id():
        return _page("Upwork не е конфигуриран",
                     "<p>Недостасува UPWORK_CLIENT_ID на серверот.</p>", status=503)
    params = {
        "response_type": "code",
        "client_id": _client_id(),
        "redirect_uri": CALLBACK_URL,
        "state": make_state(),
    }
    return RedirectResponse(f"{AUTHORIZE_URL}?{urlencode(params)}", status_code=302)


@router.get("/callback")
async def callback(code: Optional[str] = Query(None), state: Optional[str] = Query(None),
                   error: Optional[str] = Query(None)):
    if error:
        return _page("Поврзувањето со Upwork е откажано",
                     f"<p>Upwork врати: {html.escape(error)}</p>", status=400)
    if not code:
        # Opened directly (e.g. by a reviewer): explain instead of a bare 404.
        return _page(
            "Upwork OAuth callback",
            "<p>This is the OAuth 2.0 return address for Fakturino DOOEL's internal hiring "
            "tool (Upwork API key \"Fakturino Tender Team Hiring\"). Upwork redirects here "
            "after our account administrator authorizes the connection; it is not used by "
            "the public.</p>"
            "<p>Ова е адресата на која Upwork се враќа по одобрувањето на поврзувањето "
            "на нашата интерна алатка за ангажирање.</p>",
        )
    if not state or not verify_state(state):
        return _page("Неважечко барање", "<p>Барањето е истечено или не е валидно. "
                     "Започнете го поврзувањето повторно.</p>", status=400)
    if not (_client_id() and _client_secret()):
        return _page("Upwork не е конфигуриран",
                     "<p>Недостасуваат UPWORK_CLIENT_ID / UPWORK_CLIENT_SECRET.</p>", status=503)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CALLBACK_URL,
                "client_id": _client_id(),
                "client_secret": _client_secret(),
            })
    except httpx.HTTPError:
        logger.exception("upwork token exchange failed")
        return _page("Грешка", "<p>Upwork не одговори. Обидете се повторно.</p>", status=502)
    if r.status_code != 200:
        logger.error("upwork token exchange %s: %s", r.status_code, r.text[:300])
        return _page("Грешка", "<p>Upwork го одби поврзувањето.</p>", status=502)

    tokens = r.json()
    tokens["obtained_at"] = int(time.time())
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO system_config (config_key, config_value, updated_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (config_key) DO UPDATE
               SET config_value = EXCLUDED.config_value, updated_at = NOW()""",
            TOKENS_KEY, json.dumps(tokens),
        )
    return _page("Upwork е поврзан", "<p>Поврзувањето е успешно. Можете да го затворите прозорецот.</p>")


@router.get("/status", dependencies=[Depends(require_admin)])
async def status():
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT config_value, updated_at FROM system_config WHERE config_key = $1", TOKENS_KEY
        )
    configured = bool(_client_id() and _client_secret())
    if not row:
        return {"configured": configured, "connected": False}
    data = json.loads(row["config_value"] or "{}")
    expires = (data.get("obtained_at") or 0) + int(data.get("expires_in") or 0)
    return {
        "configured": configured,
        "connected": bool(data.get("access_token")),
        "access_expires_at": expires or None,
        "has_refresh_token": bool(data.get("refresh_token")),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
