"""
Risk Investigation API Endpoints for nabavkidata.com
Deep corruption research using CorruptionResearchOrchestrator

Security:
- Requires authentication
- Rate limited (10 requests per hour for free tier)
- Results cached for 24 hours
- All actions are audit logged

Features:
- Investigate tender, company, or institution
- Multi-source research (DB, web, e-nabavki, company registry, documents)
- AI-powered risk synthesis using Gemini
- Cached results from corruption_investigations table
- Structured risk assessment with evidence
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict
from time import time
import sys
import os
import asyncio

# Add AI module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

from database import get_db
from models import User
from api.auth import get_current_user

# Import CorruptionResearchOrchestrator
try:
    from corruption_research_orchestrator import CorruptionResearchOrchestrator
    ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    ORCHESTRATOR_AVAILABLE = False
    print(f"Warning: CorruptionResearchOrchestrator not available: {e}")

logger = logging.getLogger(__name__)

# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/api/risk",
    tags=["Risk Investigation"]
)


# ============================================================================
# RATE LIMITING
# ============================================================================

class InvestigationRateLimiter:
    """
    Rate limiter specifically for investigation endpoints
    10 requests per hour for free users, more for paid tiers
    """

    def __init__(self):
        # Store request timestamps per user
        # In production, use Redis for distributed rate limiting
        self.user_requests: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        user_id: str,
        subscription_tier: str = "free"
    ) -> tuple[bool, str, int]:
        """
        Check if user has exceeded rate limit

        Returns:
            (is_allowed, error_message, requests_remaining)
        """
        # Define tier limits (requests per hour)
        tier_limits = {
            "free": 10,
            "basic": 50,
            "pro": 200,
            "enterprise": 1000
        }

        limit = tier_limits.get(subscription_tier.lower(), tier_limits["free"])

        now = time()
        window_seconds = 3600  # 1 hour

        # Get user's request history
        user_requests = self.user_requests[user_id]

        # Remove requests older than 1 hour
        cutoff_time = now - window_seconds
        user_requests[:] = [t for t in user_requests if t > cutoff_time]

        # Check if limit exceeded
        if len(user_requests) >= limit:
            reset_time = int(min(user_requests) + window_seconds - now)
            return (
                False,
                f"Rate limit exceeded. {limit} investigations per hour allowed for {subscription_tier} tier. Resets in {reset_time}s.",
                0
            )

        # Add current request
        user_requests.append(now)

        remaining = limit - len(user_requests)
        return True, "", remaining

    def get_remaining_requests(self, user_id: str, subscription_tier: str = "free") -> int:
        """Get number of remaining requests for user"""
        tier_limits = {
            "free": 10,
            "basic": 50,
            "pro": 200,
            "enterprise": 1000
        }

        limit = tier_limits.get(subscription_tier.lower(), tier_limits["free"])

        now = time()
        window_seconds = 3600

        user_requests = self.user_requests[user_id]
        cutoff_time = now - window_seconds
        user_requests[:] = [t for t in user_requests if t > cutoff_time]

        return max(0, limit - len(user_requests))


# Global rate limiter instance
investigation_rate_limiter = InvestigationRateLimiter()


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class InvestigateRequest(BaseModel):
    """Request to investigate an entity"""
    type: str = Field(..., pattern="^(tender|company|institution)$", description="Entity type to investigate")
    query: str = Field(..., min_length=1, max_length=500, description="Tender ID, company name, or institution name")


class SourceCheck(BaseModel):
    """Track which sources were checked"""
    database: bool = False
    enabavki: bool = False
    web_search: bool = False
    company: bool = False
    documents: bool = False


class Finding(BaseModel):
    """Individual research finding"""
    source: str = Field(..., description="Source: db|web|enabavki|company|document")
    type: str = Field(..., description="Type: red_flag|info|connection|anomaly|discrepancy")
    description: str = Field(..., description="Finding description")
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence in this finding")
    corroborated: Optional[bool] = Field(None, description="Whether finding is corroborated by multiple sources")


class DataQuality(BaseModel):
    """Information about data completeness"""
    db_data_complete: Optional[bool] = None
    official_data_available: Optional[bool] = None
    web_data_found: Optional[bool] = None
    missing_info: List[str] = Field(default_factory=list)


class InvestigateResponse(BaseModel):
    """Response from investigation"""
    risk_score: int = Field(..., ge=0, le=100, description="Risk score 0-100")
    risk_level: str = Field(..., pattern="^(minimal|low|medium|high|critical)$")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in assessment")
    findings: List[Finding] = Field(default_factory=list)
    sources_checked: SourceCheck
    recommendations: List[str] = Field(default_factory=list)
    summary_mk: str = Field(..., description="Summary in Macedonian")
    data_quality: DataQuality
    investigated_at: datetime
    cached: bool = Field(False, description="Whether result was from cache")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_cached_investigation(
    db: AsyncSession,
    entity_id: str,
    entity_type: str,
    max_age_hours: int = 24
) -> Optional[Dict[str, Any]]:
    """
    Check if investigation exists in cache (corruption_investigations table)
    and is less than max_age_hours old
    """
    try:
        from sqlalchemy import text

        query = """
        SELECT
            entity_id,
            entity_type,
            entity_name,
            risk_score,
            risk_level,
            confidence,
            findings,
            recommendations,
            summary_mk,
            summary_en,
            data_quality,
            investigated_at
        FROM corruption_investigations
        WHERE entity_id = :entity_id
          AND entity_type = :entity_type
          AND investigated_at > :cutoff_time
        ORDER BY investigated_at DESC
        LIMIT 1
        """

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        result = await db.execute(
            text(query),
            {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "cutoff_time": cutoff_time
            }
        )

        row = result.fetchone()

        if row:
            return {
                "entity_id": row[0],
                "entity_type": row[1],
                "entity_name": row[2],
                "risk_score": row[3],
                "risk_level": row[4],
                "confidence": row[5],
                "findings": row[6],
                "recommendations": row[7],
                "summary_mk": row[8],
                "summary_en": row[9],
                "data_quality": row[10],
                "investigated_at": row[11]
            }

        return None

    except Exception as e:
        logger.warning(f"Failed to check cache: {e}")
        return None


def map_finding_to_schema(finding_dict: Dict[str, Any]) -> Finding:
    """Convert finding dict from orchestrator to Finding schema"""
    evidence_items = []

    if isinstance(finding_dict.get("evidence"), dict):
        evidence_obj = finding_dict["evidence"]
        if "items" in evidence_obj:
            evidence_items = [str(item) for item in evidence_obj["items"][:5]]  # Limit to 5 items
        else:
            # Flatten evidence dict to strings
            evidence_items = [f"{k}: {v}" for k, v in evidence_obj.items() if k != "corroborating_sources"][:5]
    elif isinstance(finding_dict.get("evidence"), list):
        evidence_items = [str(item) for item in finding_dict["evidence"][:5]]

    return Finding(
        source=finding_dict.get("source", "unknown"),
        type=finding_dict.get("finding_type") or finding_dict.get("type", "info"),
        description=finding_dict.get("description", ""),
        severity=finding_dict.get("severity", "low"),
        evidence=evidence_items,
        confidence=finding_dict.get("confidence"),
        corroborated=finding_dict.get("evidence", {}).get("corroborated") if isinstance(finding_dict.get("evidence"), dict) else None
    )


def determine_sources_checked(evidence_summary: Dict[str, Any]) -> SourceCheck:
    """Determine which sources were checked based on evidence summary"""
    return SourceCheck(
        database=bool(evidence_summary.get("db_research")),
        enabavki=bool(evidence_summary.get("official_tender") or evidence_summary.get("official_bidders")),
        web_search=bool(evidence_summary.get("web_research")),
        company=bool(evidence_summary.get("winner_research") or evidence_summary.get("ownership_research")),
        documents=bool(evidence_summary.get("document_analysis"))
    )


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/investigate", response_model=InvestigateResponse)
async def investigate_entity(
    request: InvestigateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Investigate tender, company, or institution for corruption risks

    Uses CorruptionResearchOrchestrator to:
    1. Check all available data sources (DB, e-nabavki, web, company registry, documents)
    2. Cross-reference findings from multiple sources
    3. Use AI (Gemini) to synthesize intelligent risk assessment
    4. Provide evidence-based findings with confidence scores

    Request Body:
    - type: "tender" | "company" | "institution"
    - query: Tender ID, company name, or institution name

    Rate Limits:
    - Free tier: 10 requests/hour
    - Basic tier: 50 requests/hour
    - Pro tier: 200 requests/hour
    - Enterprise: 1000 requests/hour

    Caching:
    - Results are cached for 24 hours
    - Fresh investigation only runs if no recent cached result exists

    Returns:
    - Detailed risk assessment with findings, evidence, and recommendations
    """
    if not ORCHESTRATOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Corruption research service not available. Check configuration."
        )

    # Check rate limit
    subscription_tier = getattr(current_user, "subscription_tier", "free")
    is_allowed, error_msg, remaining = investigation_rate_limiter.check_rate_limit(
        str(current_user.user_id),
        subscription_tier
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": error_msg,
                "tier": subscription_tier,
                "remaining": remaining,
                "upgrade_url": "/pricing"
            }
        )

    # Check cache first
    cached_result = await get_cached_investigation(
        db,
        entity_id=request.query,
        entity_type=request.type,
        max_age_hours=24
    )

    if cached_result:
        logger.info(f"Returning cached investigation for {request.type}: {request.query}")

        # Map cached result to response schema
        findings = []
        if cached_result.get("findings"):
            for finding_dict in cached_result["findings"]:
                try:
                    findings.append(map_finding_to_schema(finding_dict))
                except Exception as e:
                    logger.warning(f"Failed to map finding: {e}")

        data_quality_dict = cached_result.get("data_quality") or {}

        return InvestigateResponse(
            risk_score=cached_result.get("risk_score", 0),
            risk_level=cached_result.get("risk_level", "minimal"),
            confidence=cached_result.get("confidence", 0.5),
            findings=findings,
            sources_checked=SourceCheck(
                database=data_quality_dict.get("db_data_complete", False),
                enabavki=data_quality_dict.get("official_data_available", False),
                web_search=data_quality_dict.get("web_data_found", False),
                company=True,  # Assume company research was attempted
                documents=False
            ),
            recommendations=cached_result.get("recommendations", []),
            summary_mk=cached_result.get("summary_mk", ""),
            data_quality=DataQuality(
                db_data_complete=data_quality_dict.get("db_data_complete"),
                official_data_available=data_quality_dict.get("official_data_available"),
                web_data_found=data_quality_dict.get("web_data_found"),
                missing_info=data_quality_dict.get("missing_info", [])
            ),
            investigated_at=cached_result.get("investigated_at", datetime.utcnow()),
            cached=True
        )

    # No cached result - run fresh investigation
    logger.info(f"Running fresh investigation for {request.type}: {request.query}")

    try:
        # Initialize orchestrator
        orchestrator = CorruptionResearchOrchestrator()
        await orchestrator.initialize()

        try:
            # Run investigation based on type
            if request.type == "tender":
                assessment = await orchestrator.investigate_tender(request.query)
            elif request.type == "company":
                assessment = await orchestrator.investigate_company(request.query)
            elif request.type == "institution":
                assessment = await orchestrator.investigate_institution(request.query)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid investigation type: {request.type}"
                )

            # Map findings to schema
            findings = []
            for finding in assessment.findings:
                try:
                    if hasattr(finding, "to_dict"):
                        finding_dict = finding.to_dict()
                    elif isinstance(finding, dict):
                        finding_dict = finding
                    else:
                        continue

                    findings.append(map_finding_to_schema(finding_dict))
                except Exception as e:
                    logger.warning(f"Failed to map finding: {e}")

            # Determine sources checked
            sources_checked = determine_sources_checked(assessment.evidence_summary)

            # Map data quality
            dq = assessment.data_quality or {}
            data_quality = DataQuality(
                db_data_complete=dq.get("db_data_complete"),
                official_data_available=dq.get("official_data_available"),
                web_data_found=dq.get("web_data_found"),
                missing_info=dq.get("missing_info", [])
            )

            return InvestigateResponse(
                risk_score=assessment.risk_score,
                risk_level=assessment.risk_level,
                confidence=assessment.confidence,
                findings=findings,
                sources_checked=sources_checked,
                recommendations=assessment.recommendations,
                summary_mk=assessment.summary_mk,
                data_quality=data_quality,
                investigated_at=assessment.timestamp,
                cached=False
            )

        finally:
            # Always close orchestrator
            await orchestrator.close()

    except Exception as e:
        logger.error(f"Investigation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation failed: {str(e)}"
        )


@router.get("/investigate/limits")
async def get_investigation_limits(
    current_user: User = Depends(get_current_user)
):
    """
    Get current rate limit status for investigations

    Returns:
    - Tier
    - Hourly limit
    - Remaining requests
    - Reset time
    """
    subscription_tier = getattr(current_user, "subscription_tier", "free")

    tier_limits = {
        "free": 10,
        "basic": 50,
        "pro": 200,
        "enterprise": 1000
    }

    limit = tier_limits.get(subscription_tier.lower(), tier_limits["free"])
    remaining = investigation_rate_limiter.get_remaining_requests(
        str(current_user.user_id),
        subscription_tier
    )

    return {
        "tier": subscription_tier,
        "hourly_limit": limit,
        "remaining": remaining,
        "window_seconds": 3600
    }
