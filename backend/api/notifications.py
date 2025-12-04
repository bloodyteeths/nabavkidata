"""
Notifications API

Push notification system for in-app notifications
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from datetime import datetime
import uuid
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from api.auth import get_current_user

router = APIRouter()


# ============================================================================
# MODELS
# ============================================================================

class NotificationBase(BaseModel):
    type: str  # 'alert_match', 'briefing_ready', 'tender_update', 'system'
    title: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = {}


class NotificationCreate(NotificationBase):
    user_id: str


class Notification(NotificationBase):
    notification_id: str
    user_id: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationMarkRead(BaseModel):
    notification_ids: List[str]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def create_notification(
    db: AsyncSession,
    user_id: str,
    type: str,
    title: str,
    message: str = None,
    data: dict = None,
    tender_id: str = None,
    alert_id: str = None
):
    """Create a notification for a user"""
    import json
    notification_id = str(uuid.uuid4())

    query = text("""
        INSERT INTO notifications (notification_id, user_id, type, title, message, data, tender_id, alert_id, is_read, created_at)
        VALUES (:notification_id, :user_id, :type, :title, :message, :data, :tender_id, :alert_id, false, NOW())
    """)

    await db.execute(query, {
        'notification_id': notification_id,
        'user_id': user_id,
        'type': type,
        'title': title,
        'message': message,
        'data': json.dumps(data or {}),
        'tender_id': tender_id,
        'alert_id': alert_id
    })
    await db.commit()

    return {
        'notification_id': notification_id,
        'user_id': user_id,
        'type': type,
        'title': title,
        'message': message,
        'data': data or {},
        'is_read': False,
        'created_at': datetime.utcnow()
    }


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("")
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False, alias='unread'),
    type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get user notifications (paginated)
    """
    user_id = str(current_user.user_id)
    offset = (page - 1) * page_size

    # Build WHERE clause
    where_conditions = ["user_id = :user_id"]
    params = {"user_id": user_id, "limit": page_size, "offset": offset}

    if unread_only:
        where_conditions.append("is_read = false")
    if type:
        where_conditions.append("type = :type")
        params["type"] = type

    where_clause = " AND ".join(where_conditions)

    # Count total
    count_query = text(f"SELECT COUNT(*) FROM notifications WHERE {where_clause}")
    count_result = await db.execute(count_query, params)
    total = count_result.scalar() or 0

    # Get paginated results
    query = text(f"""
        SELECT notification_id, user_id, type, title, message, data, tender_id, alert_id, is_read, created_at
        FROM notifications
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(query, params)
    rows = result.fetchall()

    items = [
        {
            'notification_id': str(row.notification_id),
            'user_id': str(row.user_id),
            'type': row.type,
            'title': row.title,
            'message': row.message,
            'data': row.data or {},
            'tender_id': row.tender_id,
            'alert_id': str(row.alert_id) if row.alert_id else None,
            'is_read': row.is_read,
            'created_at': row.created_at.isoformat() if row.created_at else None
        }
        for row in rows
    ]

    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': items
    }


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get count of unread notifications (for badge)
    """
    user_id = str(current_user.user_id)

    query = text("""
        SELECT COUNT(*) FROM notifications
        WHERE user_id = :user_id AND is_read = false
    """)

    result = await db.execute(query, {"user_id": user_id})
    count = result.scalar() or 0

    return {'unread_count': count}


@router.post("/mark-read")
async def mark_notifications_read(
    body: NotificationMarkRead,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Mark specific notifications as read
    """
    user_id = str(current_user.user_id)

    if not body.notification_ids:
        return {'message': 'No notifications to mark', 'updated': 0}

    # Build placeholders for IN clause
    placeholders = ", ".join([f":id_{i}" for i in range(len(body.notification_ids))])
    params = {"user_id": user_id}
    for i, nid in enumerate(body.notification_ids):
        params[f"id_{i}"] = nid

    query = text(f"""
        UPDATE notifications
        SET is_read = true
        WHERE notification_id IN ({placeholders}) AND user_id = :user_id
    """)

    result = await db.execute(query, params)
    await db.commit()

    return {
        'message': f'Marked {result.rowcount} notifications as read',
        'updated': result.rowcount
    }


@router.post("/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Mark all user notifications as read
    """
    user_id = str(current_user.user_id)

    query = text("""
        UPDATE notifications
        SET is_read = true
        WHERE user_id = :user_id AND is_read = false
    """)

    result = await db.execute(query, {"user_id": user_id})
    await db.commit()

    return {
        'message': f'Marked all notifications as read',
        'updated': result.rowcount
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a notification
    """
    user_id = str(current_user.user_id)

    query = text("""
        DELETE FROM notifications
        WHERE notification_id = :notification_id AND user_id = :user_id
    """)

    result = await db.execute(query, {"notification_id": notification_id, "user_id": user_id})
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {'message': 'Notification deleted'}


# ============================================================================
# ADMIN ENDPOINTS (for creating notifications)
# ============================================================================

@router.post("/admin/create")
async def admin_create_notification(
    notification: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Admin endpoint to create a notification for a user
    """
    # Check if user is admin
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await create_notification(
        db=db,
        user_id=notification.user_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        data=notification.data,
        tender_id=notification.data.get('tender_id') if notification.data else None,
        alert_id=notification.data.get('alert_id') if notification.data else None
    )

    return result


@router.post("/admin/broadcast")
async def admin_broadcast_notification(
    notification: NotificationBase,
    target_users: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Admin endpoint to broadcast a notification to multiple users
    """
    # Check if user is admin
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")

    # If no target_users specified, send to all users
    if not target_users:
        query = text("SELECT user_id FROM users")
        result = await db.execute(query)
        target_users = [str(row.user_id) for row in result.fetchall()]

    # Create notification for each user
    created_count = 0
    for user_id in target_users:
        await create_notification(
            db=db,
            user_id=user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            data=notification.data
        )
        created_count += 1

    return {
        'message': f'Broadcast sent to {created_count} users',
        'count': created_count
    }
