"""
Cron Execution Logger
Tracks cron job executions for monitoring in admin panel
"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import will be done lazily to avoid circular imports
_CronExecution = None


def _get_cron_execution_model():
    global _CronExecution
    if _CronExecution is None:
        from models import CronExecution
        _CronExecution = CronExecution
    return _CronExecution


class CronLogger:
    """Context manager for logging cron executions"""

    def __init__(
        self,
        db: AsyncSession,
        job_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.db = db
        self.job_name = job_name
        self.details = details or {}
        self.execution_id: Optional[UUID] = None
        self.started_at: Optional[datetime] = None
        self.records_processed: int = 0

    async def __aenter__(self):
        """Log cron start"""
        CronExecution = _get_cron_execution_model()

        self.started_at = datetime.utcnow()
        self.execution_id = uuid.uuid4()

        execution = CronExecution(
            execution_id=self.execution_id,
            job_name=self.job_name,
            status="started",
            started_at=self.started_at,
            details=self.details
        )
        self.db.add(execution)
        await self.db.commit()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Log cron completion or failure"""
        CronExecution = _get_cron_execution_model()

        completed_at = datetime.utcnow()
        duration = int((completed_at - self.started_at).total_seconds())

        # Update the execution record
        result = await self.db.execute(
            select(CronExecution).where(CronExecution.execution_id == self.execution_id)
        )
        execution = result.scalar_one_or_none()

        if execution:
            if exc_type is not None:
                # Job failed
                execution.status = "failed"
                execution.error_message = str(exc_val)
            else:
                # Job completed successfully
                execution.status = "completed"

            execution.completed_at = completed_at
            execution.duration_seconds = duration
            execution.records_processed = self.records_processed
            execution.details = self.details

            await self.db.commit()

        # Don't suppress exceptions
        return False

    def set_records_processed(self, count: int):
        """Update the count of records processed"""
        self.records_processed = count

    def add_detail(self, key: str, value: Any):
        """Add a detail to the execution log"""
        self.details[key] = value


async def log_cron_start(
    db: AsyncSession,
    job_name: str,
    details: Optional[Dict[str, Any]] = None
) -> UUID:
    """Log cron job start and return execution_id"""
    CronExecution = _get_cron_execution_model()

    execution_id = uuid.uuid4()
    execution = CronExecution(
        execution_id=execution_id,
        job_name=job_name,
        status="started",
        started_at=datetime.utcnow(),
        details=details or {}
    )
    db.add(execution)
    await db.commit()
    return execution_id


async def log_cron_complete(
    db: AsyncSession,
    execution_id: UUID,
    records_processed: int = 0,
    details: Optional[Dict[str, Any]] = None
):
    """Log cron job completion"""
    CronExecution = _get_cron_execution_model()

    result = await db.execute(
        select(CronExecution).where(CronExecution.execution_id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if execution:
        completed_at = datetime.utcnow()
        execution.status = "completed"
        execution.completed_at = completed_at
        execution.duration_seconds = int((completed_at - execution.started_at).total_seconds())
        execution.records_processed = records_processed
        if details:
            execution.details = {**(execution.details or {}), **details}
        await db.commit()


async def log_cron_failed(
    db: AsyncSession,
    execution_id: UUID,
    error_message: str,
    details: Optional[Dict[str, Any]] = None
):
    """Log cron job failure"""
    CronExecution = _get_cron_execution_model()

    result = await db.execute(
        select(CronExecution).where(CronExecution.execution_id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if execution:
        completed_at = datetime.utcnow()
        execution.status = "failed"
        execution.completed_at = completed_at
        execution.duration_seconds = int((completed_at - execution.started_at).total_seconds())
        execution.error_message = error_message
        if details:
            execution.details = {**(execution.details or {}), **details}
        await db.commit()
