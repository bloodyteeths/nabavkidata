"""
nabavkidata.com Backend API
FastAPI REST server
"""
from dotenv import load_dotenv
load_dotenv()  # Load .env file before any other imports

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pathlib import Path
import json
import os

from database import init_db, close_db, get_db
from db_pool import get_asyncpg_pool, close_asyncpg_pool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api import tenders, documents, rag, auth, billing, admin, fraud_endpoints, personalization, scraper, stripe_webhook, entities, analytics, suppliers, tender_details, products, epazar, ai, cpv_codes, saved_searches, market_analytics, pricing, competitors, competitor_tracking, alerts, briefings, notifications, corruption, risk, api_keys, insights, contact, explainability, collusion, outreach, referrals, whistleblower, clawd_monitor, chat_sessions
# Note: report_campaigns commented out - missing weasyprint on server
# from api import report_campaigns
from middleware.fraud import FraudPreventionMiddleware
from middleware.rate_limit import RateLimitMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

app = FastAPI(
    title="nabavkidata.com API",
    description="Macedonian Tender Intelligence Platform - AI-powered tender search and analysis",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS Middleware - must be first
# Security: Explicitly list allowed methods and headers (no wildcards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://nabavkidata.com",
        "https://www.nabavkidata.com",
        "https://nabavkidata.vercel.app",
        "https://api.nabavkidata.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Fingerprint", "X-Requested-With", "X-CSRF-Token", "Accept", "Accept-Language", "Content-Language", "X-API-Key", "X-Auth-Token"],
)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Rate Limiting - applied to all endpoints
app.add_middleware(RateLimitMiddleware)

# Fraud Prevention - checks for abuse patterns
app.add_middleware(FraudPreventionMiddleware)


# Startup/Shutdown Events
@app.on_event("startup")
async def startup():
    """Initialize database connection on startup"""
    await init_db()
    pool = await get_asyncpg_pool()
    print("✓ Database connection pools initialized")

    # Initialize GNN inference service (non-blocking, gracefully degrades)
    try:
        import sys
        from pathlib import Path as _Path
        _ai_root = _Path(__file__).parent.parent / "ai" / "corruption" / "ml_models"
        if str(_ai_root.parent.parent.parent) not in sys.path:
            sys.path.insert(0, str(_ai_root.parent.parent.parent))

        from ai.corruption.ml_models.gnn_inference import GNNInferenceService
        gnn_service = GNNInferenceService.get_instance()
        await gnn_service.initialize(pool=pool)
        print(f"✓ GNN Inference Service initialized (mode={gnn_service.mode})")
    except Exception as e:
        print(f"⚠ GNN Inference Service not available: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Close database connections on shutdown"""
    # Cleanup GNN inference service
    try:
        from ai.corruption.ml_models.gnn_inference import GNNInferenceService
        service = GNNInferenceService.get_instance()
        service.cleanup()
        print("✓ GNN Inference Service cleaned up")
    except Exception:
        pass

    await close_db()
    await close_asyncpg_pool()
    print("✓ Database connections closed")


# Include API routers
app.include_router(auth.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(stripe_webhook.router, prefix="/api")  # Stripe webhook handler
app.include_router(tender_details.router, prefix="/api")  # Tender bidders/lots/amendments/documents - MUST BE BEFORE tenders
app.include_router(tenders.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(ai.router, prefix="/api")  # AI endpoints (CPV suggest, requirements extraction, competitor analysis)
app.include_router(pricing.router, prefix="/api")  # Pricing analytics (historical price aggregation)
app.include_router(scraper.router, prefix="/api")  # Scraper API
app.include_router(entities.router, prefix="/api")  # Entity profiles
app.include_router(analytics.router, prefix="/api")  # Analytics & trends
app.include_router(insights.router, prefix="/api")  # Business intelligence insights
app.include_router(suppliers.router, prefix="/api")  # Supplier profiles
app.include_router(competitors.router, prefix="/api")  # Competitor activity tracking and bidding pattern analysis
app.include_router(competitor_tracking.router, prefix="/api")  # Competitor tracking (Phase 5.1)
app.include_router(products.router, prefix="/api")  # Product search
app.include_router(epazar.router)  # e-Pazar marketplace data
app.include_router(admin.router)  # Admin router has its own prefix
app.include_router(fraud_endpoints.router)  # Fraud router has its own prefix
app.include_router(personalization.router)  # Personalization router has its own prefix
app.include_router(cpv_codes.router, prefix="/api")  # CPV codes browser
app.include_router(saved_searches.router, prefix="/api")  # Saved searches/alerts
app.include_router(market_analytics.router, prefix="/api")  # Market analytics endpoints
app.include_router(alerts.router, prefix="/api")  # Alert matching engine (Phase 6.1)
app.include_router(briefings.router, prefix="/api")  # Daily briefings (Phase 6.2)
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])  # Push notifications (Phase 6.5)
app.include_router(corruption.router)  # Corruption detection & risk analysis
app.include_router(risk.router)  # Risk investigation (corruption research orchestrator)
app.include_router(explainability.router)  # ML explainability (SHAP/LIME)
app.include_router(collusion.router)  # Collusion detection & network analysis
app.include_router(api_keys.router, prefix="/api")  # API key management (Enterprise tier)
# app.include_router(report_campaigns.router)  # Report-first outreach campaigns (disabled - missing weasyprint)
app.include_router(contact.router, prefix="/api")  # Contact form submissions
app.include_router(outreach.router, prefix="/api")  # Outreach campaigns, unsubscribe, Postmark webhook
app.include_router(referrals.router, prefix="/api")  # Referral program (user endpoints)
app.include_router(referrals.admin_router, prefix="/api")  # Referral program (admin payout management)
app.include_router(whistleblower.router)  # Anonymous whistleblower portal (Phase 4.5)
app.include_router(clawd_monitor.router, prefix="/api")  # Clawd VA monitoring endpoint
app.include_router(chat_sessions.router, prefix="/api")  # Persistent chat sessions with memory


# Root endpoints
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "nabavkidata.com API",
        "version": "1.0.0",
        "description": "Macedonian Tender Intelligence Platform",
        "documentation": "/api/docs",
        "status": "operational"
    }


def _read_scraper_health():
    health_path = Path("/var/log/nabavkidata/health.json")
    if not health_path.exists():
        return None
    try:
        return json.loads(health_path.read_text())
    except Exception:
        return None


async def _database_health(db: AsyncSession):
    db_status = "ok"
    tender_count = None
    doc_count = None
    category_counts = {}
    try:
        res = await db.execute(text("SELECT COUNT(*) FROM tenders"))
        tender_count = res.scalar()
        res_docs = await db.execute(text("SELECT COUNT(*) FROM documents"))
        doc_count = res_docs.scalar()
        # Get counts by source_category
        res_cats = await db.execute(text("""
            SELECT COALESCE(source_category, 'unknown') as cat, COUNT(*) as cnt
            FROM tenders GROUP BY source_category ORDER BY cnt DESC
        """))
        for row in res_cats:
            category_counts[row[0]] = row[1]
    except Exception as e:
        db_status = f"error: {e}"
    return db_status, tender_count, doc_count, category_counts


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """
    Public health check for external monitoring (Clawd VA) and admin panel.
    No auth required. Returns DB stats, scraper health, and cron status.
    """
    # --- DB stats via asyncpg pool ---
    db_ok = False
    tender_count = None
    doc_count = None
    category_counts = {}
    try:
        pool = await get_asyncpg_pool()
        await pool.fetchval("SELECT 1")
        db_ok = True
        tender_count = await pool.fetchval("SELECT COUNT(*) FROM tenders")
        doc_count = await pool.fetchval("SELECT COUNT(*) FROM documents")
        rows = await pool.fetch(
            "SELECT COALESCE(source_category, 'unknown') as cat, COUNT(*) as cnt "
            "FROM tenders GROUP BY source_category"
        )
        for row in rows:
            category_counts[row["cat"]] = row["cnt"]
    except Exception:
        pass

    # --- Scraper status from marker file ---
    scraper_status = "unknown"
    scraper_last_run = None
    try:
        marker = Path("/tmp/nabavkidata_scraper_last_run")
        if marker.exists():
            mtime = marker.stat().st_mtime
            scraper_last_run = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%SZ")
            age_hours = (datetime.utcnow() - datetime.utcfromtimestamp(mtime)).total_seconds() / 3600
            scraper_status = "ok" if age_hours < 26 else "stale"
    except Exception:
        scraper_status = "failed"

    # --- Scraper health.json ---
    scraper_health = _read_scraper_health()

    # --- Cron status ---
    cron_status = "ok" if scraper_status == "ok" and db_ok else "degraded"

    overall = "ok" if db_ok else "unhealthy"

    return {
        "status": overall,
        "health": {"database": db_ok},
        "database": {
            "status": "ok" if db_ok else "error",
            "tenders": tender_count,
            "documents": doc_count,
            "tenders_by_category": category_counts,
        },
        "scraper": scraper_health,
        "scraper_status": scraper_status,
        "scraper_last_run": scraper_last_run,
        "cron": cron_status,
        "rag": "ok" if db_ok else "unknown",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health/scraper")
@app.get("/api/health/scraper")
async def scraper_health_check():
    """
    Scraper-specific health check for Clawd VA monitoring.
    Returns 200 with status 'ok' if scraper ran within last 26 hours.
    """
    try:
        marker = Path("/tmp/nabavkidata_scraper_last_run")
        if marker.exists():
            mtime = marker.stat().st_mtime
            last_run = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%SZ")
            age_hours = (datetime.utcnow() - datetime.utcfromtimestamp(mtime)).total_seconds() / 3600
            status = "ok" if age_hours < 26 else "stale"
        else:
            last_run = None
            status = "unknown"
    except Exception:
        last_run = None
        status = "failed"

    scraper_health = _read_scraper_health()

    return {
        "status": status,
        "last_run": last_run,
        "dataset": scraper_health.get("dataset") if scraper_health else None,
        "last_status": scraper_health.get("status") if scraper_health else None,
        "total_tenders": scraper_health.get("db", {}).get("total_tenders") if scraper_health else None,
        "timestamp": datetime.utcnow().isoformat()
    }
