"""
Outreach API Endpoints
Handles unsubscribe, webhooks, and admin operations
"""
import os
import hmac
import hashlib
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["outreach"])

UNSUBSCRIBE_SECRET = os.getenv('UNSUBSCRIBE_SECRET', 'nabavki-unsub-secret-2025')

# ============================================================================
# SCHEMAS
# ============================================================================

class UnsubscribeRequest(BaseModel):
    email: str
    token: str

class UnsubscribeResponse(BaseModel):
    success: bool
    message: str


# ============================================================================
# HELPERS
# ============================================================================

def verify_unsubscribe_token(email: str, token: str) -> bool:
    expected = hashlib.sha256(f"{email}:{UNSUBSCRIBE_SECRET}".encode()).hexdigest()[:32]
    return hmac.compare_digest(token, expected)


async def add_to_suppression_sql(db: AsyncSession, email: str, reason: str, source: str = "manual", notes: str = None):
    """Add email to suppression_list using raw SQL."""
    email = email.lower().strip()
    await db.execute(
        text("""
            INSERT INTO suppression_list (email, reason, source, notes, created_at)
            VALUES (:email, :reason, :source, :notes, NOW())
            ON CONFLICT (email) DO NOTHING
        """),
        {"email": email, "reason": reason, "source": source, "notes": notes}
    )
    # Also mark lead as bounced/unsubscribed in outreach_leads
    status_map = {"bounce": "bounced", "complaint": "unsubscribed", "unsubscribed": "unsubscribed"}
    new_status = status_map.get(reason, "unsubscribed")
    await db.execute(
        text("""
            UPDATE outreach_leads SET outreach_status = :status
            WHERE LOWER(email) = :email AND outreach_status NOT IN ('bounced', 'unsubscribed')
        """),
        {"status": new_status, "email": email}
    )
    await db.commit()


# ============================================================================
# UNSUBSCRIBE ENDPOINT (PUBLIC)
# ============================================================================

@router.get("/unsubscribe", response_model=UnsubscribeResponse)
async def unsubscribe_get(
    e: str = Query(..., description="Email address"),
    t: str = Query(..., description="Verification token"),
    db: AsyncSession = Depends(get_db)
):
    """Handle unsubscribe via GET (for email link clicks)."""
    if not verify_unsubscribe_token(e, t):
        raise HTTPException(status_code=400, detail="Invalid or expired unsubscribe link")

    await add_to_suppression_sql(db, e, "unsubscribed", "user_request")

    return UnsubscribeResponse(
        success=True,
        message="Успешно се одјавивте од маркетинг пораки. Нема да добивате повеќе е-пошта од нас."
    )


@router.post("/unsubscribe", response_model=UnsubscribeResponse)
async def unsubscribe_post(
    request: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Handle unsubscribe via POST."""
    if not verify_unsubscribe_token(request.email, request.token):
        raise HTTPException(status_code=400, detail="Invalid or expired unsubscribe link")

    await add_to_suppression_sql(db, request.email, "unsubscribed", "user_request")

    return UnsubscribeResponse(
        success=True,
        message="Successfully unsubscribed from marketing emails."
    )


# ============================================================================
# POSTMARK WEBHOOK (PUBLIC)
# ============================================================================

@router.post("/webhook/postmark")
async def postmark_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Postmark webhook events.
    Updates outreach_emails table with delivery/open/click/bounce status.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    record_type = data.get("RecordType", "")
    email = (data.get("Email") or data.get("Recipient") or "").lower().strip()

    logger.info(f"Postmark webhook: {record_type} for {email}")

    try:
        if record_type == "Bounce":
            bounce_type = data.get("Type", "")
            if bounce_type in ["HardBounce", "BadEmailAddress", "ManuallyDeactivated"]:
                await add_to_suppression_sql(db, email, "bounce", "postmark", f"Type: {bounce_type}")

            # Mark in outreach_emails
            await db.execute(
                text("""
                    UPDATE outreach_emails
                    SET bounced = true, bounce_reason = :reason
                    WHERE lead_id IN (SELECT lead_id FROM outreach_leads WHERE LOWER(email) = :email)
                      AND bounced = false
                """),
                {"email": email, "reason": bounce_type}
            )
            await db.commit()

        elif record_type == "SpamComplaint":
            await add_to_suppression_sql(db, email, "complaint", "postmark")

        elif record_type == "Open":
            await db.execute(
                text("""
                    UPDATE outreach_emails
                    SET opened_at = COALESCE(opened_at, NOW())
                    WHERE lead_id IN (SELECT lead_id FROM outreach_leads WHERE LOWER(email) = :email)
                      AND opened_at IS NULL
                """),
                {"email": email}
            )
            await db.commit()

        elif record_type == "Click":
            await db.execute(
                text("""
                    UPDATE outreach_emails
                    SET clicked_at = COALESCE(clicked_at, NOW()),
                        opened_at = COALESCE(opened_at, NOW())
                    WHERE lead_id IN (SELECT lead_id FROM outreach_leads WHERE LOWER(email) = :email)
                      AND clicked_at IS NULL
                """),
                {"email": email}
            )
            await db.commit()

        elif record_type == "Delivery":
            await db.execute(
                text("""
                    UPDATE outreach_emails
                    SET delivered_at = COALESCE(delivered_at, NOW())
                    WHERE lead_id IN (SELECT lead_id FROM outreach_leads WHERE LOWER(email) = :email)
                      AND delivered_at IS NULL
                """),
                {"email": email}
            )
            await db.commit()

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"status": "ok"}


# ============================================================================
# ADMIN STATS (PROTECTED)
# ============================================================================

@router.get("/admin/stats")
async def admin_get_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get outreach campaign statistics."""
    leads = await db.execute(
        text("""
            SELECT segment, outreach_status, COUNT(*) as count
            FROM outreach_leads
            GROUP BY segment, outreach_status
            ORDER BY segment, outreach_status
        """)
    )

    emails = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_sent,
                COUNT(CASE WHEN delivered_at IS NOT NULL THEN 1 END) as delivered,
                COUNT(CASE WHEN opened_at IS NOT NULL THEN 1 END) as opened,
                COUNT(CASE WHEN clicked_at IS NOT NULL THEN 1 END) as clicked,
                COUNT(CASE WHEN bounced THEN 1 END) as bounced,
                COUNT(CASE WHEN replied_at IS NOT NULL THEN 1 END) as replied
            FROM outreach_emails
        """)
    )

    suppressed = await db.execute(
        text("SELECT reason, COUNT(*) as count FROM suppression_list GROUP BY reason")
    )

    email_row = emails.fetchone()

    return {
        "leads": [{"segment": r.segment, "status": r.outreach_status, "count": r.count} for r in leads],
        "emails": {
            "total_sent": email_row.total_sent if email_row else 0,
            "delivered": email_row.delivered if email_row else 0,
            "opened": email_row.opened if email_row else 0,
            "clicked": email_row.clicked if email_row else 0,
            "bounced": email_row.bounced if email_row else 0,
            "replied": email_row.replied if email_row else 0,
        },
        "suppressions": [{"reason": r.reason, "count": r.count} for r in suppressed]
    }
