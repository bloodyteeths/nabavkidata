"""
Referral Program API Endpoints for nabavkidata.com
Users earn 20% recurring commission when referred users subscribe to paid plans.
Payouts via Stripe Connect (Express accounts) or manual bank transfer as fallback.
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
import stripe

from database import get_db
from models import User
from api.auth import get_current_active_user

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://www.nabavkidata.com")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

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
    bank_name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_holder: Optional[str] = Field(None, min_length=1, max_length=255)
    iban: Optional[str] = Field(None, min_length=10, max_length=50)

class ConnectStatusResponse(BaseModel):
    connected: bool = False
    status: Optional[str] = None  # null, 'pending', 'active', 'restricted'
    charges_enabled: bool = False
    payouts_enabled: bool = False

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


@router.post("/connect/onboard")
async def start_connect_onboarding(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Start Stripe Connect Express onboarding. Creates account if needed, returns onboarding URL."""
    user_id = str(current_user.user_id)

    # Check if user already has a Connect account
    result = await db.execute(
        text("SELECT stripe_connect_id FROM users WHERE user_id = :uid"),
        {"uid": user_id}
    )
    row = result.fetchone()
    connect_id = row[0] if row else None

    if not connect_id:
        # Create new Express account
        try:
            account = stripe.Account.create(
                type="express",
                country="MK",
                email=current_user.email,
                capabilities={"transfers": {"requested": True}},
                tos_acceptance={"service_agreement": "recipient"},
                metadata={"user_id": user_id, "platform": "nabavkidata"},
            )
            connect_id = account.id
            await db.execute(
                text("UPDATE users SET stripe_connect_id = :cid, stripe_connect_status = 'pending' WHERE user_id = :uid"),
                {"cid": connect_id, "uid": user_id}
            )
            await db.commit()
            logger.info(f"Created Stripe Connect account {connect_id} for user {user_id}")
        except stripe.StripeError as e:
            logger.error(f"Failed to create Connect account: {e}")
            raise HTTPException(status_code=500, detail="Не можевме да креираме Stripe сметка. Обидете се повторно.")

    # Generate onboarding link
    try:
        account_link = stripe.AccountLink.create(
            account=connect_id,
            refresh_url=f"{FRONTEND_URL}/settings?connect=refresh",
            return_url=f"{FRONTEND_URL}/settings?connect=success",
            type="account_onboarding",
        )
        return {"url": account_link.url}
    except stripe.StripeError as e:
        logger.error(f"Failed to create account link: {e}")
        raise HTTPException(status_code=500, detail="Не можевме да генерираме линк за поврзување.")


@router.get("/connect/status", response_model=ConnectStatusResponse)
async def get_connect_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current Stripe Connect account status."""
    user_id = str(current_user.user_id)

    result = await db.execute(
        text("SELECT stripe_connect_id, stripe_connect_status FROM users WHERE user_id = :uid"),
        {"uid": user_id}
    )
    row = result.fetchone()

    if not row or not row[0]:
        return ConnectStatusResponse()

    connect_id, local_status = row[0], row[1]

    # Fetch fresh status from Stripe
    try:
        account = stripe.Account.retrieve(connect_id)
        charges_enabled = account.charges_enabled or False
        payouts_enabled = account.payouts_enabled or False

        # Determine status
        if charges_enabled and payouts_enabled:
            new_status = "active"
        elif account.requirements and account.requirements.currently_due:
            new_status = "restricted"
        else:
            new_status = "pending"

        # Update local cache if changed
        if new_status != local_status:
            await db.execute(
                text("UPDATE users SET stripe_connect_status = :st WHERE user_id = :uid"),
                {"st": new_status, "uid": user_id}
            )
            await db.commit()

        return ConnectStatusResponse(
            connected=True,
            status=new_status,
            charges_enabled=charges_enabled,
            payouts_enabled=payouts_enabled,
        )
    except stripe.StripeError as e:
        logger.error(f"Failed to retrieve Connect account {connect_id}: {e}")
        return ConnectStatusResponse(connected=True, status=local_status or "pending")


@router.post("/request-payout")
async def request_payout(
    data: PayoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Request a payout. Uses Stripe Connect transfer if connected, otherwise manual bank transfer."""
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

    # Check if user has active Stripe Connect
    connect_result = await db.execute(
        text("SELECT stripe_connect_id, stripe_connect_status FROM users WHERE user_id = :uid"),
        {"uid": user_id}
    )
    connect_row = connect_result.fetchone()
    connect_id = connect_row[0] if connect_row else None
    connect_status = connect_row[1] if connect_row else None

    if connect_id and connect_status == "active":
        # Stripe Connect transfer - instant payout
        try:
            transfer = stripe.Transfer.create(
                amount=available,
                currency="eur",
                destination=connect_id,
                description=f"Referral payout for {current_user.email}",
                metadata={"user_id": user_id, "type": "referral_payout"},
            )
            await db.execute(
                text("""
                    INSERT INTO referral_payouts
                        (user_id, amount_cents, currency, status, payout_method, stripe_transfer_id, paid_at)
                    VALUES (:uid, :amount, 'EUR', 'completed', 'stripe', :transfer_id, NOW())
                """),
                {"uid": user_id, "amount": available, "transfer_id": transfer.id}
            )
            await db.commit()
            logger.info(f"Stripe transfer {transfer.id}: {available} cents EUR to {connect_id} for user {user_id}")
            return {"message": "Исплатата е извршена на вашата Stripe сметка."}
        except stripe.StripeError as e:
            logger.error(f"Stripe transfer failed for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Трансферот не успеа: {str(e)}")
    else:
        # Manual bank transfer fallback
        if not data.bank_name or not data.account_holder or not data.iban:
            raise HTTPException(
                status_code=400,
                detail="Потребни се банкарски податоци (име, банка, IBAN) за мануелна исплата."
            )

        await db.execute(
            text("""
                INSERT INTO referral_payouts
                    (user_id, amount_cents, currency, status, bank_name, account_holder, iban, payout_method)
                VALUES (:uid, :amount, 'EUR', 'pending', :bank, :holder, :iban, 'manual')
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
        logger.info(f"Manual payout request: {available} cents EUR for user {user_id}")
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


@admin_router.get("/dashboard")
async def admin_referral_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin: get all referrers with their balances and stats."""
    if not hasattr(current_user, 'role') or current_user.role not in ('admin', 'superadmin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        text("""
            SELECT
                u.email,
                u.stripe_connect_status,
                COALESCE(e.total_earned, 0) AS total_earned_cents,
                COALESCE(p_completed.total_paid, 0) AS total_paid_out_cents,
                COALESCE(e.total_earned, 0) - COALESCE(p_all.total_claimed, 0) AS pending_balance_cents,
                COALESCE(c.active_count, 0) AS active_referrals,
                COALESCE(c.total_count, 0) AS total_referrals
            FROM referral_codes rc
            JOIN users u ON u.user_id = rc.user_id
            LEFT JOIN (
                SELECT referrer_id, SUM(amount_cents) AS total_earned
                FROM referral_earnings GROUP BY referrer_id
            ) e ON e.referrer_id = rc.user_id
            LEFT JOIN (
                SELECT user_id, SUM(amount_cents) AS total_paid
                FROM referral_payouts WHERE status = 'completed' GROUP BY user_id
            ) p_completed ON p_completed.user_id = rc.user_id
            LEFT JOIN (
                SELECT user_id, SUM(amount_cents) AS total_claimed
                FROM referral_payouts WHERE status IN ('completed', 'pending', 'approved') GROUP BY user_id
            ) p_all ON p_all.user_id = rc.user_id
            LEFT JOIN (
                SELECT referrer_id,
                       COUNT(*) AS total_count,
                       COUNT(*) FILTER (WHERE status = 'active') AS active_count
                FROM referral_conversions GROUP BY referrer_id
            ) c ON c.referrer_id = rc.user_id
            WHERE COALESCE(e.total_earned, 0) > 0 OR COALESCE(c.total_count, 0) > 0
            ORDER BY COALESCE(e.total_earned, 0) DESC
        """)
    )
    rows = result.fetchall()

    referrers = [
        {
            "email": row[0],
            "stripe_connect_status": row[1],
            "total_earned_cents": row[2],
            "total_paid_out_cents": row[3],
            "pending_balance_cents": max(0, row[4]),
            "active_referrals": row[5],
            "total_referrals": row[6],
        }
        for row in rows
    ]

    return {"referrers": referrers}
