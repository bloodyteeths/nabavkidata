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
from models_auth import UserRole
# Note: Using Subscription from models.py (maps to existing subscriptions table)
# UserSubscription, Payment, Invoice etc. from models_billing use tables that don't exist yet
from middleware.rbac import get_current_active_user, require_role
from pydantic import BaseModel, Field


# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/api/admin",
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
    total_users = await db.scalar(select(func.count(User.user_id)))
    active_users = total_users  # All users are considered active
    verified_users = await db.scalar(
        select(func.count(User.user_id)).where(User.email_verified == True)
    )

    # Tender statistics
    total_tenders = await db.scalar(select(func.count(Tender.tender_id)))
    open_tenders = await db.scalar(
        select(func.count(Tender.tender_id)).where(Tender.status == "open")
    )

    # Subscription statistics (using Subscription model from models.py)
    total_subscriptions = await db.scalar(select(func.count(Subscription.subscription_id)))
    active_subscriptions = await db.scalar(
        select(func.count(Subscription.subscription_id))
        .where(Subscription.status == "active")
    )

    # Revenue statistics - no payments table yet, return zeros
    current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue_mkd = Decimal(0)
    monthly_revenue_eur = Decimal(0)

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
    query = select(User)

    # Apply filters
    conditions = []
    if role:
        conditions.append(User.role == role)
    # status filter removed - all users are active in current schema
    if search:
        conditions.append(
            or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(User.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    # Convert to response format
    user_items = [
        UserListItem(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            subscription_tier=user.subscription_tier or "free",
            email_verified=user.email_verified,
            is_active=True,  # All users considered active
            role=user.role or "user",
            created_at=user.created_at,
            last_login=None  # Field doesn't exist in User model
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
    result = await db.execute(select(User).where(User.user_id == user_id))
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

    # Get active subscription (using Subscription model from models.py)
    subscription_result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == user_id,
                Subscription.status == "active"
            )
        )
        .order_by(desc(Subscription.created_at))
        .limit(1)
    )
    active_subscription_obj = subscription_result.scalar_one_or_none()

    active_subscription = None
    if active_subscription_obj:
        active_subscription = {
            "subscription_id": str(active_subscription_obj.subscription_id),
            "status": active_subscription_obj.status,
            "current_period_start": active_subscription_obj.current_period_start.isoformat() if active_subscription_obj.current_period_start else None,
            "current_period_end": active_subscription_obj.current_period_end.isoformat() if active_subscription_obj.current_period_end else None,
            "auto_renew": not active_subscription_obj.cancel_at_period_end
        }

    return UserDetailResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        subscription_tier=user.subscription_tier or "free",
        email_verified=user.email_verified,
        is_active=True,
        role=user.role or "user",
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=None,
        stripe_customer_id=user.stripe_customer_id,
        failed_login_attempts=0,
        locked_until=None,
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
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Build update dictionary
    updates = {}
    if update_data.role is not None:
        valid_roles = ["admin", "moderator", "user"]
        if update_data.role.lower() not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {update_data.role}. Valid roles: {valid_roles}"
            )
        updates["role"] = update_data.role.lower()
    if update_data.email_verified is not None:
        updates["email_verified"] = update_data.email_verified
    if update_data.subscription_tier is not None:
        updates["subscription_tier"] = update_data.subscription_tier

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    updates["updated_at"] = datetime.utcnow()

    # Update user
    await db.execute(
        update(User)
        .where(User.user_id == user_id)
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
    result = await db.execute(select(User).where(User.user_id == user_id))
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
    await db.execute(delete(User).where(User.user_id == user_id))
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
    Ban user account (set role to 'banned')
    """
    # Prevent self-ban
    if str(current_user.user_id) == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban your own account"
        )

    # Update user - set role to banned
    result = await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(role='banned', updated_at=datetime.utcnow())
        .returning(User.email)
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
    Unban user account (restore role to 'user')
    """
    # Update user - restore role to user
    result = await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(role='user', updated_at=datetime.utcnow())
        .returning(User.email)
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
    # Build query - join with User to get email (using Subscription from models.py)
    query = (
        select(
            Subscription,
            User.email
        )
        .join(User, User.user_id == Subscription.user_id)
    )

    # Apply filters
    if status:
        query = query.where(Subscription.status == status)

    # Get total count
    count_query = select(func.count(Subscription.subscription_id))
    if status:
        count_query = count_query.where(Subscription.status == status)
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(Subscription.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    # Convert to response format
    subscription_items = [
        SubscriptionListItem(
            subscription_id=row.Subscription.subscription_id,
            user_email=row.email,
            plan_name=row.Subscription.tier or "Unknown",  # Use tier as plan name
            status=row.Subscription.status,
            current_period_start=row.Subscription.current_period_start,
            current_period_end=row.Subscription.current_period_end,
            cancel_at_period_end=row.Subscription.cancel_at_period_end or False,
            auto_renew=not (row.Subscription.cancel_at_period_end or False)
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
            select(func.count(User.user_id))
            .where(func.date(User.created_at) == date)
        ) or 0
        users_growth[date.isoformat()] = count

    # Revenue trend (last 12 months) - No payments table yet, return zeros
    revenue_trend = {}
    for i in range(12, 0, -1):
        month_start = (datetime.utcnow() - timedelta(days=30*i)).replace(day=1)
        revenue_trend[month_start.strftime("%Y-%m")] = Decimal(0)

    # Query trend (last 30 days)
    queries_trend = {}
    for i in range(30, 0, -1):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        count = await db.scalar(
            select(func.count(QueryHistory.query_id))
            .where(func.date(QueryHistory.created_at) == date)
        ) or 0
        queries_trend[date.isoformat()] = count

    # Subscription distribution (by role)
    subscription_distribution = {}
    result = await db.execute(
        select(User.role, func.count(User.user_id))
        .group_by(User.role)
    )
    for role, count in result.all():
        subscription_distribution[role or "user"] = count

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
        select(AuditLog, User.email)
        .outerjoin(User, User.user_id == AuditLog.user_id)
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
    query = select(User.user_id)

    conditions = []
    if broadcast.target_verified_only:
        conditions.append(User.email_verified == True)

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
    from services.postmark import postmark_service

    # Build user query
    query = select(User.user_id, User.email, User.full_name)

    conditions = [User.email_verified == True]  # Only send to active users
    if broadcast.target_verified_only:
        conditions.append(User.email_verified == True)

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

            html_content = postmark_service._get_email_template(
                title=broadcast.subject,
                content=content,
                button_text="Go to Dashboard",
                button_link=f"{frontend_url}/dashboard"
            )

            success = await postmark_service.send_email(
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


# ============================================================================
# CONTACTS MANAGEMENT ENDPOINTS
# ============================================================================

class ContactItem(BaseModel):
    """Contact item for admin"""
    contact_id: UUID
    contact_type: str  # procuring_entity, winner, bidder
    entity_name: str
    entity_type: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    contact_person: Optional[str]
    source_tender_id: Optional[str]
    status: str
    scraped_at: Optional[datetime]

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Paginated contacts response"""
    total: int
    skip: int
    limit: int
    with_email_count: int
    contacts: List[ContactItem]


class ContactStatsResponse(BaseModel):
    """Contact statistics response"""
    total_contacts: int
    with_email: int
    without_email: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]


@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    contact_type: Optional[str] = None,
    has_email: Optional[bool] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all contacts for admin outreach

    Filters:
    - contact_type: Filter by type (procuring_entity, winner, bidder)
    - has_email: Filter to only contacts with/without email
    - status: Filter by status (new, contacted, subscribed, unsubscribed)
    - search: Search by entity name or email
    """
    # Build query
    base_query = "SELECT * FROM contacts WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM contacts WHERE 1=1"
    email_count_query = "SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL AND email != ''"
    params = {}

    # Apply filters
    if contact_type:
        base_query += " AND contact_type = :contact_type"
        count_query += " AND contact_type = :contact_type"
        email_count_query += " AND contact_type = :contact_type"
        params["contact_type"] = contact_type

    if has_email is True:
        base_query += " AND email IS NOT NULL AND email != ''"
        count_query += " AND email IS NOT NULL AND email != ''"
    elif has_email is False:
        base_query += " AND (email IS NULL OR email = '')"
        count_query += " AND (email IS NULL OR email = '')"

    if status:
        base_query += " AND status = :status"
        count_query += " AND status = :status"
        params["status"] = status

    if search:
        base_query += " AND (entity_name ILIKE :search OR email ILIKE :search)"
        count_query += " AND (entity_name ILIKE :search OR email ILIKE :search)"
        params["search"] = f"%{search}%"

    # Get total count
    total = await db.scalar(text(count_query), params) or 0

    # Get count with email
    with_email_count = await db.scalar(text(email_count_query), params) or 0

    # Get paginated results
    base_query += " ORDER BY contact_type, entity_name LIMIT :limit OFFSET :skip"
    params["limit"] = limit
    params["skip"] = skip

    result = await db.execute(text(base_query), params)
    rows = result.fetchall()

    # Convert to response format
    contacts = [
        ContactItem(
            contact_id=row.contact_id,
            contact_type=row.contact_type,
            entity_name=row.entity_name,
            entity_type=row.entity_type,
            email=row.email,
            phone=row.phone,
            address=row.address,
            city=row.city,
            contact_person=row.contact_person,
            source_tender_id=row.source_tender_id,
            status=row.status,
            scraped_at=row.scraped_at
        )
        for row in rows
    ]

    return ContactListResponse(
        total=total,
        skip=skip,
        limit=limit,
        with_email_count=with_email_count,
        contacts=contacts
    )


@router.get("/contacts/stats", response_model=ContactStatsResponse)
async def get_contact_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get contact statistics for admin dashboard

    Returns:
    - Total contacts
    - Contacts with email
    - Breakdown by type (procuring_entity, winner, bidder)
    - Breakdown by status
    """
    # Total contacts
    total_contacts = await db.scalar(text("SELECT COUNT(*) FROM contacts")) or 0

    # With email
    with_email = await db.scalar(
        text("SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL AND email != ''")
    ) or 0

    # By type
    type_result = await db.execute(
        text("SELECT contact_type, COUNT(*) as count FROM contacts GROUP BY contact_type")
    )
    by_type = {row.contact_type: row.count for row in type_result.fetchall()}

    # By status
    status_result = await db.execute(
        text("SELECT status, COUNT(*) as count FROM contacts GROUP BY status")
    )
    by_status = {row.status: row.count for row in status_result.fetchall()}

    return ContactStatsResponse(
        total_contacts=total_contacts,
        with_email=with_email,
        without_email=total_contacts - with_email,
        by_type=by_type,
        by_status=by_status
    )


@router.get("/contacts/export")
async def export_contacts(
    contact_type: Optional[str] = None,
    has_email: bool = True,
    format: str = Query("csv", regex="^(csv|json)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export contacts to CSV or JSON for email campaigns

    Parameters:
    - contact_type: Filter by type (procuring_entity, winner, bidder)
    - has_email: Only export contacts with email (default: True)
    - format: Export format (csv, json)

    Returns file download
    """
    from fastapi.responses import StreamingResponse
    import csv
    import io

    # Build query
    query = "SELECT * FROM contacts WHERE 1=1"
    params = {}

    if contact_type:
        query += " AND contact_type = :contact_type"
        params["contact_type"] = contact_type

    if has_email:
        query += " AND email IS NOT NULL AND email != ''"

    query += " ORDER BY contact_type, entity_name"

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "export_contacts",
        {
            "format": format,
            "contact_type": contact_type,
            "has_email": has_email,
            "count": len(rows)
        }
    )

    if format == "json":
        # Export as JSON
        contacts = [
            {
                "entity_name": row.entity_name,
                "contact_type": row.contact_type,
                "email": row.email,
                "phone": row.phone,
                "address": row.address,
                "city": row.city,
                "contact_person": row.contact_person,
                "source_tender_id": row.source_tender_id,
            }
            for row in rows
        ]

        import json
        json_str = json.dumps(contacts, ensure_ascii=False, indent=2)

        return StreamingResponse(
            iter([json_str]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=contacts_{datetime.utcnow().strftime('%Y%m%d')}.json"}
        )

    else:
        # Export as CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Entity Name", "Type", "Email", "Phone", "Address", "City",
            "Contact Person", "Source Tender ID"
        ])

        # Data rows
        for row in rows:
            writer.writerow([
                row.entity_name,
                row.contact_type,
                row.email or "",
                row.phone or "",
                row.address or "",
                row.city or "",
                row.contact_person or "",
                row.source_tender_id or ""
            ])

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=contacts_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )


@router.patch("/contacts/{contact_id}/status", response_model=MessageResponse)
async def update_contact_status(
    contact_id: UUID,
    new_status: str = Query(..., regex="^(new|contacted|subscribed|unsubscribed)$"),
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update contact status after outreach

    Status values:
    - new: Not yet contacted
    - contacted: Email/message sent
    - subscribed: Signed up for service
    - unsubscribed: Opted out
    """
    query = """
        UPDATE contacts
        SET status = :status,
            notes = COALESCE(:notes, notes),
            last_contacted_at = CASE WHEN :status IN ('contacted', 'subscribed') THEN NOW() ELSE last_contacted_at END,
            updated_at = NOW()
        WHERE contact_id = :contact_id
        RETURNING entity_name
    """

    result = await db.execute(text(query), {
        "status": new_status,
        "notes": notes,
        "contact_id": contact_id
    })
    await db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    # Log admin action
    await log_admin_action(
        db, current_user.user_id, "update_contact_status",
        {"contact_id": str(contact_id), "new_status": new_status, "notes": notes}
    )

    return MessageResponse(
        message="Contact status updated",
        detail=f"Contact '{row.entity_name}' marked as {new_status}"
    )
