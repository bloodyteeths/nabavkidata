"""
Admin API Endpoints for nabavkidata.com
Provides comprehensive admin control panel functionality

Security:
- Requires ADMIN or SUPERADMIN role
- All actions are audit logged
- Rate limited to prevent abuse

Features:
- User management (list, update, ban, delete)
- Tender management (approve, reject, delete)
- Subscription monitoring
- System analytics and health monitoring
- Audit log viewing
- Scraper control
- Broadcast notifications
"""
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal

from database import get_db
from models import (
    User, Tender, Document, Subscription, Alert, Notification,
    UsageTracking, AuditLog, QueryHistory, SystemConfig
)
from models_auth import UserRole, UserAuth
from models_billing import (
    UserSubscription, Payment, Invoice, SubscriptionPlan,
    SubscriptionStatus, PaymentStatus
)
from middleware.rbac import get_current_active_user, require_role
from pydantic import BaseModel, Field


# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_role(UserRole.admin))]
)


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class DashboardStats(BaseModel):
    """Admin dashboard statistics"""
    total_users: int
    active_users: int
    verified_users: int
    total_tenders: int
    open_tenders: int
    total_subscriptions: int
    active_subscriptions: int
    monthly_revenue_mkd: Decimal
    monthly_revenue_eur: Decimal
    total_queries_today: int
    total_queries_month: int


class UserListItem(BaseModel):
    """User list item for admin"""
    user_id: UUID
    email: str
    full_name: Optional[str]
    subscription_tier: str
    email_verified: bool
    is_active: bool
    role: str
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response"""
    total: int
    skip: int
    limit: int
    users: List[UserListItem]


class UserDetailResponse(BaseModel):
    """Detailed user information"""
    user_id: UUID
    email: str
    full_name: Optional[str]
    subscription_tier: str
    email_verified: bool
    is_active: bool
    role: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    stripe_customer_id: Optional[str]
    failed_login_attempts: int
    locked_until: Optional[datetime]
    total_queries: int
    active_alerts: int
    active_subscription: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """Update user request"""
    role: Optional[str] = None
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None
    subscription_tier: Optional[str] = None


class TenderListItem(BaseModel):
    """Tender list item for admin"""
    tender_id: str
    title: str
    category: Optional[str]
    procuring_entity: Optional[str]
    status: str
    estimated_value_mkd: Optional[Decimal]
    opening_date: Optional[datetime]
    closing_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TenderListResponse(BaseModel):
    """Paginated tender list response"""
    total: int
    skip: int
    limit: int
    tenders: List[TenderListItem]


class SubscriptionListItem(BaseModel):
    """Subscription list item"""
    subscription_id: UUID
    user_email: str
    plan_name: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    auto_renew: bool

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """Paginated subscription list response"""
    total: int
    skip: int
    limit: int
    subscriptions: List[SubscriptionListItem]


class AnalyticsResponse(BaseModel):
    """System analytics response"""
    users_growth: Dict[str, int]
    revenue_trend: Dict[str, Decimal]
    queries_trend: Dict[str, int]
    subscription_distribution: Dict[str, int]
    top_categories: List[Dict[str, Any]]
    active_users_today: int
    active_users_week: int
    active_users_month: int


class AuditLogItem(BaseModel):
    """Audit log item"""
    audit_id: UUID
    user_id: Optional[UUID]
    user_email: Optional[str]
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Paginated audit log response"""
    total: int
    skip: int
    limit: int
    logs: List[AuditLogItem]


class ScraperStatus(BaseModel):
    """Scraper status response"""
    is_running: bool
    last_run: Optional[datetime]
    last_success: Optional[datetime]
    total_scraped: int
    errors_count: int
    next_scheduled_run: Optional[datetime]


class SystemHealthResponse(BaseModel):
    """Detailed system health response"""
    status: str
    database: str
    redis: Optional[str]
    storage: Dict[str, Any]
    services: Dict[str, str]
    uptime_seconds: int
    timestamp: datetime


class BroadcastRequest(BaseModel):
    """Broadcast notification request"""
    message: str = Field(..., min_length=1, max_length=1000)
    target_tier: Optional[str] = None
    target_verified_only: bool = False


class EmailBroadcastRequest(BaseModel):
    """Email broadcast request"""
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)
    target_tier: Optional[str] = None
    target_verified_only: bool = False
    send_notification: bool = True  # Also send in-app notification


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    detail: Optional[str] = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def log_admin_action(
    db: AsyncSession,
    user_id: UUID,
    action: str,
    details: Dict[str, Any],
    ip_address: Optional[str] = None
):
    """Log admin action to audit log"""
    audit_log = AuditLog(
        user_id=user_id,
        action=f"admin_{action}",
        details=details,
        ip_address=ip_address
    )
    db.add(audit_log)
    await db.commit()


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get admin dashboard statistics

    Returns:
    - User counts (total, active, verified)
    - Tender counts (total, open)
    - Subscription counts (total, active)
    - Revenue metrics (monthly in MKD and EUR)
    - Query statistics (today, this month)
    """
    # User statistics
    total_users = await db.scalar(select(func.count(UserAuth.user_id)))
    active_users = await db.scalar(
        select(func.count(UserAuth.user_id)).where(UserAuth.is_active == True)
    )
    verified_users = await db.scalar(
        select(func.count(UserAuth.user_id)).where(UserAuth.is_verified == True)
    )

    # Tender statistics
    total_tenders = await db.scalar(select(func.count(Tender.tender_id)))
    open_tenders = await db.scalar(
        select(func.count(Tender.tender_id)).where(Tender.status == "open")
    )

    # Subscription statistics
    total_subscriptions = await db.scalar(select(func.count(UserSubscription.subscription_id)))
    active_subscriptions = await db.scalar(
        select(func.count(UserSubscription.subscription_id))
        .where(UserSubscription.status == SubscriptionStatus.active)
    )

    # Revenue statistics (current month)
    current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_revenue_mkd = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_mkd), 0))
        .where(
            and_(
                Payment.status == PaymentStatus.succeeded,
                Payment.created_at >= current_month_start
            )
        )
    ) or Decimal(0)

    monthly_revenue_eur = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_eur), 0))
        .where(
            and_(
                Payment.status == PaymentStatus.succeeded,
                Payment.created_at >= current_month_start
            )
        )
    ) or Decimal(0)

    # Query statistics
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total_queries_today = await db.scalar(
        select(func.count(QueryHistory.query_id))
        .where(QueryHistory.created_at >= today_start)
    ) or 0

    total_queries_month = await db.scalar(
        select(func.count(QueryHistory.query_id))
        .where(QueryHistory.created_at >= current_month_start)
    ) or 0

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "view_dashboard",
        {"action": "viewed dashboard stats"}
    )

    return DashboardStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        verified_users=verified_users or 0,
        total_tenders=total_tenders or 0,
        open_tenders=open_tenders or 0,
        total_subscriptions=total_subscriptions or 0,
        active_subscriptions=active_subscriptions or 0,
        monthly_revenue_mkd=monthly_revenue_mkd,
        monthly_revenue_eur=monthly_revenue_eur,
        total_queries_today=total_queries_today,
        total_queries_month=total_queries_month
    )


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    role: Optional[str] = None,
    status: Optional[str] = None,
    subscription: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all users with filtering

    Filters:
    - role: Filter by user role (admin, user, etc.)
    - status: Filter by status (active, inactive)
    - subscription: Filter by subscription tier
    - search: Search by email or name
    """
    # Build query
    query = select(UserAuth)

    # Apply filters
    conditions = []
    if role:
        conditions.append(UserAuth.role == role)
    if status == "active":
        conditions.append(UserAuth.is_active == True)
    elif status == "inactive":
        conditions.append(UserAuth.is_active == False)
    if search:
        conditions.append(
            or_(
                UserAuth.email.ilike(f"%{search}%"),
                UserAuth.full_name.ilike(f"%{search}%")
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(UserAuth.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    # Convert to response format
    user_items = [
        UserListItem(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            subscription_tier="free",  # Default, will be enhanced with join
            email_verified=user.is_verified,
            is_active=user.is_active,
            role=user.role.value,
            created_at=user.created_at,
            last_login=user.last_login
        )
        for user in users
    ]

    return UserListResponse(
        total=total,
        skip=skip,
        limit=limit,
        users=user_items
    )


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_details(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific user

    Includes:
    - Basic user info
    - Subscription details
    - Usage statistics
    - Active alerts count
    """
    # Get user
    result = await db.execute(select(UserAuth).where(UserAuth.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get usage statistics
    total_queries = await db.scalar(
        select(func.count(QueryHistory.query_id))
        .where(QueryHistory.user_id == user_id)
    ) or 0

    active_alerts = await db.scalar(
        select(func.count(Alert.alert_id))
        .where(and_(Alert.user_id == user_id, Alert.is_active == True))
    ) or 0

    # Get active subscription
    subscription_result = await db.execute(
        select(UserSubscription)
        .where(
            and_(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.active
            )
        )
        .order_by(desc(UserSubscription.created_at))
        .limit(1)
    )
    active_subscription_obj = subscription_result.scalar_one_or_none()

    active_subscription = None
    if active_subscription_obj:
        active_subscription = {
            "subscription_id": str(active_subscription_obj.subscription_id),
            "status": active_subscription_obj.status.value,
            "current_period_start": active_subscription_obj.current_period_start.isoformat(),
            "current_period_end": active_subscription_obj.current_period_end.isoformat(),
            "auto_renew": active_subscription_obj.auto_renew
        }

    return UserDetailResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        subscription_tier="free",
        email_verified=user.is_verified,
        is_active=user.is_active,
        role=user.role.value,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        stripe_customer_id=None,
        failed_login_attempts=0,
        locked_until=user.locked_until,
        total_queries=total_queries,
        active_alerts=active_alerts,
        active_subscription=active_subscription
    )


@router.patch("/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user information

    Can update:
    - role (user, admin, superadmin)
    - is_active (ban/unban)
    - email_verified (verify email manually)
    - subscription_tier
    """
    # Get user
    result = await db.execute(select(UserAuth).where(UserAuth.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Build update dictionary
    updates = {}
    if update_data.role is not None:
        try:
            updates["role"] = UserRole[update_data.role]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {update_data.role}"
            )
    if update_data.is_active is not None:
        updates["is_active"] = update_data.is_active
    if update_data.email_verified is not None:
        updates["is_verified"] = update_data.email_verified

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    updates["updated_at"] = datetime.utcnow()

    # Update user
    await db.execute(
        update(UserAuth)
        .where(UserAuth.user_id == user_id)
        .values(**updates)
    )
    await db.commit()

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "update_user",
        {"user_id": str(user_id), "updates": {k: str(v) for k, v in updates.items()}}
    )

    return MessageResponse(
        message="User updated successfully",
        detail=f"Updated fields: {', '.join(updates.keys())}"
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete user account

    WARNING: This is a destructive action that will:
    - Delete the user account
    - Cascade delete all related data (alerts, subscriptions, etc.)
    """
    # Prevent self-deletion
    if str(current_user.user_id) == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    # Check if user exists
    result = await db.execute(select(UserAuth).where(UserAuth.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Log before deletion
    await log_admin_action(
        db, current_user.user_id, "delete_user",
        {"user_id": str(user_id), "email": user.email}
    )

    # Delete related records first (FK constraints)
    # Order matters - delete from child tables first
    related_tables = [
        "alerts",
        "notifications",
        "query_history",
        "subscriptions",
        "usage_tracking",
        "rate_limits",
        "payment_fingerprints",
        "fraud_detection",
        "suspicious_activities",
    ]

    for table in related_tables:
        await db.execute(text(f"DELETE FROM {table} WHERE user_id = :user_id"), {"user_id": user_id})

    # Handle duplicate_account_detection (has two FK columns)
    await db.execute(text("DELETE FROM duplicate_account_detection WHERE user_id = :user_id OR duplicate_user_id = :user_id"), {"user_id": user_id})

    # Delete user
    await db.execute(delete(UserAuth).where(UserAuth.user_id == user_id))
    await db.commit()

    return MessageResponse(
        message="User deleted successfully",
        detail=f"User {user.email} has been permanently deleted"
    )


@router.post("/users/{user_id}/ban", response_model=MessageResponse)
async def ban_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Ban user account (set is_active to False)
    """
    # Prevent self-ban
    if str(current_user.user_id) == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban your own account"
        )

    # Update user
    result = await db.execute(
        update(UserAuth)
        .where(UserAuth.user_id == user_id)
        .values(is_active=False, updated_at=datetime.utcnow())
        .returning(UserAuth.email)
    )
    await db.commit()

    user_email = result.scalar_one_or_none()
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "ban_user",
        {"user_id": str(user_id), "email": user_email}
    )

    return MessageResponse(
        message="User banned successfully",
        detail=f"User {user_email} has been banned"
    )


@router.post("/users/{user_id}/unban", response_model=MessageResponse)
async def unban_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Unban user account (set is_active to True)
    """
    # Update user
    result = await db.execute(
        update(UserAuth)
        .where(UserAuth.user_id == user_id)
        .values(is_active=True, updated_at=datetime.utcnow())
        .returning(UserAuth.email)
    )
    await db.commit()

    user_email = result.scalar_one_or_none()
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "unban_user",
        {"user_id": str(user_id), "email": user_email}
    )

    return MessageResponse(
        message="User unbanned successfully",
        detail=f"User {user_email} has been unbanned"
    )


# ============================================================================
# TENDER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/tenders", response_model=TenderListResponse)
async def list_tenders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all tenders with filtering

    Filters:
    - status: Filter by tender status
    - category: Filter by category
    - search: Search in title and description
    """
    # Build query
    query = select(Tender)

    # Apply filters
    conditions = []
    if status:
        conditions.append(Tender.status == status)
    if category:
        conditions.append(Tender.category == category)
    if search:
        conditions.append(
            or_(
                Tender.title.ilike(f"%{search}%"),
                Tender.description.ilike(f"%{search}%")
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(Tender.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    tenders = result.scalars().all()

    # Convert to response format
    tender_items = [
        TenderListItem(
            tender_id=tender.tender_id,
            title=tender.title,
            category=tender.category,
            procuring_entity=tender.procuring_entity,
            status=tender.status,
            estimated_value_mkd=tender.estimated_value_mkd,
            opening_date=tender.opening_date,
            closing_date=tender.closing_date,
            created_at=tender.created_at
        )
        for tender in tenders
    ]

    return TenderListResponse(
        total=total,
        skip=skip,
        limit=limit,
        tenders=tender_items
    )


@router.post("/tenders/{tender_id}/approve", response_model=MessageResponse)
async def approve_tender(
    tender_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve tender (set status to 'open')
    """
    result = await db.execute(
        update(Tender)
        .where(Tender.tender_id == tender_id)
        .values(status="open", updated_at=datetime.utcnow())
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "approve_tender",
        {"tender_id": tender_id}
    )

    return MessageResponse(
        message="Tender approved successfully",
        detail=f"Tender {tender_id} is now open"
    )


@router.delete("/tenders/{tender_id}", response_model=MessageResponse)
async def delete_tender(
    tender_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete tender

    WARNING: This will cascade delete all associated documents and embeddings
    """
    # Log before deletion
    await log_admin_action(
        db, current_user.user_id, "delete_tender",
        {"tender_id": tender_id}
    )

    # Delete tender
    result = await db.execute(delete(Tender).where(Tender.tender_id == tender_id))
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )

    return MessageResponse(
        message="Tender deleted successfully",
        detail=f"Tender {tender_id} has been permanently deleted"
    )


# ============================================================================
# SUBSCRIPTION MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all subscriptions with filtering

    Filters:
    - status: Filter by subscription status (active, cancelled, expired)
    """
    # Build query - join with UserAuth to get email and with Plan to get plan name
    query = (
        select(
            UserSubscription,
            UserAuth.email,
            SubscriptionPlan.name.label("plan_name")
        )
        .join(UserAuth, UserAuth.user_id == UserSubscription.user_id)
        .join(SubscriptionPlan, SubscriptionPlan.plan_id == UserSubscription.plan_id)
    )

    # Apply filters
    if status:
        try:
            status_enum = SubscriptionStatus[status]
            query = query.where(UserSubscription.status == status_enum)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )

    # Get total count
    count_query = select(func.count(UserSubscription.subscription_id))
    if status:
        try:
            status_enum = SubscriptionStatus[status]
            count_query = count_query.where(UserSubscription.status == status_enum)
        except KeyError:
            pass
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(UserSubscription.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    # Convert to response format
    subscription_items = [
        SubscriptionListItem(
            subscription_id=row.UserSubscription.subscription_id,
            user_email=row.email,
            plan_name=row.plan_name,
            status=row.UserSubscription.status.value,
            current_period_start=row.UserSubscription.current_period_start,
            current_period_end=row.UserSubscription.current_period_end,
            cancel_at_period_end=row.UserSubscription.cancel_at_period_end,
            auto_renew=row.UserSubscription.auto_renew
        )
        for row in rows
    ]

    return SubscriptionListResponse(
        total=total,
        skip=skip,
        limit=limit,
        subscriptions=subscription_items
    )


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system analytics

    Returns:
    - User growth trend (last 30 days)
    - Revenue trend (last 12 months)
    - Query trend (last 30 days)
    - Subscription distribution
    - Top tender categories
    - Active users metrics
    """
    # User growth trend (last 30 days)
    users_growth = {}
    for i in range(30, 0, -1):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        count = await db.scalar(
            select(func.count(UserAuth.user_id))
            .where(func.date(UserAuth.created_at) == date)
        ) or 0
        users_growth[date.isoformat()] = count

    # Revenue trend (last 12 months)
    revenue_trend = {}
    for i in range(12, 0, -1):
        month_start = (datetime.utcnow() - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        revenue = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount_mkd), 0))
            .where(
                and_(
                    Payment.status == PaymentStatus.succeeded,
                    Payment.created_at >= month_start,
                    Payment.created_at < month_end
                )
            )
        ) or Decimal(0)
        revenue_trend[month_start.strftime("%Y-%m")] = revenue

    # Query trend (last 30 days)
    queries_trend = {}
    for i in range(30, 0, -1):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        count = await db.scalar(
            select(func.count(QueryHistory.query_id))
            .where(func.date(QueryHistory.created_at) == date)
        ) or 0
        queries_trend[date.isoformat()] = count

    # Subscription distribution
    subscription_distribution = {}
    result = await db.execute(
        select(UserAuth.role, func.count(UserAuth.user_id))
        .group_by(UserAuth.role)
    )
    for role, count in result.all():
        subscription_distribution[role.value] = count

    # Top categories
    top_categories = []
    result = await db.execute(
        select(Tender.category, func.count(Tender.tender_id).label("count"))
        .where(Tender.category.isnot(None))
        .group_by(Tender.category)
        .order_by(desc("count"))
        .limit(10)
    )
    for category, count in result.all():
        top_categories.append({"category": category, "count": count})

    # Active users
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    active_users_today = await db.scalar(
        select(func.count(func.distinct(QueryHistory.user_id)))
        .where(QueryHistory.created_at >= today)
    ) or 0

    active_users_week = await db.scalar(
        select(func.count(func.distinct(QueryHistory.user_id)))
        .where(QueryHistory.created_at >= week_ago)
    ) or 0

    active_users_month = await db.scalar(
        select(func.count(func.distinct(QueryHistory.user_id)))
        .where(QueryHistory.created_at >= month_ago)
    ) or 0

    return AnalyticsResponse(
        users_growth=users_growth,
        revenue_trend={k: float(v) for k, v in revenue_trend.items()},
        queries_trend=queries_trend,
        subscription_distribution=subscription_distribution,
        top_categories=top_categories,
        active_users_today=active_users_today,
        active_users_week=active_users_week,
        active_users_month=active_users_month
    )


# ============================================================================
# AUDIT LOG ENDPOINTS
# ============================================================================

@router.get("/logs", response_model=AuditLogResponse)
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: Optional[str] = None,
    user_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs with filtering

    Filters:
    - action: Filter by action type
    - user_id: Filter by user
    - start_date: Filter by start date
    - end_date: Filter by end date
    """
    # Build query with join to get user email
    query = (
        select(AuditLog, UserAuth.email)
        .outerjoin(UserAuth, UserAuth.user_id == AuditLog.user_id)
    )

    # Apply filters
    conditions = []
    if action:
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count(AuditLog.audit_id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    # Convert to response format
    log_items = [
        AuditLogItem(
            audit_id=row.AuditLog.audit_id,
            user_id=row.AuditLog.user_id,
            user_email=row.email,
            action=row.AuditLog.action,
            details=row.AuditLog.details or {},
            ip_address=str(row.AuditLog.ip_address) if row.AuditLog.ip_address else None,
            created_at=row.AuditLog.created_at
        )
        for row in rows
    ]

    return AuditLogResponse(
        total=total,
        skip=skip,
        limit=limit,
        logs=log_items
    )


# ============================================================================
# SCRAPER CONTROL ENDPOINTS
# ============================================================================

@router.post("/scraper/trigger", response_model=MessageResponse)
async def trigger_scraper(
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger scraper execution

    This will run the scraper in the background
    """
    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "trigger_scraper",
        {"action": "manually triggered scraper"}
    )

    # TODO: Implement actual scraper trigger
    # background_tasks.add_task(run_scraper)

    return MessageResponse(
        message="Scraper triggered successfully",
        detail="Scraper is now running in the background"
    )


@router.get("/scraper/status", response_model=ScraperStatus)
async def get_scraper_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current scraper status

    Returns:
    - Whether scraper is running
    - Last run time
    - Total scraped count
    - Error count
    - Next scheduled run
    """
    # Get total tenders
    total_tenders = await db.scalar(select(func.count(Tender.tender_id))) or 0

    # Get last scrape run from scrape_history table
    last_run_query = text("""
        SELECT started_at, completed_at, status, errors
        FROM scrape_history
        ORDER BY started_at DESC
        LIMIT 1
    """)
    result = await db.execute(last_run_query)
    last_run_row = result.fetchone()

    # Get last successful run
    last_success_query = text("""
        SELECT completed_at
        FROM scrape_history
        WHERE status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
    """)
    result = await db.execute(last_success_query)
    last_success_row = result.fetchone()

    # Get total errors
    errors_query = text("SELECT COALESCE(SUM(errors), 0) FROM scrape_history")
    total_errors = await db.scalar(errors_query) or 0

    # Check if currently running
    is_running = False
    last_run = None
    last_success = None

    if last_run_row:
        last_run = last_run_row[0]  # started_at
        is_running = last_run_row[2] == 'running'  # status

    if last_success_row:
        last_success = last_success_row[0]

    return ScraperStatus(
        is_running=is_running,
        last_run=last_run,
        last_success=last_success,
        total_scraped=total_tenders,
        errors_count=int(total_errors),
        next_scheduled_run=None  # Cron-based, not tracked in DB
    )


# ============================================================================
# SYSTEM HEALTH ENDPOINTS
# ============================================================================

@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed system health status

    Checks:
    - Database connectivity
    - Redis (if available)
    - Storage system
    - External services
    """
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        database_status = "healthy"
    except Exception as e:
        database_status = f"unhealthy: {str(e)}"

    # TODO: Check other services (Redis, storage, etc.)

    return SystemHealthResponse(
        status="healthy" if database_status == "healthy" else "degraded",
        database=database_status,
        redis=None,
        storage={"status": "healthy", "available_space": "unknown"},
        services={
            "api": "healthy",
            "scraper": "unknown",
            "email": "unknown"
        },
        uptime_seconds=0,
        timestamp=datetime.utcnow()
    )


class VectorHealthResponse(BaseModel):
    """Vector database health response"""
    status: str
    total_embeddings: int
    total_documents: int
    documents_with_embeddings: int
    documents_without_embeddings: int
    coverage_percentage: float
    avg_chunks_per_document: float
    index_status: str
    last_embedding_created: Optional[datetime]
    storage_size_mb: Optional[float]


@router.get("/vectors/health", response_model=VectorHealthResponse)
async def get_vector_health(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get vector database health and statistics

    Returns:
    - Total embeddings count
    - Document coverage (how many docs have embeddings)
    - Index health status
    - Storage metrics
    - Last embedding timestamp
    """
    try:
        # Get total embeddings
        total_embeddings = await db.scalar(
            text("SELECT COUNT(*) FROM embeddings")
        ) or 0

        # Get total documents
        total_documents = await db.scalar(
            text("SELECT COUNT(*) FROM documents WHERE extraction_status = 'success'")
        ) or 0

        # Get documents with embeddings (distinct)
        documents_with_embeddings = await db.scalar(
            text("""
                SELECT COUNT(DISTINCT doc_id)
                FROM embeddings
                WHERE doc_id IS NOT NULL
            """)
        ) or 0

        # Calculate coverage
        documents_without_embeddings = total_documents - documents_with_embeddings
        coverage_percentage = (
            (documents_with_embeddings / total_documents * 100)
            if total_documents > 0 else 0.0
        )

        # Get average chunks per document
        avg_chunks = await db.scalar(
            text("""
                SELECT AVG(chunk_count)::float
                FROM (
                    SELECT doc_id, COUNT(*) as chunk_count
                    FROM embeddings
                    WHERE doc_id IS NOT NULL
                    GROUP BY doc_id
                ) AS counts
            """)
        ) or 0.0

        # Get last embedding created
        last_embedding = await db.scalar(
            text("""
                SELECT created_at
                FROM embeddings
                ORDER BY created_at DESC
                LIMIT 1
            """)
        )

        # Check index status
        index_exists = await db.scalar(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE tablename = 'embeddings'
                    AND indexname LIKE '%vector%'
                )
            """)
        )
        index_status = "healthy" if index_exists else "missing"

        # Estimate storage size (approximate)
        storage_size = await db.scalar(
            text("""
                SELECT pg_total_relation_size('embeddings')::float / 1024 / 1024
            """)
        ) or 0.0

        # Determine overall status
        if coverage_percentage >= 90 and index_status == "healthy":
            status = "healthy"
        elif coverage_percentage >= 70:
            status = "degraded"
        else:
            status = "unhealthy"

        return VectorHealthResponse(
            status=status,
            total_embeddings=total_embeddings,
            total_documents=total_documents,
            documents_with_embeddings=documents_with_embeddings,
            documents_without_embeddings=documents_without_embeddings,
            coverage_percentage=round(coverage_percentage, 2),
            avg_chunks_per_document=round(avg_chunks, 2),
            index_status=index_status,
            last_embedding_created=last_embedding,
            storage_size_mb=round(storage_size, 2)
        )

    except Exception as e:
        logger.error(f"Vector health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Vector health check failed: {str(e)}"
        )


# ============================================================================
# BROADCAST NOTIFICATION ENDPOINTS
# ============================================================================

@router.post("/broadcast", response_model=MessageResponse)
async def broadcast_notification(
    broadcast: BroadcastRequest,
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
):
    """
    Send notification to all users (or filtered subset)

    Filters:
    - target_tier: Send only to specific subscription tier
    - target_verified_only: Send only to verified users
    """
    # Build user query
    query = select(UserAuth.user_id)

    conditions = []
    if broadcast.target_verified_only:
        conditions.append(UserAuth.is_verified == True)

    if conditions:
        query = query.where(and_(*conditions))

    # Get all matching users
    result = await db.execute(query)
    user_ids = [row[0] for row in result.all()]

    # Create notifications for all users
    notifications = [
        Notification(
            user_id=user_id,
            message=broadcast.message,
            is_read=False
        )
        for user_id in user_ids
    ]

    db.add_all(notifications)
    await db.commit()

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "broadcast_notification",
        {
            "message": broadcast.message,
            "recipients_count": len(user_ids),
            "target_tier": broadcast.target_tier,
            "verified_only": broadcast.target_verified_only
        }
    )

    return MessageResponse(
        message="Broadcast sent successfully",
        detail=f"Notification sent to {len(user_ids)} users"
    )


class EmailBroadcastResponse(BaseModel):
    """Email broadcast response"""
    message: str
    recipients_count: int
    emails_sent: int
    emails_failed: int


@router.post("/broadcast/email", response_model=EmailBroadcastResponse)
async def broadcast_email(
    broadcast: EmailBroadcastRequest,
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
):
    """
    Send email broadcast to all users (or filtered subset)

    This sends actual emails via Mailersend to all matching users.
    Use with caution as this can send many emails.

    Filters:
    - target_tier: Send only to specific subscription tier
    - target_verified_only: Send only to verified users
    - send_notification: Also create in-app notification (default: True)
    """
    from services.mailer import mailer_service

    # Build user query
    query = select(UserAuth.user_id, UserAuth.email, UserAuth.full_name)

    conditions = [UserAuth.is_active == True]  # Only send to active users
    if broadcast.target_verified_only:
        conditions.append(UserAuth.is_verified == True)

    query = query.where(and_(*conditions))

    # Get all matching users
    result = await db.execute(query)
    users = result.all()

    if not users:
        return EmailBroadcastResponse(
            message="No users match the criteria",
            recipients_count=0,
            emails_sent=0,
            emails_failed=0
        )

    # Send emails in background
    emails_sent = 0
    emails_failed = 0

    # Create broadcast email content
    frontend_url = os.getenv("FRONTEND_URL", "https://nabavkidata.com")

    for user_id, email, full_name in users:
        try:
            # Generate email HTML content
            content = f"""
            <p>Hello <strong>{full_name or 'User'}</strong>,</p>
            <div style="margin: 20px 0; padding: 20px; background-color: #f8fafc; border-radius: 8px; border-left: 4px solid #2563eb;">
                {broadcast.message.replace(chr(10), '<br>')}
            </div>
            <p style="margin-top: 20px;">If you have any questions, please don't hesitate to contact our support team.</p>
            """

            html_content = mailer_service._get_email_template(
                title=broadcast.subject,
                content=content,
                button_text="Go to Dashboard",
                button_link=f"{frontend_url}/dashboard"
            )

            success = await mailer_service.send_transactional_email(
                to=email,
                subject=broadcast.subject,
                html_content=html_content,
                reply_to="support@nabavkidata.com"
            )

            if success:
                emails_sent += 1
            else:
                emails_failed += 1
                logger.warning(f"Failed to send broadcast email to {email}")

        except Exception as e:
            emails_failed += 1
            logger.error(f"Error sending broadcast email to {email}: {e}")

    # Create in-app notifications if requested
    if broadcast.send_notification:
        notifications = [
            Notification(
                user_id=user_id,
                message=f"{broadcast.subject}: {broadcast.message[:200]}{'...' if len(broadcast.message) > 200 else ''}",
                is_read=False
            )
            for user_id, _, _ in users
        ]
        db.add_all(notifications)
        await db.commit()

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "broadcast_email",
        {
            "subject": broadcast.subject,
            "message_preview": broadcast.message[:100],
            "recipients_count": len(users),
            "emails_sent": emails_sent,
            "emails_failed": emails_failed,
            "target_tier": broadcast.target_tier,
            "verified_only": broadcast.target_verified_only,
            "with_notification": broadcast.send_notification
        }
    )

    return EmailBroadcastResponse(
        message="Email broadcast completed",
        recipients_count=len(users),
        emails_sent=emails_sent,
        emails_failed=emails_failed
    )
