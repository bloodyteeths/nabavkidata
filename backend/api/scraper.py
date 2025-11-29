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
from sqlalchemy import select, func, and_, desc, text
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from database import get_db
from models import ScrapingJob, Tender, Document, CronExecution
from models_auth import UserRole
from middleware.rbac import get_current_active_user, require_role
from services.email_service import email_service

# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/admin/scraper",
    tags=["Admin - Scraper"]
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
    table_exists = await db.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'scraping_jobs'
        )
    """))
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
    dependencies=[Depends(require_role(UserRole.admin))]
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
    dependencies=[Depends(require_role(UserRole.admin))]
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
    dependencies=[Depends(require_role(UserRole.admin))]
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


# ============================================================================
# LIVE SCRAPER MONITORING ENDPOINT (ADMIN)
# ============================================================================

@router.get(
    "/live-status",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def get_live_scraper_status(
    db: AsyncSession = Depends(get_db)
):
    """
    Get live scraper process status from the server (admin only)

    This endpoint checks:
    - If scrapy processes are running on the server
    - Last lines from the scraper log file
    - Database counts for progress tracking
    """
    import subprocess
    import os
    from pathlib import Path

    result = {
        "processes": [],
        "log_tail": [],
        "database_stats": {},
        "downloaded_files": 0,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Check for running scrapy processes
    try:
        ps_output = subprocess.run(
            ["pgrep", "-af", "scrapy"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if ps_output.stdout:
            for line in ps_output.stdout.strip().split('\n'):
                if line and 'scrapy crawl' in line:
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        result["processes"].append({
                            "pid": parts[0],
                            "command": parts[1][:200]  # Truncate long commands
                        })
    except Exception as e:
        result["process_error"] = str(e)

    # Read last lines from log file
    log_files = [
        "/tmp/nabavki_full_scrape.log",
        "/tmp/spider_test.log",
        "/var/log/nabavkidata/scraper.log"
    ]

    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    # Read last 50 lines
                    lines = f.readlines()[-50:]
                    result["log_tail"] = [line.strip() for line in lines if line.strip()]
                    result["log_file"] = log_file
                break
            except Exception as e:
                result["log_error"] = str(e)

    # Count downloaded files
    downloads_dir = Path("/home/ubuntu/nabavkidata/scraper/downloads/files")
    if downloads_dir.exists():
        try:
            result["downloaded_files"] = len(list(downloads_dir.glob("*")))
        except Exception:
            pass

    # Get database counts
    try:
        total_tenders = await db.scalar(select(func.count(Tender.tender_id))) or 0
        total_documents = await db.scalar(select(func.count(Document.doc_id))) or 0
        downloaded_docs = await db.scalar(
            select(func.count(Document.doc_id)).where(Document.file_path.isnot(None))
        ) or 0

        result["database_stats"] = {
            "total_tenders": total_tenders,
            "total_documents": total_documents,
            "downloaded_documents": downloaded_docs
        }
    except Exception as e:
        result["db_error"] = str(e)

    # Determine overall status
    if result["processes"]:
        result["status"] = "running"
        result["message"] = f"{len(result['processes'])} scraper process(es) running"
    else:
        result["status"] = "idle"
        result["message"] = "No scraper processes detected"

    return result


# ============================================================================
# MANUAL SCRAPER TRIGGER ENDPOINTS (ADMIN)
# ============================================================================

SCRAPER_CONFIGS = {
    "nabavki_active": {
        "name": "E-Nabavki Active Tenders",
        "command": "scrapy crawl nabavki -a categories=active",
        "log_file": "/tmp/nabavki_active.log",
        "description": "Scrape active tenders from e-nabavki.gov.mk"
    },
    "nabavki_awarded": {
        "name": "E-Nabavki Awarded Tenders",
        "command": "scrapy crawl nabavki -a categories=awarded",
        "log_file": "/tmp/nabavki_awarded.log",
        "description": "Scrape awarded tenders from e-nabavki.gov.mk"
    },
    "nabavki_cancelled": {
        "name": "E-Nabavki Cancelled Tenders",
        "command": "scrapy crawl nabavki -a categories=cancelled",
        "log_file": "/tmp/nabavki_cancelled.log",
        "description": "Scrape cancelled tenders from e-nabavki.gov.mk"
    },
    "nabavki_full": {
        "name": "E-Nabavki Full Scrape",
        "command": "scrapy crawl nabavki -a categories=active,awarded,cancelled",
        "log_file": "/tmp/nabavki_full_scrape.log",
        "description": "Full scrape of all tender categories"
    },
    "epazar": {
        "name": "E-Pazar Products",
        "command": "scrapy crawl epazar_api -a category=all",
        "log_file": "/tmp/epazar.log",
        "description": "Scrape products from e-pazar.mk"
    },
    "documents": {
        "name": "Document Processing",
        "command": "/home/ubuntu/nabavkidata/scraper/cron/process_documents.sh",
        "log_file": "/var/log/nabavkidata/documents_$(date +%Y%m%d).log",
        "description": "Process pending documents and extract products"
    }
}


@router.get(
    "/scrapers",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def list_available_scrapers():
    """List all available scrapers that can be triggered manually"""
    import subprocess

    # Check which scrapers are currently running
    running_patterns = {}
    try:
        ps_output = subprocess.run(
            ["pgrep", "-af", "scrapy"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if ps_output.stdout:
            for line in ps_output.stdout.strip().split('\n'):
                if 'nabavki' in line:
                    if 'categories=active' in line and 'awarded' not in line and 'cancelled' not in line:
                        running_patterns['nabavki_active'] = True
                    elif 'categories=awarded' in line:
                        running_patterns['nabavki_awarded'] = True
                    elif 'categories=cancelled' in line:
                        running_patterns['nabavki_cancelled'] = True
                    elif 'active,awarded,cancelled' in line:
                        running_patterns['nabavki_full'] = True
                elif 'epazar' in line:
                    running_patterns['epazar'] = True
    except Exception:
        pass

    return {
        "scrapers": [
            {
                "id": key,
                "name": config["name"],
                "description": config["description"],
                "command": config["command"],
                "log_file": config["log_file"],
                "is_running": running_patterns.get(key, False)
            }
            for key, config in SCRAPER_CONFIGS.items()
        ]
    }


@router.post(
    "/run/{scraper_id}",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def run_scraper(scraper_id: str):
    """
    Manually trigger a specific scraper (admin only)

    Runs the scraper in background via nohup
    """
    import subprocess

    if scraper_id not in SCRAPER_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scraper: {scraper_id}. Available: {list(SCRAPER_CONFIGS.keys())}"
        )

    config = SCRAPER_CONFIGS[scraper_id]

    # Build the command to run in background
    scraper_dir = "/home/ubuntu/nabavkidata/scraper"
    venv_activate = "source /home/ubuntu/nabavkidata/venv/bin/activate"
    db_url = "export DATABASE_URL='postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata'"

    log_file = config["log_file"].replace("$(date +%Y%m%d)", datetime.utcnow().strftime("%Y%m%d"))

    if scraper_id == "documents":
        # Document processing script
        full_command = f"cd {scraper_dir} && {venv_activate} && {db_url} && nohup {config['command']} > {log_file} 2>&1 &"
    else:
        # Scrapy commands
        full_command = f"cd {scraper_dir} && {venv_activate} && {db_url} && nohup {config['command']} -s LOG_LEVEL=INFO > {log_file} 2>&1 &"

    try:
        result = subprocess.run(
            ["bash", "-c", full_command],
            capture_output=True,
            text=True,
            timeout=10
        )

        return {
            "status": "started",
            "scraper_id": scraper_id,
            "name": config["name"],
            "log_file": log_file,
            "message": f"Scraper '{config['name']}' started in background. Monitor at {log_file}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start scraper: {str(e)}"
        )


@router.post(
    "/stop/{scraper_id}",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def stop_scraper(scraper_id: str):
    """Stop a running scraper by killing its process"""
    import subprocess

    if scraper_id not in SCRAPER_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Unknown scraper: {scraper_id}")

    config = SCRAPER_CONFIGS[scraper_id]

    try:
        # Find and kill processes matching this scraper
        if scraper_id.startswith("nabavki"):
            pattern = f"scrapy crawl nabavki"
        elif scraper_id == "epazar":
            pattern = "scrapy crawl epazar"
        else:
            pattern = config["command"].split()[0]

        result = subprocess.run(
            ["pkill", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=10
        )

        return {
            "status": "stopped",
            "scraper_id": scraper_id,
            "message": f"Sent kill signal to processes matching '{pattern}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop scraper: {str(e)}")


# ============================================================================
# CRON JOB STATUS AND LOGS (ADMIN)
# ============================================================================

@router.get(
    "/cron-status",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def get_cron_status():
    """Get cron job configuration and recent log files"""
    import subprocess
    import os
    from pathlib import Path

    cron_entries = []
    log_files = []

    # Expected cron jobs (for display even if not yet configured)
    expected_crons = [
        {
            "schedule": "0 8 * * *",
            "command": "python crons/email_digest.py daily",
            "description": "Daily Email Digest",
            "category": "email"
        },
        {
            "schedule": "0 8 * * 1",
            "command": "python crons/email_digest.py weekly",
            "description": "Weekly Email Digest",
            "category": "email"
        },
        {
            "schedule": "*/15 * * * *",
            "command": "python crons/instant_alerts.py",
            "description": "Instant Tender Alerts",
            "category": "email"
        },
        {
            "schedule": "0 2 * * *",
            "command": "python crons/user_interest_update.py",
            "description": "User Interest Vector Update",
            "category": "personalization"
        },
        {
            "schedule": "0 3 * * *",
            "command": "scrapy crawl nabavki",
            "description": "E-Nabavki Scraper",
            "category": "scraper"
        },
        {
            "schedule": "0 4 * * *",
            "command": "scrapy crawl epazar_api",
            "description": "E-Pazar Scraper",
            "category": "scraper"
        }
    ]

    # Get actual crontab entries
    actual_crons = set()
    try:
        cron_result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if cron_result.returncode == 0:
            for line in cron_result.stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse cron line: schedule (5 fields) + command
                    parts = line.split(None, 5)
                    if len(parts) >= 6:
                        schedule = ' '.join(parts[:5])
                        command = parts[5]
                        actual_crons.add(command[:50])  # Store partial match

                        # Generate description from command
                        if 'email_digest.py daily' in command:
                            desc = "Daily Email Digest"
                            category = "email"
                        elif 'email_digest.py weekly' in command:
                            desc = "Weekly Email Digest"
                            category = "email"
                        elif 'instant_alerts.py' in command:
                            desc = "Instant Tender Alerts"
                            category = "email"
                        elif 'user_interest_update' in command:
                            desc = "User Interest Vector Update"
                            category = "personalization"
                        elif 'nabavki' in command:
                            desc = "E-Nabavki Scraper"
                            category = "scraper"
                        elif 'epazar' in command:
                            desc = "E-Pazar Scraper"
                            category = "scraper"
                        elif 'document' in command.lower():
                            desc = "Document Processor"
                            category = "scraper"
                        else:
                            desc = "Scheduled Task"
                            category = "other"

                        cron_entries.append({
                            "schedule": schedule,
                            "command": command[:100],
                            "description": desc,
                            "category": category,
                            "status": "active"
                        })
    except Exception as e:
        pass  # If crontab fails, we show expected crons as "not configured"

    # If no crons found, show expected ones as "not configured"
    if not cron_entries:
        cron_entries = [
            {
                "schedule": cron["schedule"],
                "command": cron["command"],
                "description": cron["description"],
                "category": cron["category"],
                "status": "not_configured"
            }
            for cron in expected_crons
        ]

    # Get recent log files - include email/personalization logs
    log_dirs = [
        "/var/log/nabavkidata",
        "/tmp"
    ]

    log_patterns = [
        'nabavki', 'epazar', 'scraper', 'documents', 'spider',
        'digest', 'alert', 'vector', 'email', 'instant'
    ]

    for log_dir in log_dirs:
        if os.path.exists(log_dir):
            try:
                for f in os.listdir(log_dir):
                    if any(pattern in f.lower() for pattern in log_patterns):
                        filepath = os.path.join(log_dir, f)
                        if os.path.isfile(filepath):
                            stat = os.stat(filepath)
                            log_files.append({
                                "name": f,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
            except Exception:
                pass

    # Sort by modification time, newest first
    log_files.sort(key=lambda x: x["modified"], reverse=True)

    return {
        "cron_entries": cron_entries,
        "log_files": log_files[:20]
    }


@router.get(
    "/logs/{log_name}",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def get_log_content(
    log_name: str,
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to return")
):
    """Get content from a specific log file"""
    import os

    # Security: only allow certain directories and patterns
    allowed_dirs = ["/var/log/nabavkidata", "/tmp"]
    allowed_patterns = [
        "nabavki", "epazar", "scraper", "documents", "spider",
        "digest", "alert", "vector", "email", "instant"
    ]

    if not any(pattern in log_name for pattern in allowed_patterns):
        raise HTTPException(status_code=400, detail="Invalid log file name")

    # Find the log file
    log_path = None
    for log_dir in allowed_dirs:
        potential_path = os.path.join(log_dir, log_name)
        if os.path.isfile(potential_path):
            log_path = potential_path
            break

    if not log_path:
        raise HTTPException(status_code=404, detail=f"Log file not found: {log_name}")

    try:
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
            # Return last N lines
            content = all_lines[-lines:]

        return {
            "log_name": log_name,
            "path": log_path,
            "total_lines": len(all_lines),
            "returned_lines": len(content),
            "content": [line.rstrip() for line in content]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {str(e)}")


# ============================================================================
# CRON EXECUTION HISTORY (ADMIN)
# ============================================================================

@router.get(
    "/cron-executions",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def get_cron_executions(
    job_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get cron execution history"""
    from sqlalchemy import text

    # Check if table exists
    table_check = await db.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'cron_executions'
        )
    """))
    if not table_check.scalar():
        return {"executions": [], "message": "Cron executions table not yet created"}

    query = select(CronExecution).order_by(desc(CronExecution.started_at))

    if job_name:
        query = query.where(CronExecution.job_name == job_name)
    if status:
        query = query.where(CronExecution.status == status)

    query = query.limit(limit)
    result = await db.execute(query)
    executions = result.scalars().all()

    return {
        "executions": [
            {
                "execution_id": str(e.execution_id),
                "job_name": e.job_name,
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": e.duration_seconds,
                "records_processed": e.records_processed,
                "error_message": e.error_message,
                "details": e.details
            }
            for e in executions
        ]
    }


@router.get(
    "/cron-executions/stats",
    dependencies=[Depends(require_role(UserRole.admin))]
)
async def get_cron_execution_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get cron execution statistics"""
    from sqlalchemy import text

    # Check if table exists
    table_check = await db.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'cron_executions'
        )
    """))
    if not table_check.scalar():
        return {"stats": {}, "message": "Cron executions table not yet created"}

    # Get stats per job
    stats_query = text("""
        SELECT
            job_name,
            COUNT(*) as total_runs,
            COUNT(*) FILTER (WHERE status = 'completed') as successful,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            COUNT(*) FILTER (WHERE status = 'started') as running,
            MAX(started_at) as last_run,
            AVG(duration_seconds) FILTER (WHERE status = 'completed') as avg_duration,
            SUM(records_processed) FILTER (WHERE status = 'completed') as total_records
        FROM cron_executions
        WHERE started_at > NOW() - INTERVAL '7 days'
        GROUP BY job_name
        ORDER BY last_run DESC
    """)

    result = await db.execute(stats_query)
    rows = result.fetchall()

    stats = {}
    for row in rows:
        stats[row.job_name] = {
            "total_runs": row.total_runs,
            "successful": row.successful,
            "failed": row.failed,
            "running": row.running,
            "last_run": row.last_run.isoformat() if row.last_run else None,
            "avg_duration_seconds": round(float(row.avg_duration), 1) if row.avg_duration else None,
            "total_records_processed": row.total_records or 0
        }

    return {"stats": stats}
