"""
Clawd Monitoring API for nabavkidata.com
Provides a standardized status endpoint and webhook notification utility
for the Clawd VA monitoring system.

Security:
- Requires X-Monitor-Token header matching CLAWD_MONITOR_TOKEN env var

Endpoints:
- GET /clawd/status - App health, metrics, recent events, EC2 system stats
"""
from fastapi import APIRouter, HTTPException, Header, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import json
import logging
import os
import subprocess

import httpx

from database import get_db
from models import User, Subscription, Document

logger = logging.getLogger(__name__)

# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/clawd",
    tags=["Clawd Monitor"]
)


# ============================================================================
# AUTH HELPER
# ============================================================================

def _verify_monitor_token(x_monitor_token: Optional[str] = Header(None)):
    """Validate the X-Monitor-Token header against env var."""
    expected = os.getenv("CLAWD_MONITOR_TOKEN")
    if not expected or not x_monitor_token or x_monitor_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing monitor token"
        )


# ============================================================================
# SYSTEM METRICS HELPERS
# ============================================================================

def _get_ec2_system_metrics():
    """Read EC2 memory, disk, and CPU from /proc and df."""
    system = {}
    try:
        # Memory from /proc/meminfo (works on Linux)
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            lines = meminfo.read_text().splitlines()
            mem = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
            total_mb = mem.get("MemTotal", 0) // 1024
            available_mb = mem.get("MemAvailable", 0) // 1024
            used_mb = total_mb - available_mb
            system["memory"] = {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "available_mb": available_mb,
                "used_percent": round(used_mb / total_mb * 100, 1) if total_mb else 0,
            }
    except Exception:
        pass

    try:
        # Disk usage via os.statvfs (no subprocess needed)
        st = os.statvfs("/")
        total_gb = round(st.f_frsize * st.f_blocks / (1024**3), 1)
        free_gb = round(st.f_frsize * st.f_bavail / (1024**3), 1)
        used_gb = round(total_gb - free_gb, 1)
        system["disk"] = {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "used_percent": round(used_gb / total_gb * 100, 1) if total_gb else 0,
        }
    except Exception:
        pass

    try:
        # Load average from /proc/loadavg
        loadavg = Path("/proc/loadavg")
        if loadavg.exists():
            parts = loadavg.read_text().split()
            system["load_avg"] = {
                "1min": float(parts[0]),
                "5min": float(parts[1]),
                "15min": float(parts[2]),
            }
    except Exception:
        pass

    try:
        # Running processes summary
        result = subprocess.run(
            ["ps", "aux", "--sort=-%mem"],
            capture_output=True, text=True, timeout=5
        )
        scrapy_procs = []
        for line in result.stdout.splitlines():
            if "scrapy crawl" in line and "grep" not in line:
                parts = line.split()
                scrapy_procs.append({
                    "pid": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "cmd": " ".join(parts[10:])[:100],
                })
        system["scrapy_processes"] = scrapy_procs
    except Exception:
        system["scrapy_processes"] = []

    return system


def _get_pipeline_status():
    """Read document extraction and embedding pipeline progress from system_metrics.json."""
    try:
        metrics_path = Path("/var/log/nabavkidata/system_metrics.json")
        if metrics_path.exists():
            return json.loads(metrics_path.read_text())
    except Exception:
        pass
    return None


# ============================================================================
# STATUS ENDPOINT
# ============================================================================

@router.get("/status", dependencies=[Depends(_verify_monitor_token)])
async def clawd_status(db: AsyncSession = Depends(get_db)):
    """
    Standardized status endpoint for Clawd VA monitoring.

    Returns app health, key metrics, EC2 system stats, and recent events.
    """
    now = datetime.utcnow()
    since_24h = now - timedelta(hours=24)
    since_1h = now - timedelta(hours=1)

    health = {"database": False, "api": True, "scraper": False}
    metrics = {}

    # --- database health ---
    try:
        await db.execute(text("SELECT 1"))
        health["database"] = True
    except Exception:
        pass

    # --- new users (24h) ---
    try:
        new_users_24h = await db.scalar(
            select(func.count(User.user_id))
            .where(User.created_at >= since_24h)
        ) or 0
        metrics["new_users_24h"] = new_users_24h
    except Exception:
        metrics["new_users_24h"] = None

    # --- active subscriptions ---
    try:
        active_subs = await db.scalar(
            select(func.count(Subscription.subscription_id))
            .where(Subscription.status == "active")
        ) or 0
        metrics["active_subscriptions"] = active_subs
    except Exception:
        metrics["active_subscriptions"] = None

    # --- scraper status (from marker file + health.json, not DB) ---
    try:
        # Check marker file (touched by run-cron.sh after successful scraper runs)
        marker_found = False
        for marker_path in ["/tmp/nabavkidata_scraper_last_run", "/var/log/nabavkidata/scraper_last_run"]:
            marker = Path(marker_path)
            if marker.exists():
                mtime = marker.stat().st_mtime
                last_run_dt = datetime.utcfromtimestamp(mtime)
                metrics["scraper_last_run"] = last_run_dt.isoformat()
                age_hours = (now - last_run_dt).total_seconds() / 3600
                metrics["scraper_status"] = "ok" if age_hours < 26 else "stale"
                health["scraper"] = age_hours < 26
                marker_found = True
                break

        # Read health.json for detailed scraper status
        health_path = Path("/var/log/nabavkidata/health.json")
        if health_path.exists():
            health_data = json.loads(health_path.read_text())
            metrics["scraper_dataset"] = health_data.get("dataset")
            metrics["scraper_last_status"] = health_data.get("status")
            metrics["total_tenders"] = health_data.get("db", {}).get("total_tenders")

            # Use health.json as fallback if marker file is missing
            if not marker_found and health_data.get("finished_at"):
                metrics["scraper_last_run"] = health_data["finished_at"]
                finished = datetime.fromisoformat(health_data["finished_at"].replace("Z", "+00:00"))
                age_hours = (now - finished.replace(tzinfo=None)).total_seconds() / 3600
                metrics["scraper_status"] = "ok" if age_hours < 26 else "stale"
                health["scraper"] = health_data.get("status") == "success" and age_hours < 26

        if not marker_found and "scraper_last_run" not in metrics:
            metrics["scraper_last_run"] = None
            metrics["scraper_status"] = "unknown"
    except Exception:
        metrics["scraper_last_run"] = None
        metrics["scraper_status"] = "error"

    # --- documents processed (24h) ---
    try:
        docs_24h = await db.scalar(
            select(func.count(Document.doc_id))
            .where(Document.uploaded_at >= since_24h)
        ) or 0
        metrics["documents_processed_24h"] = docs_24h
    except Exception:
        metrics["documents_processed_24h"] = None

    # --- error rate (1h) — ratio of failed scraping jobs in the last hour ---
    try:
        total_1h = await db.scalar(
            select(func.count(ScrapingJob.job_id))
            .where(ScrapingJob.started_at >= since_1h)
        ) or 0
        failed_1h = await db.scalar(
            select(func.count(ScrapingJob.job_id))
            .where(ScrapingJob.started_at >= since_1h)
            .where(ScrapingJob.status == "failed")
        ) or 0
        metrics["error_rate_1h"] = round(failed_1h / total_1h, 2) if total_1h > 0 else 0.0
    except Exception:
        metrics["error_rate_1h"] = None

    # --- EC2 system metrics (memory, disk, load, processes) ---
    system = _get_ec2_system_metrics()

    # --- system metrics from watchdog (updated every 5 min) ---
    watchdog_metrics = _get_pipeline_status()
    if watchdog_metrics:
        # Merge watchdog data into system if /proc wasn't available
        if "memory" not in system and "memory" in watchdog_metrics:
            system["memory"] = watchdog_metrics["memory"]
        if "disk" not in system and "disk" in watchdog_metrics:
            system["disk"] = watchdog_metrics["disk"]
        if "load_avg" not in system and "load_avg" in watchdog_metrics:
            system["load_avg"] = watchdog_metrics["load_avg"]
        if "scrapy_processes" in watchdog_metrics:
            system["scrapy_processes"] = watchdog_metrics["scrapy_processes"]
        system["watchdog_updated_at"] = watchdog_metrics.get("timestamp")

    # --- recent events: new user sign-ups in last 24h ---
    recent_events = []
    try:
        recent_users_result = await db.execute(
            select(User)
            .where(User.created_at >= since_24h)
            .order_by(User.created_at.desc())
            .limit(10)
        )
        for user in recent_users_result.scalars().all():
            recent_events.append({
                "type": "new_user",
                "email": user.email,
                "name": user.full_name,
                "at": user.created_at.isoformat() if user.created_at else None
            })
    except Exception:
        pass

    overall_status = "healthy" if all(health.values()) else "degraded"

    return {
        "app": "nabavkidata",
        "status": overall_status,
        "timestamp": now.isoformat(),
        "health": health,
        "metrics": metrics,
        "system": system,
        "recent_events": recent_events
    }


# ============================================================================
# WEBHOOK NOTIFICATION UTILITY
# ============================================================================

async def notify_clawd(event_type: str, data: dict):
    """
    Fire-and-forget POST to Clawd webhook.

    Sends a JSON payload to CLAWD_WEBHOOK_URL with the event details.
    Never raises — all exceptions are silently logged.
    """
    webhook_url = os.getenv("CLAWD_WEBHOOK_URL")
    token = os.getenv("CLAWD_MONITOR_TOKEN")
    if not webhook_url:
        return

    payload = {
        "app": "nabavkidata",
        "type": event_type,
        **data,
        "at": datetime.utcnow().isoformat()
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                webhook_url,
                json=payload,
                headers={"X-Monitor-Token": token or ""}
            )
    except Exception as e:
        logger.debug(f"notify_clawd failed: {e}")
