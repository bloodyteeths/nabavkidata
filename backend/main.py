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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api import tenders, documents, rag, auth, billing, admin, fraud_endpoints, personalization, scraper, stripe_webhook, entities, analytics, suppliers, tender_details, products, epazar, ai, cpv_codes, saved_searches, market_analytics, pricing, competitors, competitor_tracking, alerts, briefings, notifications, corruption, risk, api_keys, insights
from middleware.fraud import FraudPreventionMiddleware
from middleware.rate_limit import RateLimitMiddleware

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
    allow_headers=["Authorization", "Content-Type", "X-Device-Fingerprint", "X-Requested-With", "X-CSRF-Token", "Accept", "Accept-Language", "Content-Language", "X-API-Key"],
)

# Security Middlewares
# Rate Limiting - applied to all endpoints
app.add_middleware(RateLimitMiddleware)

# Fraud Prevention - checks for abuse patterns
app.add_middleware(FraudPreventionMiddleware)


# Startup/Shutdown Events
@app.on_event("startup")
async def startup():
    """Initialize database connection on startup"""
    await init_db()
    print("✓ Database connection pool initialized")


@app.on_event("shutdown")
async def shutdown():
    """Close database connections on shutdown"""
    await close_db()
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
app.include_router(api_keys.router, prefix="/api")  # API key management (Enterprise tier)


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
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Public health check endpoint for external monitoring.
    Returns minimal information to avoid information disclosure.
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "service": "backend-api",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/health")
async def api_health(db: AsyncSession = Depends(get_db)):
    """
    Detailed health check endpoint for internal monitoring.
    TODO: Consider adding authentication for production to prevent information disclosure.
    """
    db_status, tender_count, doc_count, category_counts = await _database_health(db)
    scraper_health = _read_scraper_health()
    cron_status = "unknown"
    if scraper_health:
        cron_status = f"last run {scraper_health.get('finished_at')} status {scraper_health.get('status')}"
    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "database": {
            "status": db_status,
            "tenders": tender_count,
            "documents": doc_count,
            "tenders_by_category": category_counts,
        },
        "scraper": scraper_health,
        "cron": cron_status,
        "rag": "enabled" if os.getenv('GEMINI_API_KEY') else "disabled"
    }
