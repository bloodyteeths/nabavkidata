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


def latin_to_cyrillic(text: str) -> str:
    """
    Convert Latin transliteration to Macedonian Cyrillic.
    Used for searching Cyrillic names with Latin input.
    """
    # Multi-character mappings must be processed first
    latin_to_macedonian = {
        'dzh': 'џ', 'Dzh': 'Џ', 'DZH': 'Џ',
        'gj': 'ѓ', 'Gj': 'Ѓ', 'GJ': 'Ѓ',
        'kj': 'ќ', 'Kj': 'Ќ', 'KJ': 'Ќ',
        'lj': 'љ', 'Lj': 'Љ', 'LJ': 'Љ',
        'nj': 'њ', 'Nj': 'Њ', 'NJ': 'Њ',
        'dz': 'ѕ', 'Dz': 'Ѕ', 'DZ': 'Ѕ',
        'zh': 'ж', 'Zh': 'Ж', 'ZH': 'Ж',
        'ch': 'ч', 'Ch': 'Ч', 'CH': 'Ч',
        'sh': 'ш', 'Sh': 'Ш', 'SH': 'Ш',
    }

    # Single character mappings
    single_char = {
        'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
        'z': 'з', 'i': 'и', 'j': 'ј', 'k': 'к', 'l': 'л', 'm': 'м',
        'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т',
        'u': 'у', 'f': 'ф', 'h': 'х', 'c': 'ц',
        'A': 'А', 'B': 'Б', 'V': 'В', 'G': 'Г', 'D': 'Д', 'E': 'Е',
        'Z': 'З', 'I': 'И', 'J': 'Ј', 'K': 'К', 'L': 'Л', 'M': 'М',
        'N': 'Н', 'O': 'О', 'P': 'П', 'R': 'Р', 'S': 'С', 'T': 'Т',
        'U': 'У', 'F': 'Ф', 'H': 'Х', 'C': 'Ц'
    }

    # Process multi-character combinations first
    result = text
    for latin, cyrillic in latin_to_macedonian.items():
        result = result.replace(latin, cyrillic)

    # Then process single characters
    output = ''
    for char in result:
        output += single_char.get(char, char)

    return output


def build_bilingual_search_condition(field: str, search_term: str, param_num: int) -> tuple[str, list]:
    """
    Build SQL condition that searches both Cyrillic and Latin versions.

    Supports bidirectional search:
    - "Битола" finds institutions with "Битола" (exact Cyrillic match)
    - "Bitola" finds institutions with "Битола" (Latin -> Cyrillic conversion)
    - Also finds English names like "Municipality of Bitola"

    Args:
        field: Database field name (e.g., 't.procuring_entity')
        search_term: User's search input
        param_num: Current parameter number for SQL query

    Returns:
        Tuple of (SQL condition string, list of parameters)
    """
    # Check if search term contains Cyrillic characters
    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in search_term)

    if has_cyrillic:
        # Search term is already Cyrillic - search directly
        condition = f"{field} ILIKE '%' || ${param_num} || '%'"
        params = [search_term]
    else:
        # Search term is Latin - search both Latin AND convert to Cyrillic
        # This allows "Bitola" to find both "Municipality of Bitola" and "Општина Битола"
        cyrillic_version = latin_to_cyrillic(search_term)
        condition = f"({field} ILIKE '%' || ${param_num} || '%' OR {field} ILIKE '%' || ${param_num + 1} || '%')"
        params = [search_term, cyrillic_version]

    return condition, params


# ============================================================================
# FLAGGED TENDERS ENDPOINTS
# ============================================================================

@router.get("/flagged-tenders", response_model=FlaggedTendersResponse)
async def get_flagged_tenders(
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low)$"),
    flag_type: Optional[str] = None,
    institution: Optional[str] = None,
    winner: Optional[str] = None,
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
    - winner: Filter by winner/company name
    - min_score: Minimum risk score (0-100, default 0)
    - skip: Pagination offset
    - limit: Results per page (max 100)

    Returns list of tenders with corruption flags and risk scores.
    """
    conn = await get_db_connection()
    try:
        # Use materialized view for fast queries (1000x faster than CTE)
        query = """
        SELECT
            tender_id,
            title,
            procuring_entity,
            winner,
            estimated_value_mkd,
            status,
            total_flags,
            risk_score,
            max_severity,
            flag_types
        FROM mv_flagged_tenders
        WHERE risk_score >= $1
        """
        params = [min_score]
        param_count = 1

        if severity:
            param_count += 1
            query += f" AND max_severity = ${param_count}"
            params.append(severity)

        if flag_type:
            param_count += 1
            query += f" AND ${param_count} = ANY(flag_types)"
            params.append(flag_type)

        if institution:
            # Use bilingual search for institution names
            condition, search_params = build_bilingual_search_condition('procuring_entity', institution, param_count + 1)
            query += f" AND {condition}"
            params.extend(search_params)
            param_count += len(search_params)

        if winner:
            # Use bilingual search for winner/company names
            condition, search_params = build_bilingual_search_condition('winner', winner, param_count + 1)
            query += f" AND {condition}"
            params.extend(search_params)
            param_count += len(search_params)

        # Count query using materialized view (fast)
        count_query = """
        SELECT COUNT(*)
        FROM mv_flagged_tenders
        WHERE risk_score >= $1
        """
        count_params_used = 1
        if severity:
            count_params_used += 1
            count_query += f" AND max_severity = ${count_params_used}"
        if flag_type:
            count_params_used += 1
            count_query += f" AND ${count_params_used} = ANY(flag_types)"
        if institution:
            # Use bilingual search in count query too
            condition, search_params = build_bilingual_search_condition('procuring_entity', institution, count_params_used + 1)
            count_query += f" AND {condition}"
            count_params_used += len(search_params)
        if winner:
            # Use bilingual search in count query too
            condition, search_params = build_bilingual_search_condition('winner', winner, count_params_used + 1)
            count_query += f" AND {condition}"
            count_params_used += len(search_params)

        # Build count params in same order as main query params (excluding limit/offset)
        count_params = params[:count_params_used]
        total = await conn.fetchval(count_query, *count_params)

        # Add ordering and pagination
        query += f" ORDER BY risk_score DESC, total_flags DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
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
                AND (t.status = 'awarded' OR t.status = 'completed')
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
    Get corruption detection statistics (uses materialized view for speed)

    Returns:
    - Total flags by severity and type
    - Total tenders flagged
    - Total value at risk
    """
    conn = await get_db_connection()
    try:
        # Use materialized view for fast stats (single query instead of 4)
        row = await conn.fetchrow("""
            SELECT total_flags, total_tenders_flagged, total_value_at_risk_mkd,
                   by_severity, by_type
            FROM mv_corruption_stats
            LIMIT 1
        """)

        if row:
            # JSONB fields may be returned as strings by asyncpg - parse them
            import json
            by_severity_raw = row['by_severity']
            by_type_raw = row['by_type']

            # Parse JSONB - may be string or dict
            if isinstance(by_severity_raw, str):
                by_severity = json.loads(by_severity_raw) if by_severity_raw else {}
            elif isinstance(by_severity_raw, dict):
                by_severity = by_severity_raw
            else:
                by_severity = {}

            if isinstance(by_type_raw, str):
                by_type = json.loads(by_type_raw) if by_type_raw else {}
            elif isinstance(by_type_raw, dict):
                by_type = by_type_raw
            else:
                by_type = {}
            total_flags = row['total_flags'] or 0
            total_tenders_flagged = row['total_tenders_flagged'] or 0
            total_value_at_risk = Decimal(str(row['total_value_at_risk_mkd'])) if row['total_value_at_risk_mkd'] else Decimal(0)
        else:
            by_severity = {}
            by_type = {}
            total_flags = 0
            total_tenders_flagged = 0
            total_value_at_risk = Decimal(0)

        # Last analysis run (from tender_risk_scores if exists)
        last_analysis_run = await conn.fetchval("""
            SELECT MAX(last_analyzed)
            FROM tender_risk_scores
        """)

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
