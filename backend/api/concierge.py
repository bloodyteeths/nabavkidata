"""
Tender Q&A concierge API (15 Oct 2026).

The AI only answers basic factual questions about tenders and routes the user
to us. Logged-in users only; daily limit for free/prospect users, abuse cap for
clients/admins. Refusals and limits are returned as HTTP 200 so the frontend
never opens the paywall modal. Logic lives in services/concierge.py.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from api.auth import get_current_user
from db_pool import get_asyncpg_pool
from middleware.rbac import require_admin
from services import concierge as svc

router = APIRouter(prefix="/concierge", tags=["concierge"])


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = ""

    @field_validator("content", mode="before")
    @classmethod
    def _cut(cls, v):
        return str(v or "")[: svc.MAX_HISTORY_MSG_CHARS]


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=svc.MAX_QUESTION_CHARS)
    tender_id: Optional[str] = Field(None, max_length=100)
    history: list[HistoryItem] = Field(default_factory=list, max_length=50)
    page: Optional[Literal["chat", "tender"]] = None

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Прашањето е празно.")
        return v

    @field_validator("tender_id")
    @classmethod
    def _strip_tid(cls, v: Optional[str]) -> Optional[str]:
        # Free text here would reach the model context / order_url / log, so
        # only tender-id shapes pass (NNNNN/YYYY, OT-... imports).
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if svc.valid_tender_id(v) is None:
            raise ValueError("Невалиден број на тендер.")
        return v


@router.post("/ask")
async def ask(body: AskBody, user=Depends(get_current_user)):
    history = [h.model_dump() for h in body.history][-svc.MAX_HISTORY_MSGS:]
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        return await svc.ask(conn, user, body.question, body.tender_id, history)


@router.get("/status")
async def status(user=Depends(get_current_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        return await svc.status(conn, user)


@router.get("/admin/log")
async def admin_log(limit: int = Query(100, ge=1, le=500), admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id, c.user_id, u.email, c.tender_id, c.question, c.answer, c.refused,
                   c.reason, c.lang, c.created_at
            FROM concierge_log c LEFT JOIN users u ON u.user_id = c.user_id
            ORDER BY c.created_at DESC, c.id DESC
            LIMIT $1
            """,
            limit,
        )
    items = []
    for r in rows:
        created = r["created_at"]
        items.append({
            "id": r["id"],
            "user_id": str(r["user_id"]) if r["user_id"] is not None else None,
            "email": r["email"],
            "tender_id": r["tender_id"],
            "question": r["question"],
            "answer": r["answer"],
            "refused": r["refused"],
            "reason": r["reason"],
            "lang": r["lang"],
            "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
        })
    return {"items": items}
