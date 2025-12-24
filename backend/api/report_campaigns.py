"""
Report Campaign API Endpoints
Admin endpoints for managing report-first outreach campaigns
"""
import os
import json
import uuid
import hmac
import hashlib
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr

from database import get_db_pool
from services.report_generator import ReportGenerator, generate_reports_for_campaign
from services.email_enrichment import (
    EmailEnrichmentService, select_top_companies, enrich_missing_emails
)
from services.campaign_sender import (
    CampaignSender, handle_postmark_webhook, handle_unsubscribe,
    generate_unsubscribe_token, verify_unsubscribe_token
)

router = APIRouter(prefix="/api/report-campaigns", tags=["Report Campaigns"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateCampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    min_participations: int = 5
    min_wins: int = 2
    lookback_days: int = 365
    missed_tenders_days: int = 90
    attach_pdf_first_n: int = 20
    daily_limit: int = 100
    hourly_limit: int = 20
    followup_1_days: int = 3
    followup_2_days: int = 7


class CampaignResponse(BaseModel):
    id: str
    name: str
    status: str
    total_targets: int
    emails_sent: int
    emails_opened: int
    emails_clicked: int
    replies_received: int
    conversions: int
    created_at: str


class TargetStatsResponse(BaseModel):
    total: int
    pending: int
    report_generated: int
    sent: int
    delivered: int
    opened: int
    clicked: int
    replied: int
    converted: int
    unsubscribed: int
    bounced: int


# ============================================================================
# CAMPAIGN MANAGEMENT
# ============================================================================

@router.post("/create")
async def create_campaign(request: CreateCampaignRequest):
    """Create a new report campaign"""
    pool = await get_db_pool()

    settings = {
        "min_participations": request.min_participations,
        "min_wins": request.min_wins,
        "lookback_days": request.lookback_days,
        "missed_tenders_days": request.missed_tenders_days,
        "attach_pdf_first_n": request.attach_pdf_first_n,
        "daily_limit": request.daily_limit,
        "hourly_limit": request.hourly_limit,
        "followup_1_days": request.followup_1_days,
        "followup_2_days": request.followup_2_days,
        "report_valid_days": 14
    }

    async with pool.acquire() as conn:
        campaign_id = uuid.uuid4()
        await conn.execute("""
            INSERT INTO report_campaigns (id, name, description, settings, status)
            VALUES ($1, $2, $3, $4, 'draft')
        """, campaign_id, request.name, request.description, json.dumps(settings))

    return {
        "success": True,
        "campaign_id": str(campaign_id),
        "name": request.name,
        "settings": settings
    }


@router.get("/list")
async def list_campaigns(
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100)
):
    """List all campaigns"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT * FROM campaign_stats_view WHERE status = $1
                ORDER BY created_at DESC LIMIT $2
            """, status, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM campaign_stats_view
                ORDER BY created_at DESC LIMIT $1
            """, limit)

    return {"campaigns": [dict(r) for r in rows]}


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign details"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("""
            SELECT * FROM report_campaigns WHERE id = $1
        """, uuid.UUID(campaign_id))

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Get target stats
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'report_generated' THEN 1 END) as report_generated,
                COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent,
                COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered,
                COUNT(CASE WHEN status = 'opened' THEN 1 END) as opened,
                COUNT(CASE WHEN status = 'clicked' THEN 1 END) as clicked,
                COUNT(CASE WHEN status = 'replied' THEN 1 END) as replied,
                COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted,
                COUNT(CASE WHEN status = 'unsubscribed' THEN 1 END) as unsubscribed,
                COUNT(CASE WHEN status = 'bounced' THEN 1 END) as bounced
            FROM campaign_targets WHERE campaign_id = $1
        """, uuid.UUID(campaign_id))

    return {
        "campaign": dict(campaign),
        "target_stats": dict(stats) if stats else {}
    }


@router.post("/{campaign_id}/select-targets")
async def select_campaign_targets(
    campaign_id: str,
    limit: int = Query(default=100, le=500),
    enrich_emails: bool = Query(default=True)
):
    """Select top companies as campaign targets"""
    pool = await get_db_pool()

    # Get campaign settings
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("""
            SELECT settings FROM report_campaigns WHERE id = $1 AND status = 'draft'
        """, uuid.UUID(campaign_id))

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found or not in draft status")

        settings = json.loads(campaign['settings']) if campaign['settings'] else {}

    # Select top companies
    companies = await select_top_companies(
        pool=pool,
        min_participations=settings.get("min_participations", 5),
        min_wins=settings.get("min_wins", 2),
        lookback_days=settings.get("lookback_days", 365),
        limit=limit
    )

    # Enrich missing emails if requested
    if enrich_emails:
        companies = await enrich_missing_emails(pool, companies)

    # Filter to companies with emails
    companies_with_email = [c for c in companies if c.get("email")]

    # Insert as campaign targets
    async with pool.acquire() as conn:
        inserted = 0
        for i, company in enumerate(companies_with_email):
            # Alternate A/B variant
            variant = "A" if i % 2 == 0 else "B"

            try:
                await conn.execute("""
                    INSERT INTO campaign_targets (
                        campaign_id, company_name, company_tax_id, company_id,
                        email, subject_variant, stats, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                    ON CONFLICT DO NOTHING
                """,
                    uuid.UUID(campaign_id),
                    company["company_name"],
                    company.get("company_tax_id"),
                    uuid.UUID(company["company_id"]) if company.get("company_id") else None,
                    company["email"],
                    variant,
                    json.dumps({
                        "participations": company["participations"],
                        "wins": company["wins"],
                        "total_value": company["total_value"]
                    })
                )
                inserted += 1
            except Exception as e:
                pass  # Skip duplicates

        # Update campaign total
        await conn.execute("""
            UPDATE report_campaigns
            SET total_targets = $1, updated_at = NOW()
            WHERE id = $2
        """, inserted, uuid.UUID(campaign_id))

    return {
        "success": True,
        "campaign_id": campaign_id,
        "companies_found": len(companies),
        "companies_with_email": len(companies_with_email),
        "targets_added": inserted,
        "missing_email": len(companies) - len(companies_with_email)
    }


@router.post("/{campaign_id}/generate-reports")
async def generate_campaign_reports(
    campaign_id: str,
    limit: int = Query(default=50, le=200)
):
    """Generate PDF reports for campaign targets"""
    pool = await get_db_pool()

    # Verify campaign exists
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow("""
            SELECT id FROM report_campaigns WHERE id = $1
        """, uuid.UUID(campaign_id))

        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

    # Generate reports
    result = await generate_reports_for_campaign(pool, campaign_id, limit)

    return {
        "success": True,
        "campaign_id": campaign_id,
        "reports_generated": result["success"],
        "reports_failed": result["failed"],
        "total_processed": result["total"]
    }


@router.post("/{campaign_id}/activate")
async def activate_campaign(campaign_id: str):
    """Activate a campaign for sending"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        # Check campaign exists and has targets with reports
        result = await conn.fetchrow("""
            SELECT
                rc.status,
                COUNT(ct.id) as total_targets,
                COUNT(CASE WHEN ct.report_id IS NOT NULL THEN 1 END) as with_reports
            FROM report_campaigns rc
            LEFT JOIN campaign_targets ct ON rc.id = ct.campaign_id
            WHERE rc.id = $1
            GROUP BY rc.status
        """, uuid.UUID(campaign_id))

        if not result:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if result['total_targets'] == 0:
            raise HTTPException(status_code=400, detail="No targets in campaign")

        if result['with_reports'] == 0:
            raise HTTPException(status_code=400, detail="No reports generated yet")

        # Activate
        await conn.execute("""
            UPDATE report_campaigns
            SET status = 'active', started_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """, uuid.UUID(campaign_id))

    return {
        "success": True,
        "campaign_id": campaign_id,
        "total_targets": result['total_targets'],
        "ready_to_send": result['with_reports']
    }


@router.post("/{campaign_id}/send-batch")
async def send_campaign_batch(
    campaign_id: str,
    batch_size: int = Query(default=10, le=50),
    dry_run: bool = Query(default=False)
):
    """Send a batch of emails"""
    pool = await get_db_pool()

    sender = CampaignSender(pool)
    try:
        result = await sender.send_campaign_batch(campaign_id, batch_size, dry_run)
    finally:
        await sender.close()

    return result


@router.post("/{campaign_id}/send-followups")
async def send_campaign_followups(
    campaign_id: str,
    dry_run: bool = Query(default=False)
):
    """Send follow-up emails to eligible targets"""
    pool = await get_db_pool()

    sender = CampaignSender(pool)
    try:
        result = await sender.send_followups(campaign_id, dry_run)
    finally:
        await sender.close()

    return result


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause an active campaign"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE report_campaigns
            SET status = 'paused', updated_at = NOW()
            WHERE id = $1 AND status = 'active'
        """, uuid.UUID(campaign_id))

    return {"success": True, "status": "paused"}


@router.get("/{campaign_id}/targets")
async def list_campaign_targets(
    campaign_id: str,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0
):
    """List campaign targets"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT
                    id, company_name, email, status, subject_variant,
                    sequence_step, initial_sent_at, stats
                FROM campaign_targets
                WHERE campaign_id = $1 AND status = $2
                ORDER BY created_at
                LIMIT $3 OFFSET $4
            """, uuid.UUID(campaign_id), status, limit, offset)
        else:
            rows = await conn.fetch("""
                SELECT
                    id, company_name, email, status, subject_variant,
                    sequence_step, initial_sent_at, stats
                FROM campaign_targets
                WHERE campaign_id = $1
                ORDER BY created_at
                LIMIT $2 OFFSET $3
            """, uuid.UUID(campaign_id), limit, offset)

    return {"targets": [dict(r) for r in rows]}


@router.get("/{campaign_id}/events")
async def list_campaign_events(
    campaign_id: str,
    event_type: Optional[str] = None,
    limit: int = Query(default=100, le=500)
):
    """List campaign events"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        if event_type:
            rows = await conn.fetch("""
                SELECT * FROM outreach_events
                WHERE campaign_id = $1 AND event_type = $2
                ORDER BY created_at DESC LIMIT $3
            """, uuid.UUID(campaign_id), event_type, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM outreach_events
                WHERE campaign_id = $1
                ORDER BY created_at DESC LIMIT $2
            """, uuid.UUID(campaign_id), limit)

    return {"events": [dict(r) for r in rows]}


# ============================================================================
# REPORT DOWNLOAD
# ============================================================================

REPORT_SECRET = os.getenv("REPORT_SECRET", "nabavki-report-secret-2025")

@router.get("/report/{report_id}")
async def download_report(
    report_id: str,
    expires: int = Query(...),
    sig: str = Query(...)
):
    """Download a report PDF with signed URL verification"""
    # Verify signature
    data = f"{report_id}:{expires}:{REPORT_SECRET}"
    expected_sig = hashlib.sha256(data.encode()).hexdigest()[:16]

    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=403, detail="Невалиден линк")

    if expires < int(datetime.utcnow().timestamp()):
        raise HTTPException(status_code=410, detail="Линкот е истечен")

    # Get report
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        report = await conn.fetchrow("""
            SELECT pdf_path, company_name FROM generated_reports WHERE id = $1
        """, uuid.UUID(report_id))

        if not report or not report['pdf_path']:
            raise HTTPException(status_code=404, detail="Извештајот не е пронајден")

        if not Path(report['pdf_path']).exists():
            raise HTTPException(status_code=404, detail="PDF датотеката не е пронајдена")

    filename = f"Извештај-{report['company_name'][:30]}.pdf"
    return FileResponse(
        report['pdf_path'],
        media_type='application/pdf',
        filename=filename
    )


# ============================================================================
# WEBHOOKS
# ============================================================================

POSTMARK_WEBHOOK_SECRET = os.getenv("POSTMARK_WEBHOOK_SECRET", "")

@router.post("/webhook/postmark")
async def postmark_webhook(request: Request):
    """Handle Postmark webhook events"""
    body = await request.body()

    # Verify signature if configured
    if POSTMARK_WEBHOOK_SECRET:
        signature = request.headers.get("X-Postmark-Signature", "")
        expected = hmac.new(
            POSTMARK_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

    event_data = await request.json()
    pool = await get_db_pool()

    result = await handle_postmark_webhook(pool, event_data)
    return result


# ============================================================================
# UNSUBSCRIBE
# ============================================================================

@router.get("/unsubscribe")
async def unsubscribe_get(
    email: str = Query(...),
    token: str = Query(...)
):
    """Handle unsubscribe via GET request (from email link)"""
    pool = await get_db_pool()
    result = await handle_unsubscribe(pool, email, token, source="email_link")

    if result.get("success"):
        return Response(
            content="""
<!DOCTYPE html>
<html lang="mk">
<head>
    <meta charset="UTF-8">
    <title>Одјава - NabavkiData</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; text-align: center; }
        .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="success">Успешно се одјавивте</div>
    <p>Нема повеќе да добивате маркетинг пораки од NabavkiData.</p>
    <p><a href="https://nabavkidata.com">Назад на NabavkiData</a></p>
</body>
</html>
            """,
            media_type="text/html"
        )
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Грешка"))


@router.post("/unsubscribe")
async def unsubscribe_post(
    email: EmailStr,
    token: str
):
    """Handle unsubscribe via POST request"""
    pool = await get_db_pool()
    return await handle_unsubscribe(pool, email, token, source="api")


# ============================================================================
# ADMIN VIEWS
# ============================================================================

@router.get("/admin/invoice-requests")
async def list_invoice_requests(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200)
):
    """List invoice requests from email replies"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT * FROM invoice_requests
                WHERE status = $1
                ORDER BY created_at DESC LIMIT $2
            """, status, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM invoice_requests
                ORDER BY created_at DESC LIMIT $1
            """, limit)

    return {"requests": [dict(r) for r in rows]}


@router.get("/admin/suppression-list")
async def list_suppressed(
    reason: Optional[str] = None,
    limit: int = Query(default=100, le=500)
):
    """List suppressed emails"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        if reason:
            rows = await conn.fetch("""
                SELECT email, reason, source, created_at
                FROM suppression_list
                WHERE reason = $1
                ORDER BY created_at DESC LIMIT $2
            """, reason, limit)
        else:
            rows = await conn.fetch("""
                SELECT email, reason, source, created_at
                FROM suppression_list
                ORDER BY created_at DESC LIMIT $1
            """, limit)

    return {"suppressed": [dict(r) for r in rows]}


@router.get("/admin/rate-limits")
async def get_rate_limits(campaign_id: Optional[str] = None):
    """Get current sending rate status"""
    pool = await get_db_pool()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    async with pool.acquire() as conn:
        daily = await conn.fetchval("""
            SELECT COUNT(*) FROM outreach_events
            WHERE event_type = 'sent' AND created_at >= $1
        """, today_start)

        hourly = await conn.fetchval("""
            SELECT COUNT(*) FROM outreach_events
            WHERE event_type = 'sent' AND created_at >= $1
        """, hour_start)

    return {
        "daily_sent": daily or 0,
        "daily_limit": 100,
        "hourly_sent": hourly or 0,
        "hourly_limit": 20,
        "can_send": (daily or 0) < 100 and (hourly or 0) < 20
    }


@router.get("/admin/enrichment-queue")
async def list_enrichment_queue(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200)
):
    """List email enrichment queue"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT * FROM email_enrichment_queue
                WHERE status = $1
                ORDER BY updated_at DESC LIMIT $2
            """, status, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM email_enrichment_queue
                ORDER BY updated_at DESC LIMIT $1
            """, limit)

    return {"queue": [dict(r) for r in rows]}
