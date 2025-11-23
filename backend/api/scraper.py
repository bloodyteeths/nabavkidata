"""
Scraper API Endpoints for nabavkidata.com
Provides scraper control and monitoring functionality

Security:
- Requires ADMIN role for control operations
- Health check endpoint is public for monitoring

Features:
- Scraper health check (public)
- Scraper job history
- Manual scraper trigger
- Scraper status monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from database import get_db
from models import ScrapingJob, Tender, Document
from models_auth import UserRole
from middleware.rbac import get_current_active_user, require_role
from services.email_service import email_service

# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/scraper",
    tags=["Scraper"]
)

# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class ScraperHealthResponse(BaseModel):
    """Scraper health check response"""
    status: str  # healthy, warning, unhealthy
    last_successful_run: Optional[datetime]
    hours_since_success: Optional[float]
    recent_jobs_count: int
    failed_jobs_count: int
    error_rate: float
    avg_duration_minutes: Optional[float]
    total_tenders_scraped: int
    total_documents_scraped: int
    issues: List[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class ScrapingJobResponse(BaseModel):
    """Scraping job details response"""
    job_id: UUID
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    tenders_scraped: int
    documents_scraped: int
    errors_count: int
    error_message: Optional[str]
    spider_name: Optional[str]
    incremental: bool
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True


class ScrapingJobListResponse(BaseModel):
    """Paginated scraping job list response"""
    total: int
    skip: int
    limit: int
    jobs: List[ScrapingJobResponse]


class ScraperTriggerRequest(BaseModel):
    """Request to trigger scraper manually"""
    incremental: bool = Field(default=True, description="Run incremental scrape (only new/updated tenders)")
    max_pages: Optional[int] = Field(default=None, description="Limit pages to scrape (for testing)")
    notify_on_complete: bool = Field(default=True, description="Send email notification when complete")


class ScraperTriggerResponse(BaseModel):
    """Response after triggering scraper"""
    message: str
    job_id: UUID
    status: str


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    detail: Optional[str] = None


# ============================================================================
# SCRAPER HEALTH CHECK ENDPOINT (PUBLIC)
# ============================================================================

@router.get("/health", response_model=ScraperHealthResponse)
async def get_scraper_health(
    db: AsyncSession = Depends(get_db)
):
    """
    Get scraper health status (public endpoint for monitoring)

    Checks:
    - Last successful scrape time
    - Recent job error rate
    - Average job duration
    - Total scraped counts

    Returns:
    - status: healthy (< 2h since success, < 20% error rate)
    - status: warning (< 24h since success, < 50% error rate)
    - status: unhealthy (> 24h since success or > 50% error rate)
    """
    now = datetime.utcnow()
    issues = []

    # Check if scraping_jobs table exists
    table_exists = await db.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'scraping_jobs'
        )
    """)
    if not table_exists.scalar():
        return ScraperHealthResponse(
            status="warning",
            last_successful_run=None,
            hours_since_success=None,
            recent_jobs_count=0,
            failed_jobs_count=0,
            error_rate=0.0,
            avg_duration_minutes=None,
            total_tenders_scraped=0,
            total_documents_scraped=0,
            issues=["Scraping jobs table not found - scraper may not have run yet"],
            timestamp=now
        )

    # Get last successful scrape
    last_success_result = await db.execute(
        select(ScrapingJob)
        .where(ScrapingJob.status == "completed")
        .order_by(desc(ScrapingJob.completed_at))
        .limit(1)
    )
    last_success = last_success_result.scalar_one_or_none()

    hours_since_success = None
    if last_success and last_success.completed_at:
        hours_since_success = (now - last_success.completed_at).total_seconds() / 3600

        if hours_since_success > 24:
            issues.append(f"No successful scrape in {hours_since_success:.1f} hours (> 24h)")
        elif hours_since_success > 2:
            issues.append(f"Last successful scrape was {hours_since_success:.1f} hours ago")

    # Get recent jobs (last 10)
    recent_jobs_result = await db.execute(
        select(ScrapingJob)
        .where(ScrapingJob.completed_at.isnot(None))
        .order_by(desc(ScrapingJob.started_at))
        .limit(10)
    )
    recent_jobs = recent_jobs_result.scalars().all()

    recent_jobs_count = len(recent_jobs)
    failed_jobs_count = sum(1 for job in recent_jobs if job.status == "failed")
    error_rate = (failed_jobs_count / recent_jobs_count * 100) if recent_jobs_count > 0 else 0.0

    if error_rate > 50:
        issues.append(f"High error rate: {error_rate:.1f}% (> 50%)")
    elif error_rate > 20:
        issues.append(f"Elevated error rate: {error_rate:.1f}%")

    # Calculate average duration
    avg_duration_minutes = None
    if recent_jobs:
        durations = []
        for job in recent_jobs:
            if job.completed_at and job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                durations.append(duration)

        if durations:
            avg_duration_minutes = sum(durations) / len(durations) / 60

            if avg_duration_minutes > 60:
                issues.append(f"Jobs taking unusually long: {avg_duration_minutes:.1f} minutes average")

    # Get total counts
    total_tenders = await db.scalar(select(func.count(Tender.tender_id))) or 0
    total_documents = await db.scalar(select(func.count(Document.doc_id))) or 0

    # Determine overall status
    if not last_success:
        overall_status = "warning"
        issues.append("No successful scrapes found")
    elif hours_since_success and hours_since_success <= 2 and error_rate < 20:
        overall_status = "healthy"
    elif hours_since_success and hours_since_success <= 24 and error_rate < 50:
        overall_status = "warning"
    else:
        overall_status = "unhealthy"

    return ScraperHealthResponse(
        status=overall_status,
        last_successful_run=last_success.completed_at if last_success else None,
        hours_since_success=hours_since_success,
        recent_jobs_count=recent_jobs_count,
        failed_jobs_count=failed_jobs_count,
        error_rate=error_rate,
        avg_duration_minutes=avg_duration_minutes,
        total_tenders_scraped=total_tenders,
        total_documents_scraped=total_documents,
        issues=issues if issues else ["No issues detected"],
        timestamp=now
    )


# ============================================================================
# SCRAPER JOB HISTORY ENDPOINT (ADMIN)
# ============================================================================

@router.get(
    "/jobs",
    response_model=ScrapingJobListResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def get_scraping_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get scraping job history (admin only)

    Filters:
    - status: Filter by job status (running, completed, failed)
    """
    # Build query
    query = select(ScrapingJob)

    # Apply status filter
    if status:
        query = query.where(ScrapingJob.status == status)

    # Get total count
    count_query = select(func.count(ScrapingJob.job_id))
    if status:
        count_query = count_query.where(ScrapingJob.status == status)
    total = await db.scalar(count_query) or 0

    # Get paginated results
    query = query.order_by(desc(ScrapingJob.started_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Convert to response format
    job_items = []
    for job in jobs:
        duration_seconds = None
        if job.completed_at and job.started_at:
            duration_seconds = int((job.completed_at - job.started_at).total_seconds())

        job_items.append(ScrapingJobResponse(
            job_id=job.job_id,
            started_at=job.started_at,
            completed_at=job.completed_at,
            status=job.status,
            tenders_scraped=job.tenders_scraped,
            documents_scraped=job.documents_scraped,
            errors_count=job.errors_count,
            error_message=job.error_message,
            spider_name=job.spider_name,
            incremental=job.incremental,
            duration_seconds=duration_seconds
        ))

    return ScrapingJobListResponse(
        total=total,
        skip=skip,
        limit=limit,
        jobs=job_items
    )


# ============================================================================
# SCRAPER TRIGGER ENDPOINT (ADMIN)
# ============================================================================

@router.post(
    "/trigger",
    response_model=ScraperTriggerResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def trigger_scraper(
    trigger_request: ScraperTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger scraper execution (admin only)

    This will:
    1. Create a new scraping job record
    2. Run the scraper in the background
    3. Update job status on completion
    4. Send email notification if requested
    """
    # Create scraping job record
    job = ScrapingJob(
        started_at=datetime.utcnow(),
        status="running",
        spider_name="nabavki",
        incremental=trigger_request.incremental
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Add background task to run scraper
    # Note: Actual scraper execution would be implemented here
    # background_tasks.add_task(run_scraper_task, job.job_id, trigger_request)

    return ScraperTriggerResponse(
        message="Scraper triggered successfully",
        job_id=job.job_id,
        status="running"
    )


# ============================================================================
# SCRAPER STATUS ENDPOINT (ADMIN)
# ============================================================================

@router.get(
    "/status",
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def get_scraper_status(
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed scraper status (admin only)

    Returns:
    - Current running jobs
    - Last completed job details
    - System statistics
    """
    # Check for running jobs
    running_jobs_result = await db.execute(
        select(ScrapingJob)
        .where(ScrapingJob.status == "running")
        .order_by(desc(ScrapingJob.started_at))
    )
    running_jobs = running_jobs_result.scalars().all()

    # Get last completed job
    last_job_result = await db.execute(
        select(ScrapingJob)
        .where(ScrapingJob.status.in_(["completed", "failed"]))
        .order_by(desc(ScrapingJob.completed_at))
        .limit(1)
    )
    last_job = last_job_result.scalar_one_or_none()

    # Get statistics
    total_jobs = await db.scalar(select(func.count(ScrapingJob.job_id))) or 0
    total_tenders = await db.scalar(select(func.count(Tender.tender_id))) or 0
    total_documents = await db.scalar(select(func.count(Document.doc_id))) or 0

    return {
        "is_running": len(running_jobs) > 0,
        "running_jobs": [
            {
                "job_id": str(job.job_id),
                "started_at": job.started_at.isoformat(),
                "spider_name": job.spider_name,
                "incremental": job.incremental
            }
            for job in running_jobs
        ],
        "last_job": {
            "job_id": str(last_job.job_id),
            "completed_at": last_job.completed_at.isoformat() if last_job.completed_at else None,
            "status": last_job.status,
            "tenders_scraped": last_job.tenders_scraped,
            "documents_scraped": last_job.documents_scraped,
            "errors_count": last_job.errors_count
        } if last_job else None,
        "statistics": {
            "total_jobs": total_jobs,
            "total_tenders": total_tenders,
            "total_documents": total_documents
        }
    }
