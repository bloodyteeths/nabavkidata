"""
Referral Program API Endpoints for nabavkidata.com
Users earn 20% recurring commission when referred users subscribe to paid plans.
Balance is tracked internally; admin pays out manually via bank transfer.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, text
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import secrets
import logging
import os

from database import get_db
from models import User
from api.auth import get_current_active_user

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://www.nabavkidata.com")

# ============================================================================
# SCHEMAS
# ============================================================================

class ReferralCodeResponse(BaseModel):
    code: str
    referral_url: str

class ReferralStats(BaseModel):
    total_referrals: int = 0
    active_referrals: int = 0
    total_earned_cents: int = 0
    total_paid_out_cents: int = 0
    pending_balance_cents: int = 0
    currency: str = "EUR"

class EarningItem(BaseModel):
    earning_id: str
    referred_email: str
    amount_cents: int
    currency: str
    created_at: str

class EarningsResponse(BaseModel):
    earnings: list
    total: int

class PayoutRequest(BaseModel):
    bank_name: str = Field(..., min_length=1, max_length=255)
    account_holder: str = Field(..., min_length=1, max_length=255)
    iban: str = Field(..., min_length=10, max_length=50)

class PayoutItem(BaseModel):
    payout_id: str
    user_email: str
    amount_cents: int
    currency: str
    status: str
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    iban: Optional[str] = None
    requested_at: str

class AdminPayoutAction(BaseModel):
    admin_notes: Optional[str] = None


# ============================================================================
# USER ENDPOINTS
# ============================================================================

router = APIRouter(
    prefix="/referrals",
    tags=["Referrals"]
)


def mask_email(email: str) -> str:
    """Mask email for privacy: zl***@gmail.com"""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


@router.get("/my-code", response_model=ReferralCodeResponse)
async def get_my_referral_code(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get or create the current user's referral code and URL."""
    user_id = str(current_user.user_id)

    # Check if code already exists
    result = await db.execute(
        text("SELECT code FROM referral_codes WHERE user_id = :uid"),
        {"uid": user_id}
    )
    row = result.fetchone()

    if row:
        code = row[0]
    else:
        # Generate unique 8-char code
        for _ in range(10):
            code = secrets.token_urlsafe(6)[:8]
            existing = await db.execute(
                text("SELECT 1 FROM referral_codes WHERE code = :code"),
                {"code": code}
            )
            if not existing.fetchone():
                break
        else:
            raise HTTPException(status_code=500, detail="Could not generate unique code")

        await db.execute(
            text("INSERT INTO referral_codes (user_id, code) VALUES (:uid, :code)"),
            {"uid": user_id, "code": code}
        )
        await db.commit()

    return ReferralCodeResponse(
        code=code,
        referral_url=f"{FRONTEND_URL}/?ref={code}"
    )


@router.get("/stats", response_model=ReferralStats)
async def get_referral_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get referral statistics for the current user."""
    user_id = str(current_user.user_id)

    # Total referrals
    total_result = await db.execute(
        text("SELECT COUNT(*) FROM referral_conversions WHERE referrer_id = :uid"),
        {"uid": user_id}
    )
    total_referrals = total_result.scalar() or 0

    # Active referrals
    active_result = await db.execute(
        text("SELECT COUNT(*) FROM referral_conversions WHERE referrer_id = :uid AND status = 'active'"),
        {"uid": user_id}
    )
    active_referrals = active_result.scalar() or 0

    # Total earned
    earned_result = await db.execute(
        text("SELECT COALESCE(SUM(amount_cents), 0) FROM referral_earnings WHERE referrer_id = :uid"),
        {"uid": user_id}
    )
    total_earned_cents = earned_result.scalar() or 0

    # Total paid out
    paid_result = await db.execute(
        text("SELECT COALESCE(SUM(amount_cents), 0) FROM referral_payouts WHERE user_id = :uid AND status = 'completed'"),
        {"uid": user_id}
    )
    total_paid_out_cents = paid_result.scalar() or 0

    # Pending payout requests (already submitted but not yet paid)
    pending_requests_result = await db.execute(
        text("SELECT COALESCE(SUM(amount_cents), 0) FROM referral_payouts WHERE user_id = :uid AND status IN ('pending', 'approved')"),
        {"uid": user_id}
    )
    pending_requests_cents = pending_requests_result.scalar() or 0

    pending_balance_cents = total_earned_cents - total_paid_out_cents - pending_requests_cents

    return ReferralStats(
        total_referrals=total_referrals,
        active_referrals=active_referrals,
        total_earned_cents=total_earned_cents,
        total_paid_out_cents=total_paid_out_cents,
        pending_balance_cents=max(0, pending_balance_cents),
        currency="EUR"
    )


@router.get("/earnings")
async def get_referral_earnings(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of referral earnings."""
    user_id = str(current_user.user_id)

    # Total count
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM referral_earnings WHERE referrer_id = :uid"),
        {"uid": user_id}
    )
    total = count_result.scalar() or 0

    # Earnings with referred user email
    result = await db.execute(
        text("""
            SELECT e.earning_id, u.email, e.amount_cents, e.currency, e.created_at
            FROM referral_earnings e
            JOIN users u ON u.user_id = e.referred_user_id
            WHERE e.referrer_id = :uid
            ORDER BY e.created_at DESC
            LIMIT :lim OFFSET :off
        """),
        {"uid": user_id, "lim": limit, "off": skip}
    )
    rows = result.fetchall()

    earnings = [
        {
            "earning_id": str(row[0]),
            "referred_email": mask_email(row[1]),
            "amount_cents": row[2],
            "currency": row[3],
            "created_at": row[4].isoformat() if row[4] else None
        }
        for row in rows
    ]

    return {"earnings": earnings, "total": total}


@router.post("/request-payout")
async def request_payout(
    data: PayoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Request a payout of referral earnings. Minimum 5 EUR."""
    user_id = str(current_user.user_id)

    # Check for existing pending payout
    existing = await db.execute(
        text("SELECT 1 FROM referral_payouts WHERE user_id = :uid AND status IN ('pending', 'approved')"),
        {"uid": user_id}
    )
    if existing.fetchone():
        raise HTTPException(
            status_code=400,
            detail="Веќе имате активно барање за исплата. Почекајте да се обработи."
        )

    # Calculate available balance
    earned_result = await db.execute(
        text("SELECT COALESCE(SUM(amount_cents), 0) FROM referral_earnings WHERE referrer_id = :uid"),
        {"uid": user_id}
    )
    total_earned = earned_result.scalar() or 0

    paid_result = await db.execute(
        text("SELECT COALESCE(SUM(amount_cents), 0) FROM referral_payouts WHERE user_id = :uid AND status IN ('completed', 'pending', 'approved')"),
        {"uid": user_id}
    )
    total_paid = paid_result.scalar() or 0

    available = total_earned - total_paid

    if available < 500:  # Minimum 5 EUR
        raise HTTPException(
            status_code=400,
            detail="Минимален износ за исплата е 5 EUR."
        )

    # Create payout request
    await db.execute(
        text("""
            INSERT INTO referral_payouts (user_id, amount_cents, currency, status, bank_name, account_holder, iban)
            VALUES (:uid, :amount, 'EUR', 'pending', :bank, :holder, :iban)
        """),
        {
            "uid": user_id,
            "amount": available,
            "bank": data.bank_name,
            "holder": data.account_holder,
            "iban": data.iban
        }
    )
    await db.commit()

    logger.info(f"Payout request created: {available} cents EUR for user {user_id}")

    return {"message": "Барањето за исплата е испратено. Ќе ве известиме кога ќе биде обработено."}


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

admin_router = APIRouter(
    prefix="/admin/referrals",
    tags=["Admin - Referrals"]
)


@admin_router.get("/payouts")
async def admin_list_payouts(
    payout_status: Optional[str] = "pending",
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: list referral payout requests."""
    # Check admin role
    if not hasattr(current_user, 'role') or current_user.role not in ('admin', 'superadmin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    conditions = ""
    params = {"lim": limit, "off": skip}

    if payout_status and payout_status != "all":
        conditions = "WHERE p.status = :st"
        params["st"] = payout_status

    result = await db.execute(
        text(f"""
            SELECT p.payout_id, u.email, p.amount_cents, p.currency, p.status,
                   p.bank_name, p.account_holder, p.iban, p.requested_at, p.paid_at, p.admin_notes
            FROM referral_payouts p
            JOIN users u ON u.user_id = p.user_id
            {conditions}
            ORDER BY p.requested_at DESC
            LIMIT :lim OFFSET :off
        """),
        params
    )
    rows = result.fetchall()

    payouts = [
        {
            "payout_id": str(row[0]),
            "user_email": row[1],
            "amount_cents": row[2],
            "currency": row[3],
            "status": row[4],
            "bank_name": row[5],
            "account_holder": row[6],
            "iban": row[7],
            "requested_at": row[8].isoformat() if row[8] else None,
            "paid_at": row[9].isoformat() if row[9] else None,
            "admin_notes": row[10]
        }
        for row in rows
    ]

    return {"payouts": payouts}


@admin_router.post("/payouts/{payout_id}/complete")
async def admin_complete_payout(
    payout_id: str,
    data: AdminPayoutAction = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: mark a payout as completed (paid via bank transfer)."""
    if not hasattr(current_user, 'role') or current_user.role not in ('admin', 'superadmin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        text("SELECT status FROM referral_payouts WHERE payout_id = :pid"),
        {"pid": payout_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Payout not found")
    if row[0] == "completed":
        raise HTTPException(status_code=400, detail="Payout already completed")

    notes = data.admin_notes if data else None
    await db.execute(
        text("""
            UPDATE referral_payouts
            SET status = 'completed', paid_at = NOW(), admin_notes = :notes
            WHERE payout_id = :pid
        """),
        {"pid": payout_id, "notes": notes}
    )
    await db.commit()

    logger.info(f"Admin completed payout {payout_id}")
    return {"message": "Payout marked as completed"}


@admin_router.post("/payouts/{payout_id}/reject")
async def admin_reject_payout(
    payout_id: str,
    data: AdminPayoutAction,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: reject a payout request."""
    if not hasattr(current_user, 'role') or current_user.role not in ('admin', 'superadmin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        text("SELECT status FROM referral_payouts WHERE payout_id = :pid"),
        {"pid": payout_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Payout not found")

    await db.execute(
        text("""
            UPDATE referral_payouts
            SET status = 'rejected', admin_notes = :notes
            WHERE payout_id = :pid
        """),
        {"pid": payout_id, "notes": data.admin_notes}
    )
    await db.commit()

    logger.info(f"Admin rejected payout {payout_id}")
    return {"message": "Payout rejected"}
