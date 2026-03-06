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
    e: Optional[str] = Query(None, description="Email address"),
    t: Optional[str] = Query(None, description="Verification token"),
    email: Optional[str] = Query(None, description="Email address (legacy param)"),
    token: Optional[str] = Query(None, description="Verification token (legacy param)"),
    db: AsyncSession = Depends(get_db)
):
    """Handle unsubscribe via GET (for email link clicks)."""
    # Support both new (e/t) and legacy (email/token) param names
    resolved_email = e or email
    resolved_token = t or token

    if not resolved_email or not resolved_token:
        raise HTTPException(status_code=400, detail="Missing email or token parameter")

    if not verify_unsubscribe_token(resolved_email, resolved_token):
        raise HTTPException(status_code=400, detail="Invalid or expired unsubscribe link")

    await add_to_suppression_sql(db, resolved_email, "unsubscribed", "user_request")

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
# WELCOME SERIES OPEN TRACKING
# ============================================================================

async def _update_welcome_series_open(db: AsyncSession, email: str):
    """Update welcome_series opened_at columns when user opens a welcome email."""
    try:
        # Find user by email and their welcome_series progress
        result = await db.execute(
            text("""
                SELECT ws.id, ws.current_step
                FROM welcome_series ws
                JOIN users u ON u.user_id = ws.user_id
                WHERE LOWER(u.email) = :email
                LIMIT 1
            """),
            {"email": email}
        )
        row = result.fetchone()
        if not row:
            return

        ws_id, current_step = row[0], row[1]

        # Mark the most recently sent email as opened
        # current_step is the next to send, so current_step - 1 is the last sent
        step = max(1, current_step - 1) if current_step > 1 else 1
        col = f"email_{step}_opened_at"

        # Only update if the column exists and isn't already set
        await db.execute(
            text(f"""
                UPDATE welcome_series
                SET {col} = COALESCE({col}, NOW())
                WHERE id = :ws_id
            """),
            {"ws_id": ws_id}
        )
    except Exception as e:
        logger.debug(f"Welcome series open tracking failed (non-critical): {e}")


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
            # Also update welcome_series open tracking
            await _update_welcome_series_open(db, email)
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
            # Also update welcome_series open tracking (click implies open)
            await _update_welcome_series_open(db, email)
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
