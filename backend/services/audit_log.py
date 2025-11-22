"""
Audit Logging Service for nabavkidata.com
Tracks admin actions, user actions, and system events
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import uuid

from database import AsyncSessionLocal
from models import AuditLog, User

logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for logging and retrieving audit events"""

    async def log_admin_action(
        self,
        admin_id: uuid.UUID,
        action: str,
        target: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Optional[uuid.UUID]:
        """
        Log an administrative action

        Args:
            admin_id: UUID of admin user performing action
            action: Action type (e.g., 'user_ban', 'config_update', 'data_export')
            target: Target of action (e.g., user_id, config_key)
            details: Additional details about the action
            ip_address: IP address of admin

        Returns:
            UUID of created audit log entry or None on error
        """
        try:
            async with AsyncSessionLocal() as session:
                audit_entry = AuditLog(
                    audit_id=uuid.uuid4(),
                    user_id=admin_id,
                    action=f"admin:{action}",
                    details={
                        "target": target,
                        "action_type": "admin",
                        **(details or {})
                    },
                    ip_address=ip_address,
                    created_at=datetime.utcnow()
                )

                session.add(audit_entry)
                await session.commit()

                logger.info(
                    f"Admin action logged: {action} by {admin_id} on {target}"
                )

                return audit_entry.audit_id

        except Exception as e:
            logger.error(f"Error logging admin action: {e}")
            return None

    async def log_user_action(
        self,
        user_id: uuid.UUID,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Optional[uuid.UUID]:
        """
        Log a user action

        Args:
            user_id: UUID of user performing action
            action: Action type (e.g., 'login', 'password_change', 'data_export')
            details: Additional details about the action
            ip_address: IP address of user

        Returns:
            UUID of created audit log entry or None on error
        """
        try:
            async with AsyncSessionLocal() as session:
                audit_entry = AuditLog(
                    audit_id=uuid.uuid4(),
                    user_id=user_id,
                    action=f"user:{action}",
                    details={
                        "action_type": "user",
                        **(details or {})
                    },
                    ip_address=ip_address,
                    created_at=datetime.utcnow()
                )

                session.add(audit_entry)
                await session.commit()

                logger.info(f"User action logged: {action} by {user_id}")

                return audit_entry.audit_id

        except Exception as e:
            logger.error(f"Error logging user action: {e}")
            return None

    async def log_system_event(
        self,
        event: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[uuid.UUID]:
        """
        Log a system event (no user associated)

        Args:
            event: Event type (e.g., 'scraper_run', 'backup_completed', 'error')
            details: Additional details about the event

        Returns:
            UUID of created audit log entry or None on error
        """
        try:
            async with AsyncSessionLocal() as session:
                audit_entry = AuditLog(
                    audit_id=uuid.uuid4(),
                    user_id=None,
                    action=f"system:{event}",
                    details={
                        "action_type": "system",
                        **(details or {})
                    },
                    ip_address=None,
                    created_at=datetime.utcnow()
                )

                session.add(audit_entry)
                await session.commit()

                logger.info(f"System event logged: {event}")

                return audit_entry.audit_id

        except Exception as e:
            logger.error(f"Error logging system event: {e}")
            return None

    async def get_audit_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with optional filters

        Args:
            filters: Optional filters to apply:
                - user_id: Filter by specific user
                - action_type: Filter by action type prefix (admin, user, system)
                - action: Filter by specific action
                - start_date: Filter entries after this date
                - end_date: Filter entries before this date
                - ip_address: Filter by IP address
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of audit log entries with user details
        """
        try:
            async with AsyncSessionLocal() as session:
                # Build query
                query = select(AuditLog).join(
                    User,
                    AuditLog.user_id == User.user_id,
                    isouter=True
                )

                # Apply filters
                conditions = []

                if filters:
                    if "user_id" in filters:
                        conditions.append(AuditLog.user_id == filters["user_id"])

                    if "action_type" in filters:
                        conditions.append(
                            AuditLog.action.like(f"{filters['action_type']}:%")
                        )

                    if "action" in filters:
                        conditions.append(AuditLog.action == filters["action"])

                    if "start_date" in filters:
                        conditions.append(AuditLog.created_at >= filters["start_date"])

                    if "end_date" in filters:
                        conditions.append(AuditLog.created_at <= filters["end_date"])

                    if "ip_address" in filters:
                        conditions.append(AuditLog.ip_address == filters["ip_address"])

                if conditions:
                    query = query.where(and_(*conditions))

                # Order by most recent first
                query = query.order_by(AuditLog.created_at.desc())

                # Apply pagination
                query = query.limit(limit).offset(offset)

                # Execute query
                result = await session.execute(query)
                audit_logs = result.scalars().all()

                # Get user details for each log
                log_entries = []
                for log in audit_logs:
                    entry = {
                        "audit_id": str(log.audit_id),
                        "user_id": str(log.user_id) if log.user_id else None,
                        "action": log.action,
                        "details": log.details,
                        "ip_address": log.ip_address,
                        "created_at": log.created_at.isoformat()
                    }

                    # Add user details if available
                    if log.user_id:
                        user_result = await session.execute(
                            select(User).where(User.user_id == log.user_id)
                        )
                        user = user_result.scalar_one_or_none()
                        if user:
                            entry["user_email"] = user.email
                            entry["user_name"] = user.full_name

                    log_entries.append(entry)

                return log_entries

        except Exception as e:
            logger.error(f"Error retrieving audit logs: {e}")
            return []

    async def get_user_audit_trail(
        self,
        user_id: uuid.UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get complete audit trail for a specific user

        Args:
            user_id: UUID of user
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of audit log entries for the user
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        return await self.get_audit_logs(
            filters={
                "user_id": user_id,
                "start_date": start_date
            },
            limit=limit
        )

    async def get_admin_actions(
        self,
        days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all admin actions within a time period

        Args:
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of admin action audit logs
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        return await self.get_audit_logs(
            filters={
                "action_type": "admin",
                "start_date": start_date
            },
            limit=limit
        )

    async def get_security_events(
        self,
        days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get security-related audit events

        Args:
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of security-related audit logs
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            async with AsyncSessionLocal() as session:
                # Security-related actions
                security_actions = [
                    "user:login",
                    "user:logout",
                    "user:password_change",
                    "user:password_reset",
                    "user:email_change",
                    "user:2fa_enable",
                    "user:2fa_disable",
                    "admin:user_ban",
                    "admin:user_unban",
                    "admin:role_change"
                ]

                query = select(AuditLog).where(
                    and_(
                        AuditLog.action.in_(security_actions),
                        AuditLog.created_at >= start_date
                    )
                ).order_by(AuditLog.created_at.desc()).limit(limit)

                result = await session.execute(query)
                logs = result.scalars().all()

                return [
                    {
                        "audit_id": str(log.audit_id),
                        "user_id": str(log.user_id) if log.user_id else None,
                        "action": log.action,
                        "details": log.details,
                        "ip_address": log.ip_address,
                        "created_at": log.created_at.isoformat()
                    }
                    for log in logs
                ]

        except Exception as e:
            logger.error(f"Error retrieving security events: {e}")
            return []

    async def get_audit_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get audit log statistics

        Args:
            days: Number of days to analyze

        Returns:
            Statistics about audit logs
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            async with AsyncSessionLocal() as session:
                # Total events
                result = await session.execute(
                    select(func.count(AuditLog.audit_id)).where(
                        AuditLog.created_at >= start_date
                    )
                )
                total_events = result.scalar()

                # Events by type
                result = await session.execute(
                    select(
                        func.substring(AuditLog.action, 1, func.position(':' in AuditLog.action) - 1).label('action_type'),
                        func.count(AuditLog.audit_id)
                    ).where(
                        AuditLog.created_at >= start_date
                    ).group_by('action_type')
                )
                events_by_type = {row[0]: row[1] for row in result.fetchall()}

                # Most active users
                result = await session.execute(
                    select(
                        AuditLog.user_id,
                        func.count(AuditLog.audit_id)
                    ).where(
                        and_(
                            AuditLog.created_at >= start_date,
                            AuditLog.user_id.isnot(None)
                        )
                    ).group_by(AuditLog.user_id).order_by(
                        func.count(AuditLog.audit_id).desc()
                    ).limit(10)
                )
                most_active = [
                    {"user_id": str(row[0]), "event_count": row[1]}
                    for row in result.fetchall()
                ]

                return {
                    "period_days": days,
                    "total_events": total_events,
                    "events_by_type": events_by_type,
                    "most_active_users": most_active,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error getting audit stats: {e}")
            return {"error": str(e)}


# Singleton instance
audit_service = AuditLogService()
