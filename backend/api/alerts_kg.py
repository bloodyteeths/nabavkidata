"""
KG (Kyrgyzstan) Alerts API — Phase 2

Alert matching against kg.tenders schema. Uses latin_to_russian() bilingual search.

Note: for Phase 2 MVP, KG alerts are stored in the same `tender_alerts` table
as MK alerts, but with country='kg' marker in criteria.jsonb. Phase 3+ may
promote this to a separate kg_alerts table if needed.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import re

from db_pool import get_asyncpg_pool
from api.corruption import latin_to_russian

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/kg/alerts",
    tags=["KG Alerts"],
)


class KGAlertMatch(BaseModel):
    tender_id: str
    tender_number: Optional[str] = None
    title: Optional[str] = None
    buyer_name: Optional[str] = None
    amount_kgs: Optional[float] = None
    date_contest: Optional[datetime] = None
    matched_keyword: str


@router.get("/preview")
async def preview_kg_alert(
    keywords: str = Query(..., description="Comma-separated keywords (Latin or Cyrillic)"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Preview what tenders would match a given set of KG keywords.
    Used by ZA Invest to test alert setup before saving.

    Bilingual: Latin input auto-converted to Russian Cyrillic via latin_to_russian().
    """
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        raise HTTPException(status_code=400, detail="At least one keyword required")

    conditions = []
    params: list = []
    param_num = 0

    for kw in keyword_list:
        has_cyrillic = any("Ѐ" <= c <= "ӿ" for c in kw)
        if has_cyrillic:
            param_num += 1
            conditions.append(f"title ILIKE '%' || ${param_num} || '%'")
            params.append(kw)
        else:
            cyr = latin_to_russian(kw)
            param_num += 1
            conditions.append(f"(title ILIKE '%' || ${param_num} || '%'")
            params.append(kw)
            param_num += 1
            conditions[-1] += f" OR title ILIKE '%' || ${param_num} || '%')"
            params.append(cyr)

    where_kw = " OR ".join(conditions)

    sql = f"""
        SELECT tender_id, tender_number, title, buyer_name, amount_kgs,
               date_contest,
               (CASE {' '.join([f"WHEN title ILIKE '%%' || ${i+1} || '%%' THEN ${i+1}" for i in range(len(params))])}
                ELSE '' END) as matched_keyword
        FROM kg.tenders
        WHERE date_contest > NOW() AND ({where_kw})
        ORDER BY date_contest ASC NULLS LAST
        LIMIT {int(limit)}
    """

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return {
        "keywords_input": keyword_list,
        "keywords_expanded": [
            {"input": kw, "cyrillic": latin_to_russian(kw) if not any("Ѐ" <= c <= "ӿ" for c in kw) else kw}
            for kw in keyword_list
        ],
        "matches": [dict(r) for r in rows],
        "count": len(rows),
    }


@router.get("/latin-to-russian")
async def convert_latin_to_russian(text: str = Query(..., description="Latin text to transliterate")):
    """Utility: convert Latin input to Russian/Kyrgyz Cyrillic. Preview for ZA Invest UI."""
    return {"input": text, "output": latin_to_russian(text)}


# ============================================================
# Phase 4 — anonymous email subscriptions
# ============================================================
import secrets
import os

from services.postmark import postmark_service

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://nabavkidata.com")


class KGSubscribeRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Email address")
    keywords: List[str] = Field(..., min_length=1, max_length=20, description="Keywords to match (1-20)")


class KGSubscribeResponse(BaseModel):
    ok: bool
    message: str


def _sanitize_email(email: str) -> str:
    email = email.strip().lower()
    if not re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", email):
        raise HTTPException(status_code=400, detail="Некорректный email адрес")
    return email


def _sanitize_keywords(raw: List[str]) -> List[str]:
    cleaned: List[str] = []
    seen: set = set()
    for kw in raw:
        kw = kw.strip()
        if len(kw) < 2 or len(kw) > 100:
            continue
        low = kw.lower()
        if low in seen:
            continue
        seen.add(low)
        cleaned.append(kw)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Введите хотя бы одно ключевое слово (2+ символа)")
    return cleaned


@router.post("/subscribe", response_model=KGSubscribeResponse)
async def subscribe_kg_alerts(req: KGSubscribeRequest):
    """Create or update anonymous subscription. Sends email verification link."""
    email = _sanitize_email(req.email)
    keywords = _sanitize_keywords(req.keywords)

    verify_token = secrets.token_urlsafe(32)
    unsub_token = secrets.token_urlsafe(32)

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        # UPSERT — if email exists, reset verification token + keywords (user re-subscribing)
        await conn.execute(
            """
            INSERT INTO kg.alert_subscriptions
                (email, keywords, verify_token, unsubscribe_token, is_verified, updated_at)
            VALUES ($1, $2, $3, $4, FALSE, NOW())
            ON CONFLICT (email) DO UPDATE SET
                keywords = EXCLUDED.keywords,
                verify_token = EXCLUDED.verify_token,
                unsubscribe_token = EXCLUDED.unsubscribe_token,
                is_verified = FALSE,
                verified_at = NULL,
                unsubscribed_at = NULL,
                updated_at = NOW()
            """,
            email, keywords, verify_token, unsub_token,
        )

    verify_url = f"{PUBLIC_BASE_URL}/kg/alerts/verify?token={verify_token}"
    kw_list_html = "".join(f"<li>{k}</li>" for k in keywords)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">
      <h2>Подтвердите подписку на Zakupki.KG</h2>
      <p>Здравствуйте!</p>
      <p>Вы подписались на ежедневные уведомления о новых тендерах Кыргызстана
      по следующим ключевым словам:</p>
      <ul>{kw_list_html}</ul>
      <p>Чтобы активировать подписку, нажмите на кнопку:</p>
      <p style="margin:24px 0"><a href="{verify_url}"
        style="background:#2563eb;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px">
        Подтвердить подписку</a></p>
      <p style="color:#666;font-size:12px">Если вы не оформляли подписку, просто проигнорируйте это письмо.
      Ссылка на отписку будет в каждом уведомлении.</p>
      <p style="color:#666;font-size:12px">Zakupki.KG — независимый мониторинг тендеров Кыргызстана</p>
    </div>
    """
    text = (
        f"Здравствуйте! Вы подписались на уведомления Zakupki.KG.\n\n"
        f"Ключевые слова: {', '.join(keywords)}\n\n"
        f"Для подтверждения откройте ссылку:\n{verify_url}\n\n"
        f"Если вы не оформляли подписку, проигнорируйте письмо."
    )

    sent = await postmark_service.send_email(
        to=email,
        subject="Подтвердите подписку на Zakupki.KG",
        html_content=html,
        text_content=text,
        tag="kg-alert-verify",
    )

    if not sent:
        logger.error(f"Failed to send verification email to {email}")
        # Don't leak internal error; keep record so user can request resend
        return KGSubscribeResponse(
            ok=True,
            message="Подписка зарегистрирована, но письмо с подтверждением не удалось отправить. "
                    "Попробуйте позже или напишите на hello@facturino.mk.",
        )

    return KGSubscribeResponse(
        ok=True,
        message="Проверьте вашу почту — мы отправили письмо для подтверждения подписки.",
    )


@router.get("/verify")
async def verify_kg_subscription(token: str = Query(..., min_length=20)):
    """Verify subscription via magic-link token from confirmation email."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE kg.alert_subscriptions
            SET is_verified = TRUE, verified_at = NOW(), updated_at = NOW()
            WHERE verify_token = $1 AND is_verified = FALSE
            RETURNING email
            """,
            token,
        )
    if not row:
        return {"ok": False, "message": "Токен недействителен или уже использован."}
    return {"ok": True, "message": f"Подписка активирована для {row['email']}. Первое уведомление придёт в течение 24 часов."}


@router.get("/unsubscribe")
async def unsubscribe_kg_alerts(token: str = Query(..., min_length=20)):
    """One-click unsubscribe via token in each digest email."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE kg.alert_subscriptions
            SET unsubscribed_at = NOW(), updated_at = NOW()
            WHERE unsubscribe_token = $1 AND unsubscribed_at IS NULL
            RETURNING email
            """,
            token,
        )
    if not row:
        return {"ok": False, "message": "Ссылка недействительна или подписка уже отменена."}
    return {"ok": True, "message": f"Подписка для {row['email']} отменена. Больше уведомлений не будет."}
