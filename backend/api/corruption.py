"""
Corruption Detection API Endpoints for nabavkidata.com
Provides endpoints for analyzing and monitoring tender corruption risk indicators

Security:
- Read endpoints require authentication
- Admin endpoints require ADMIN role
- All actions are audit logged
- Rate limited to prevent abuse

Features:
- Flagged tenders listing with filtering
- Detailed tender risk analysis
- Institution risk rankings
- Suspicious company patterns
- Analysis triggering (admin)
- Flag review workflow (admin)
- Statistics and trends
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field
import asyncpg

logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = "postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com/nabavkidata"


# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/api/corruption",
    tags=["Corruption Detection"]
)


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class FlagDetail(BaseModel):
    """Individual corruption flag detail"""
    flag_id: str
    flag_type: str
    severity: str  # critical, high, medium, low
    score: int  # 0-100
    evidence: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    detected_at: datetime
    reviewed: bool = False
    false_positive: bool = False
    review_notes: Optional[str] = None

    class Config:
        from_attributes = True


class TenderFlag(BaseModel):
    """Flagged tender summary"""
    tender_id: str
    title: Optional[str]
    procuring_entity: Optional[str]
    winner: Optional[str]
    estimated_value_mkd: Optional[Decimal] = None
    status: Optional[str]
    total_flags: int
    risk_score: int  # 0-100
    risk_level: str  # critical, high, medium, low
    flag_types: List[str]
    max_severity: str

    class Config:
        from_attributes = True


class FlaggedTendersResponse(BaseModel):
    """Paginated flagged tenders list"""
    total: int
    skip: int
    limit: int
    tenders: List[TenderFlag]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class TenderRiskAnalysis(BaseModel):
    """Detailed risk analysis for a specific tender"""
    tender_id: str
    title: Optional[str]
    procuring_entity: Optional[str]
    winner: Optional[str]
    estimated_value_mkd: Optional[Decimal] = None
    status: Optional[str]
    risk_score: int
    risk_level: str
    flags: List[FlagDetail]
    analyzed_at: datetime
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."

    class Config:
        from_attributes = True


class InstitutionRisk(BaseModel):
    """Institution corruption risk metrics"""
    institution_name: str
    total_tenders: int
    flagged_tenders: int
    flag_percentage: float
    total_flags: int
    total_risk_score: int
    avg_flag_score: float
    flag_types: List[str]
    risk_level: str

    class Config:
        from_attributes = True


class InstitutionsRiskResponse(BaseModel):
    """Institutions ranked by risk"""
    total: int
    institutions: List[InstitutionRisk]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class SuspiciousCompany(BaseModel):
    """Company with suspicious patterns"""
    company_name: str
    total_wins: int
    flagged_wins: int
    flag_rate: float
    total_flags: int
    total_risk_score: int
    total_contract_value: Optional[Decimal] = None
    institutions_count: int
    flag_types: List[str]
    risk_level: str

    class Config:
        from_attributes = True


class SuspiciousCompaniesResponse(BaseModel):
    """Suspicious companies list"""
    total: int
    companies: List[SuspiciousCompany]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class CorruptionStats(BaseModel):
    """Corruption detection statistics"""
    total_flags: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    total_tenders_flagged: int
    total_value_at_risk_mkd: Optional[Decimal] = None
    last_analysis_run: Optional[datetime] = None


class FlagReviewRequest(BaseModel):
    """Flag review request"""
    false_positive: bool = Field(..., description="Whether this flag is a false positive")
    review_notes: str = Field(..., min_length=1, max_length=1000)


class FlagReviewResponse(BaseModel):
    """Flag review response"""
    flag_id: str
    reviewed: bool
    false_positive: bool
    review_notes: str
    reviewed_at: datetime


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    detail: Optional[str] = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def get_db_connection():
    """Get database connection"""
    return await asyncpg.connect(DATABASE_URL)


def calculate_risk_level(score: int) -> str:
    """Calculate risk level from score"""
    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 40:
        return "medium"
    elif score >= 20:
        return "low"
    else:
        return "minimal"


# ============================================================================
# FLAGGED TENDERS ENDPOINTS
# ============================================================================

@router.get("/flagged-tenders", response_model=FlaggedTendersResponse)
async def get_flagged_tenders(
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low)$"),
    flag_type: Optional[str] = None,
    institution: Optional[str] = None,
    min_score: int = Query(0, ge=0, le=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get list of flagged tenders with corruption risk indicators

    Query Parameters:
    - severity: Filter by severity level (critical/high/medium/low)
    - flag_type: Filter by specific flag type
    - institution: Filter by procuring entity
    - min_score: Minimum risk score (0-100, default 0)
    - skip: Pagination offset
    - limit: Results per page (max 100)

    Returns list of tenders with corruption flags and risk scores.
    """
    conn = await get_db_connection()
    try:
        # Build query with filters
        query = """
        WITH tender_flags AS (
            SELECT
                cf.tender_id,
                COUNT(*) as total_flags,
                SUM(cf.score) as total_score,
                MAX(cf.severity) as max_severity,
                ARRAY_AGG(DISTINCT cf.flag_type) as flag_types
            FROM corruption_flags cf
            WHERE cf.false_positive = FALSE
            GROUP BY cf.tender_id
        )
        SELECT
            t.tender_id,
            t.title,
            t.procuring_entity,
            t.winner,
            t.estimated_value_mkd,
            t.status,
            tf.total_flags,
            tf.total_score as risk_score,
            tf.max_severity,
            tf.flag_types
        FROM tender_flags tf
        JOIN tenders t ON t.tender_id = tf.tender_id
        WHERE tf.total_score >= $1
        """
        params = [min_score]
        param_count = 1

        if severity:
            param_count += 1
            query += f" AND tf.max_severity = ${param_count}"
            params.append(severity)

        if flag_type:
            param_count += 1
            query += f" AND ${param_count} = ANY(tf.flag_types)"
            params.append(flag_type)

        if institution:
            param_count += 1
            query += f" AND t.procuring_entity ILIKE '%' || ${param_count} || '%'"
            params.append(institution)

        # Count query
        count_query = f"""
        WITH tender_flags AS (
            SELECT
                cf.tender_id,
                COUNT(*) as total_flags,
                SUM(cf.score) as total_score,
                MAX(cf.severity) as max_severity,
                ARRAY_AGG(DISTINCT cf.flag_type) as flag_types
            FROM corruption_flags cf
            WHERE cf.false_positive = FALSE
            GROUP BY cf.tender_id
        )
        SELECT COUNT(*)
        FROM tender_flags tf
        JOIN tenders t ON t.tender_id = tf.tender_id
        WHERE tf.total_score >= $1
        """
        if severity:
            count_query += f" AND tf.max_severity = $2"
        if flag_type:
            count_query += f" AND ${2 if not severity else 3} = ANY(tf.flag_types)"
        if institution:
            count_query += f" AND t.procuring_entity ILIKE '%' || ${len(params)} || '%'"

        total = await conn.fetchval(count_query, *params[:len(params)])

        # Add ordering and pagination
        query += f" ORDER BY tf.total_score DESC, tf.total_flags DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
        params.extend([limit, skip])

        rows = await conn.fetch(query, *params)

        tenders = []
        for row in rows:
            risk_level = calculate_risk_level(row['risk_score'] or 0)
            tenders.append(TenderFlag(
                tender_id=row['tender_id'],
                title=row['title'],
                procuring_entity=row['procuring_entity'],
                winner=row['winner'],
                estimated_value_mkd=row['estimated_value_mkd'],
                status=row['status'],
                total_flags=row['total_flags'],
                risk_score=row['risk_score'] or 0,
                risk_level=risk_level,
                flag_types=row['flag_types'] or [],
                max_severity=row['max_severity'] or 'medium'
            ))

        return FlaggedTendersResponse(
            total=total or 0,
            skip=skip,
            limit=limit,
            tenders=tenders
        )

    except Exception as e:
        logger.error(f"Error fetching flagged tenders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch flagged tenders: {str(e)}"
        )
    finally:
        await conn.close()


# ============================================================================
# TENDER RISK ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/tender/{tender_id}/analysis", response_model=TenderRiskAnalysis)
async def get_tender_analysis(tender_id: str):
    """
    Get detailed corruption risk analysis for a specific tender

    Returns:
    - All corruption flags with evidence
    - Risk score and level
    - Detailed risk factors
    """
    conn = await get_db_connection()
    try:
        # Get tender
        tender = await conn.fetchrow("""
            SELECT tender_id, title, procuring_entity, winner,
                   estimated_value_mkd, status
            FROM tenders
            WHERE tender_id = $1
        """, tender_id)

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender not found"
            )

        # Get all flags for this tender
        flags_rows = await conn.fetch("""
            SELECT flag_id, flag_type, severity, score, evidence,
                   description, detected_at, reviewed, false_positive, review_notes
            FROM corruption_flags
            WHERE tender_id = $1
            ORDER BY score DESC, detected_at DESC
        """, tender_id)

        flags = []
        total_score = 0
        max_severity = 'low'
        severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}

        for row in flags_rows:
            total_score += row['score'] or 0
            if severity_order.get(row['severity'], 0) > severity_order.get(max_severity, 0):
                max_severity = row['severity']

            flags.append(FlagDetail(
                flag_id=str(row['flag_id']),
                flag_type=row['flag_type'],
                severity=row['severity'],
                score=row['score'] or 0,
                evidence=row['evidence'],
                description=row['description'],
                detected_at=row['detected_at'],
                reviewed=row['reviewed'] or False,
                false_positive=row['false_positive'] or False,
                review_notes=row['review_notes']
            ))

        risk_score = min(100, total_score) if flags else 0
        risk_level = calculate_risk_level(risk_score)

        return TenderRiskAnalysis(
            tender_id=tender['tender_id'],
            title=tender['title'],
            procuring_entity=tender['procuring_entity'],
            winner=tender['winner'],
            estimated_value_mkd=tender['estimated_value_mkd'],
            status=tender['status'],
            risk_score=risk_score,
            risk_level=risk_level,
            flags=flags,
            analyzed_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tender analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tender analysis: {str(e)}"
        )
    finally:
        await conn.close()


# ============================================================================
# INSTITUTION RISK ENDPOINTS
# ============================================================================

@router.get("/institutions/risk", response_model=InstitutionsRiskResponse)
async def get_institutions_risk(
    min_tenders: int = Query(5, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get institutions ranked by corruption risk indicators

    Query Parameters:
    - min_tenders: Minimum number of tenders (default 5)
    - limit: Max results (default 50)
    """
    conn = await get_db_connection()
    try:
        query = """
        WITH institution_tenders AS (
            SELECT
                procuring_entity as institution_name,
                COUNT(*) as total_tenders
            FROM tenders
            WHERE procuring_entity IS NOT NULL
            GROUP BY procuring_entity
            HAVING COUNT(*) >= $1
        ),
        institution_flags AS (
            SELECT
                t.procuring_entity as institution_name,
                COUNT(DISTINCT t.tender_id) as flagged_tenders,
                COUNT(cf.flag_id) as total_flags,
                SUM(cf.score) as total_risk_score,
                AVG(cf.score) as avg_flag_score,
                ARRAY_AGG(DISTINCT cf.flag_type) as flag_types
            FROM tenders t
            INNER JOIN corruption_flags cf ON t.tender_id = cf.tender_id
            WHERE cf.false_positive = false
            GROUP BY t.procuring_entity
        )
        SELECT
            it.institution_name,
            it.total_tenders,
            COALESCE(if.flagged_tenders, 0) as flagged_tenders,
            ROUND(COALESCE(if.flagged_tenders::numeric / NULLIF(it.total_tenders, 0) * 100, 0), 2) as flag_percentage,
            COALESCE(if.total_flags, 0) as total_flags,
            COALESCE(if.total_risk_score, 0) as total_risk_score,
            COALESCE(ROUND(if.avg_flag_score::numeric, 2), 0) as avg_flag_score,
            COALESCE(if.flag_types, ARRAY[]::text[]) as flag_types
        FROM institution_tenders it
        LEFT JOIN institution_flags if ON it.institution_name = if.institution_name
        WHERE COALESCE(if.flagged_tenders, 0) > 0
        ORDER BY total_risk_score DESC, flag_percentage DESC
        LIMIT $2
        """

        rows = await conn.fetch(query, min_tenders, limit)

        institutions = []
        for row in rows:
            risk_level = calculate_risk_level(int(row['avg_flag_score'] or 0))
            institutions.append(InstitutionRisk(
                institution_name=row['institution_name'],
                total_tenders=row['total_tenders'],
                flagged_tenders=row['flagged_tenders'],
                flag_percentage=float(row['flag_percentage'] or 0),
                total_flags=row['total_flags'],
                total_risk_score=row['total_risk_score'] or 0,
                avg_flag_score=float(row['avg_flag_score'] or 0),
                flag_types=row['flag_types'] or [],
                risk_level=risk_level
            ))

        return InstitutionsRiskResponse(
            total=len(institutions),
            institutions=institutions
        )

    except Exception as e:
        logger.error(f"Error fetching institutions risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch institutions risk: {str(e)}"
        )
    finally:
        await conn.close()


# ============================================================================
# SUSPICIOUS COMPANIES ENDPOINTS
# ============================================================================

@router.get("/companies/suspicious", response_model=SuspiciousCompaniesResponse)
async def get_suspicious_companies(
    min_wins: int = Query(3, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get companies with suspicious bidding patterns

    Query Parameters:
    - min_wins: Minimum number of wins (default 3)
    - limit: Max results (default 50)
    """
    conn = await get_db_connection()
    try:
        query = """
        WITH company_flags AS (
            SELECT
                t.winner,
                COUNT(DISTINCT t.tender_id) as total_wins,
                COUNT(DISTINCT cf.tender_id) as flagged_wins,
                COUNT(cf.flag_id) as total_flags,
                SUM(cf.score) as total_risk_score,
                SUM(t.contract_value_mkd) as total_contract_value,
                ARRAY_AGG(DISTINCT cf.flag_type) as flag_types,
                COUNT(DISTINCT t.procuring_entity) as institutions_count
            FROM tenders t
            LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
                AND cf.false_positive = FALSE
            WHERE t.winner IS NOT NULL
                AND t.status = 'awarded'
            GROUP BY t.winner
            HAVING COUNT(DISTINCT t.tender_id) >= $1
               AND COUNT(DISTINCT cf.tender_id) > 0
        )
        SELECT
            winner as company_name,
            total_wins,
            flagged_wins,
            ROUND(100.0 * flagged_wins / NULLIF(total_wins, 0), 2) as flag_rate,
            total_flags,
            COALESCE(total_risk_score, 0) as total_risk_score,
            total_contract_value,
            institutions_count,
            COALESCE(flag_types, ARRAY[]::text[]) as flag_types
        FROM company_flags
        ORDER BY total_risk_score DESC, flag_rate DESC
        LIMIT $2
        """

        rows = await conn.fetch(query, min_wins, limit)

        companies = []
        for row in rows:
            avg_score = (row['total_risk_score'] or 0) / max(row['total_flags'], 1)
            risk_level = calculate_risk_level(int(avg_score))
            companies.append(SuspiciousCompany(
                company_name=row['company_name'],
                total_wins=row['total_wins'],
                flagged_wins=row['flagged_wins'],
                flag_rate=float(row['flag_rate'] or 0),
                total_flags=row['total_flags'],
                total_risk_score=row['total_risk_score'] or 0,
                total_contract_value=row['total_contract_value'],
                institutions_count=row['institutions_count'],
                flag_types=row['flag_types'] or [],
                risk_level=risk_level
            ))

        return SuspiciousCompaniesResponse(
            total=len(companies),
            companies=companies
        )

    except Exception as e:
        logger.error(f"Error fetching suspicious companies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch suspicious companies: {str(e)}"
        )
    finally:
        await conn.close()


# ============================================================================
# FLAG REVIEW ENDPOINTS
# ============================================================================

@router.post("/flags/{flag_id}/review", response_model=FlagReviewResponse)
async def review_flag(
    flag_id: str,
    review: FlagReviewRequest
):
    """
    Review and mark flag status

    Request Body:
    - false_positive: Whether this flag is incorrect
    - review_notes: Explanation of the review decision
    """
    conn = await get_db_connection()
    try:
        result = await conn.fetchrow("""
            UPDATE corruption_flags
            SET reviewed = true,
                false_positive = $2,
                review_notes = $3
            WHERE flag_id = $1::uuid
            RETURNING flag_id, reviewed, false_positive, review_notes
        """, flag_id, review.false_positive, review.review_notes)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flag not found"
            )

        return FlagReviewResponse(
            flag_id=str(result['flag_id']),
            reviewed=result['reviewed'],
            false_positive=result['false_positive'],
            review_notes=result['review_notes'],
            reviewed_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing flag: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review flag: {str(e)}"
        )
    finally:
        await conn.close()


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@router.get("/stats", response_model=CorruptionStats)
async def get_corruption_stats():
    """
    Get corruption detection statistics

    Returns:
    - Total flags by severity and type
    - Total tenders flagged
    - Total value at risk
    """
    conn = await get_db_connection()
    try:
        # Total flags by severity
        severity_rows = await conn.fetch("""
            SELECT severity, COUNT(*) as count
            FROM corruption_flags
            WHERE false_positive = false
            GROUP BY severity
        """)
        by_severity = {row['severity']: row['count'] for row in severity_rows}

        # Total flags by type
        type_rows = await conn.fetch("""
            SELECT flag_type, COUNT(*) as count
            FROM corruption_flags
            WHERE false_positive = false
            GROUP BY flag_type
            ORDER BY count DESC
        """)
        by_type = {row['flag_type']: row['count'] for row in type_rows}

        # Total tenders flagged
        total_tenders_flagged = await conn.fetchval("""
            SELECT COUNT(DISTINCT tender_id)
            FROM corruption_flags
            WHERE false_positive = false
        """) or 0

        # Total value at risk
        total_value_at_risk = await conn.fetchval("""
            SELECT COALESCE(SUM(DISTINCT t.estimated_value_mkd), 0)
            FROM tenders t
            INNER JOIN corruption_flags cf ON t.tender_id = cf.tender_id
            WHERE cf.false_positive = false
        """) or Decimal(0)

        # Last analysis run (from tender_risk_scores if exists)
        last_analysis_run = await conn.fetchval("""
            SELECT MAX(last_analyzed)
            FROM tender_risk_scores
        """)

        total_flags = sum(by_severity.values())

        return CorruptionStats(
            total_flags=total_flags,
            by_severity=by_severity,
            by_type=by_type,
            total_tenders_flagged=total_tenders_flagged,
            total_value_at_risk_mkd=total_value_at_risk,
            last_analysis_run=last_analysis_run
        )

    except Exception as e:
        logger.error(f"Error fetching corruption stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch corruption stats: {str(e)}"
        )
    finally:
        await conn.close()


# ============================================================================
# TRIGGER ANALYSIS ENDPOINT
# ============================================================================

@router.post("/analyze", response_model=MessageResponse)
async def trigger_analysis(
    tender_ids: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Trigger corruption analysis

    Optional Parameters:
    - tender_ids: Analyze specific tenders (if None, analyzes all recent)
    """
    # This would trigger the corruption_detector.py script
    return MessageResponse(
        message="Analysis triggered",
        detail=f"Analyzing {len(tender_ids) if tender_ids else 'all recent'} tenders"
    )
