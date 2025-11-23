"""
nabavkidata.com Backend API
FastAPI REST server
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

from database import init_db, close_db
from api import tenders, documents, rag, auth, billing, admin, fraud_endpoints, personalization, scraper, stripe_webhook
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://nabavkidata.com",
        "https://www.nabavkidata.com",
        "https://nabavkidata.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(tenders.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(scraper.router, prefix="/api")  # Scraper API
app.include_router(admin.router)  # Admin router has its own prefix
app.include_router(fraud_endpoints.router)  # Fraud router has its own prefix
app.include_router(personalization.router)  # Personalization router has its own prefix


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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "backend-api",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if os.getenv('DATABASE_URL') else "not configured",
        "rag": "enabled" if os.getenv('OPENAI_API_KEY') else "disabled"
    }
