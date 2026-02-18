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
from middleware.entitlements import require_module
from middleware.rbac import require_admin
from config.plans import ModuleName
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field
import asyncpg

from db_pool import get_asyncpg_pool
from utils.risk_levels import calculate_risk_level

logger = logging.getLogger(__name__)


# ============================================================================
# ROUTER CONFIGURATION
# ============================================================================

router = APIRouter(
    prefix="/api/corruption",
    tags=["Corruption Detection"]
)


# ============================================================================
# FLAG TYPE CONSTANTS
# ============================================================================

# All 15 corruption indicator flag types
ALL_FLAG_TYPES = [
    'single_bidder',
    'repeat_winner',
    'price_anomaly',
    'bid_clustering',
    'short_deadline',
    'procedure_type',
    'identical_bids',
    'professional_loser',
    'contract_splitting',
    'short_decision',
    'strategic_disqualification',
    'contract_value_growth',
    'bid_rotation',
    'threshold_manipulation',
    'late_amendment',
]

# Corruption Risk Index (CRI) weights per flag type
CRI_WEIGHTS = {
    'single_bidder': 1.0,
    'procedure_type': 1.2,
    'contract_splitting': 1.3,
    'identical_bids': 1.5,
    'strategic_disqualification': 1.4,
    'bid_rotation': 1.2,
    'professional_loser': 0.8,
    'short_deadline': 0.9,
    'short_decision': 1.0,
    'contract_value_growth': 1.0,
    'late_amendment': 0.9,
    'threshold_manipulation': 0.8,
    'repeat_winner': 1.1,
    'price_anomaly': 1.1,
    'bid_clustering': 1.2,
}

# Sum of all possible weights (used as denominator in CRI formula)
CRI_MAX_WEIGHT = sum(CRI_WEIGHTS.values())

# Human-readable labels in Macedonian
FLAG_TYPE_LABELS = {
    'single_bidder': 'Единствен понудувач',
    'repeat_winner': 'Повторен победник',
    'price_anomaly': 'Ценовна аномалија',
    'bid_clustering': 'Кластер на понудувачи',
    'short_deadline': 'Краток рок',
    'procedure_type': 'Ризична постапка',
    'identical_bids': 'Идентични понуди',
    'professional_loser': 'Професионален губитник',
    'contract_splitting': 'Делење на договори',
    'short_decision': 'Брза одлука',
    'strategic_disqualification': 'Стратешка дисквалификација',
    'contract_value_growth': 'Раст на вредност',
    'bid_rotation': 'Ротација на победници',
    'threshold_manipulation': 'Манипулација со прагови',
    'late_amendment': 'Доцен амандман',
}

# Valid flag_type values for query parameter validation
VALID_FLAG_TYPES = set(ALL_FLAG_TYPES)


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class FlagDetail(BaseModel):
    """Individual corruption flag detail"""
    flag_id: str
    flag_type: str
    flag_label: Optional[str] = None  # Human-readable label in Macedonian
    severity: str  # critical, high, medium, low
    score: int  # 0-100
    weight: Optional[float] = None  # CRI weight for this flag type
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
    """Get a connection from the shared pool."""
    pool = await get_asyncpg_pool()
    return await pool.acquire()


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

def _build_flagged_tenders_where(
    severity: Optional[str],
    flag_type: Optional[str],
    institution: Optional[str],
    winner: Optional[str],
    min_score: int,
) -> tuple[str, list, int]:
    """
    Build the WHERE clause, params list, and final param_count for
    mv_flagged_tenders queries (used by both the data query and count query).

    Returns:
        (where_clause, params, param_count)
        where_clause starts with "WHERE risk_score >= $1" and includes all
        applicable filters.
    """
    where = "WHERE risk_score >= $1"
    params: list = [min_score]
    param_count = 1

    if severity:
        param_count += 1
        where += f" AND max_severity = ${param_count}"
        params.append(severity)

    if flag_type:
        param_count += 1
        where += f" AND ${param_count} = ANY(flag_types)"
        params.append(flag_type)

    if institution:
        condition, search_params = build_bilingual_search_condition(
            'procuring_entity', institution, param_count + 1
        )
        where += f" AND {condition}"
        params.extend(search_params)
        param_count += len(search_params)

    if winner:
        condition, search_params = build_bilingual_search_condition(
            'winner', winner, param_count + 1
        )
        where += f" AND {condition}"
        params.extend(search_params)
        param_count += len(search_params)

    return where, params, param_count


@router.get("/flagged-tenders", response_model=FlaggedTendersResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_flagged_tenders(
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low)$"),
    flag_type: Optional[str] = Query(None, description="Filter by flag type (one of 15 corruption indicators)"),
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
    # Validate flag_type against the canonical list of 15 types
    if flag_type and flag_type not in VALID_FLAG_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid flag_type '{flag_type}'. Valid types: {', '.join(sorted(VALID_FLAG_TYPES))}"
        )

    conn = await get_db_connection()
    try:
        where, params, param_count = _build_flagged_tenders_where(
            severity, flag_type, institution, winner, min_score
        )

        # Count query using materialized view (fast)
        count_query = f"SELECT COUNT(*) FROM mv_flagged_tenders {where}"
        total = await conn.fetchval(count_query, *params)

        # Use materialized view for fast queries (1000x faster than CTE)
        query = f"""
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
        {where}
        ORDER BY risk_score DESC, total_flags DESC
        LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
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
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# TENDER RISK ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/tender/{tender_id}/analysis", response_model=TenderRiskAnalysis, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
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
        type_max_scores = {}  # {flag_type: (max_score, weight)}
        max_severity = 'low'
        severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}

        for row in flags_rows:
            flag_type = row['flag_type']
            is_false_positive = row['false_positive'] or False

            flags.append(FlagDetail(
                flag_id=str(row['flag_id']),
                flag_type=flag_type,
                flag_label=FLAG_TYPE_LABELS.get(flag_type),
                severity=row['severity'],
                score=row['score'] or 0,
                weight=CRI_WEIGHTS.get(flag_type, 1.0),
                evidence=row['evidence'],
                description=row['description'],
                detected_at=row['detected_at'],
                reviewed=row['reviewed'] or False,
                false_positive=is_false_positive,
                review_notes=row['review_notes']
            ))
            # Only non-false-positive flags contribute to CRI score
            if not is_false_positive:
                ft = row['flag_type']
                w = CRI_WEIGHTS.get(ft, 1.0)
                s = row['score'] or 0
                # Track max score per type (weighted)
                existing = type_max_scores.get(ft, (0, 0))
                if s > existing[0]:
                    type_max_scores[ft] = (s, w)
                if severity_order.get(row['severity'], 0) > severity_order.get(max_severity, 0):
                    max_severity = row['severity']

        # CRI formula: weighted average of per-type max scores + multi-indicator bonus
        if type_max_scores:
            total_ws = sum(s * w for s, w in type_max_scores.values())
            total_w = sum(w for _, w in type_max_scores.values())
            base_score = total_ws / total_w if total_w > 0 else 0
            bonus = 8 * (len(type_max_scores) - 1) if len(type_max_scores) > 1 else 0
            risk_score = min(100, round(base_score + bonus))
        else:
            risk_score = 0
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
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# INSTITUTION RISK ENDPOINTS
# ============================================================================

@router.get("/institutions/risk", response_model=InstitutionsRiskResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
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
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# SUSPICIOUS COMPANIES ENDPOINTS
# ============================================================================

@router.get("/companies/suspicious", response_model=SuspiciousCompaniesResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
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
                SUM(COALESCE(t.actual_value_mkd, t.estimated_value_mkd)) as total_contract_value,
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
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# FLAG REVIEW ENDPOINTS
# ============================================================================

@router.post("/flags/{flag_id}/review", response_model=FlagReviewResponse, dependencies=[Depends(require_admin)])
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
                review_notes = $3,
                reviewed_at = NOW()
            WHERE flag_id = $1::uuid
            RETURNING flag_id, reviewed, false_positive, review_notes, reviewed_at
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
            reviewed_at=result['reviewed_at']
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
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@router.get("/stats", response_model=CorruptionStats, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
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

        # Ensure all 15 flag types are present in by_type, defaulting to 0
        for ft in ALL_FLAG_TYPES:
            if ft not in by_type:
                by_type[ft] = 0

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
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# TRIGGER ANALYSIS ENDPOINT
# ============================================================================

@router.post("/analyze", response_model=MessageResponse, dependencies=[Depends(require_admin)])
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


# ============================================================================
# ML PREDICTION SCHEMAS
# ============================================================================

class MLPredictionRequest(BaseModel):
    """Request for ML prediction"""
    update_db: bool = Field(True, description="Whether to store prediction in database")


class BatchPredictionRequest(BaseModel):
    """Request for batch ML prediction"""
    tender_ids: List[str] = Field(..., min_length=1, max_length=100, description="List of tender IDs to predict")
    update_db: bool = Field(True, description="Whether to store predictions in database")


class FeatureContribution(BaseModel):
    """Individual feature contribution to prediction"""
    feature_name: str
    value: float
    contribution: float
    description: Optional[str] = None
    category: Optional[str] = None


class MLPredictionDetail(BaseModel):
    """Detailed ML prediction result"""
    tender_id: str
    risk_score: float = Field(..., ge=0, le=100)
    risk_level: str
    confidence: float = Field(..., ge=0, le=1)
    model_scores: Dict[str, float]
    top_features: Optional[List[FeatureContribution]] = None
    predicted_at: datetime
    model_version: Optional[str] = None

    class Config:
        from_attributes = True


class MLPredictionResponse(BaseModel):
    """Response for single ML prediction"""
    prediction: MLPredictionDetail
    tender_info: Optional[Dict[str, Any]] = None
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class MLPredictionsListResponse(BaseModel):
    """Response for listing predictions"""
    total: int
    skip: int
    limit: int
    predictions: List[MLPredictionDetail]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class BatchPredictionResponse(BaseModel):
    """Response for batch prediction"""
    batch_id: str
    total_requested: int
    total_processed: int
    high_risk_count: int
    critical_count: int
    failed_count: int
    predictions: List[MLPredictionDetail]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


# ============================================================================
# ML PREDICTION HELPER FUNCTIONS
# ============================================================================

# Model version - update when models are retrained
ML_MODEL_VERSION = "v1.0.0"


async def _get_or_create_predictor():
    """
    Get or create the ML predictor instance.
    Lazy-loaded to avoid import issues if ML deps not installed.
    """
    try:
        from ai.corruption.ml_models import CorruptionPredictor, PredictionResult
        from pathlib import Path
        import os

        models_dir = Path(__file__).parent.parent.parent / "ai" / "corruption" / "ml_models" / "models"
        predictor = CorruptionPredictor(
            models_dir=str(models_dir),
            db_url=os.getenv("DATABASE_URL")
        )
        await predictor.initialize()
        return predictor
    except ImportError as e:
        logger.error(f"ML dependencies not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ML prediction models not available. Install required dependencies."
        )
    except Exception as e:
        logger.error(f"Failed to initialize predictor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize ML predictor: {str(e)}"
        )


async def _store_prediction(
    conn: asyncpg.Connection,
    tender_id: str,
    risk_score: float,
    risk_level: str,
    confidence: float,
    model_scores: Dict[str, float],
    top_features: Optional[List[Dict[str, Any]]] = None,
    feature_importance: Optional[Dict[str, float]] = None
) -> int:
    """Store ML prediction in database"""
    import json

    result = await conn.fetchval("""
        INSERT INTO ml_predictions (
            tender_id, risk_score, risk_level, confidence,
            model_scores, top_features, feature_importance,
            model_version, predicted_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        ON CONFLICT (tender_id, model_version)
        DO UPDATE SET
            risk_score = EXCLUDED.risk_score,
            risk_level = EXCLUDED.risk_level,
            confidence = EXCLUDED.confidence,
            model_scores = EXCLUDED.model_scores,
            top_features = EXCLUDED.top_features,
            feature_importance = EXCLUDED.feature_importance,
            updated_at = NOW()
        RETURNING id
    """,
        tender_id,
        round(risk_score, 2),
        risk_level,
        round(confidence, 3),
        json.dumps(model_scores),
        json.dumps(top_features) if top_features else None,
        json.dumps(feature_importance) if feature_importance else None,
        ML_MODEL_VERSION
    )
    return result


def _build_feature_contributions(
    top_features: Optional[List[Dict[str, Any]]]
) -> Optional[List[FeatureContribution]]:
    """Convert top features to FeatureContribution objects"""
    if not top_features:
        return None

    return [
        FeatureContribution(
            feature_name=f.get('feature_name', 'unknown'),
            value=float(f.get('feature_value', 0)),
            contribution=float(f.get('contribution', 0)),
            description=f.get('description'),
            category=f.get('category')
        )
        for f in top_features[:10]  # Limit to top 10
    ]


# ============================================================================
# ML PREDICTION ENDPOINTS
# ============================================================================

@router.post("/predict/{tender_id}", response_model=MLPredictionResponse)
async def predict_tender(
    tender_id: str,
    request: Optional[MLPredictionRequest] = None
):
    """
    Run ML prediction on a single tender.

    This endpoint uses the ensemble model (Random Forest + XGBoost + Neural Network)
    to generate a corruption risk score for the specified tender.

    Path Parameters:
    - tender_id: The tender ID to analyze

    Request Body (optional):
    - update_db: Whether to store the prediction in the database (default: True)

    Returns:
    - Prediction with risk score (0-100), risk level, confidence, and feature importance
    """
    update_db = request.update_db if request else True

    conn = await get_db_connection()
    try:
        # First verify tender exists
        tender = await conn.fetchrow("""
            SELECT tender_id, title, procuring_entity, winner,
                   estimated_value_mkd, status
            FROM tenders
            WHERE tender_id = $1
        """, tender_id)

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Try to use ML predictor
        try:
            predictor = await _get_or_create_predictor()
            result = await predictor.predict_single(tender_id, update_db=False)
            await predictor.cleanup()

            if not result:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Could not extract features for tender {tender_id}"
                )

            # Store prediction if requested
            if update_db:
                await _store_prediction(
                    conn,
                    tender_id=tender_id,
                    risk_score=result.risk_score,
                    risk_level=result.risk_level,
                    confidence=result.confidence,
                    model_scores=result.model_scores,
                    top_features=None,  # Would need explainer for this
                    feature_importance=result.feature_contributions
                )

            prediction = MLPredictionDetail(
                tender_id=tender_id,
                risk_score=round(result.risk_score, 2),
                risk_level=result.risk_level,
                confidence=round(result.confidence, 3),
                model_scores={k: round(v, 2) for k, v in result.model_scores.items()},
                top_features=None,
                predicted_at=datetime.utcnow(),
                model_version=ML_MODEL_VERSION
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"ML prediction failed, using fallback: {e}")
            # Fallback: use existing corruption flags to calculate score
            flags = await conn.fetch("""
                SELECT score FROM corruption_flags
                WHERE tender_id = $1 AND false_positive = FALSE
            """, tender_id)

            if flags:
                risk_score = min(100, sum(f['score'] for f in flags))
                risk_level = calculate_risk_level(risk_score)
            else:
                risk_score = 0
                risk_level = "minimal"

            prediction = MLPredictionDetail(
                tender_id=tender_id,
                risk_score=float(risk_score),
                risk_level=risk_level,
                confidence=0.5,  # Lower confidence for fallback
                model_scores={"fallback": float(risk_score)},
                top_features=None,
                predicted_at=datetime.utcnow(),
                model_version="fallback"
            )

        tender_info = {
            "title": tender['title'],
            "procuring_entity": tender['procuring_entity'],
            "winner": tender['winner'],
            "estimated_value_mkd": float(tender['estimated_value_mkd']) if tender['estimated_value_mkd'] else None,
            "status": tender['status']
        }

        return MLPredictionResponse(
            prediction=prediction,
            tender_info=tender_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting tender {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate prediction: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


@router.get("/predictions", response_model=MLPredictionsListResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def list_predictions(
    min_score: float = Query(0, ge=0, le=100, description="Minimum risk score"),
    risk_level: Optional[str] = Query(None, pattern="^(minimal|low|medium|high|critical)$"),
    institution: Optional[str] = None,
    winner: Optional[str] = None,
    days: int = Query(30, ge=1, le=365, description="Predictions from last N days"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List recent ML predictions with filtering.

    Query Parameters:
    - min_score: Minimum risk score (0-100, default 0)
    - risk_level: Filter by risk level (minimal/low/medium/high/critical)
    - institution: Filter by procuring entity name (supports bilingual search)
    - winner: Filter by winner name (supports bilingual search)
    - days: Predictions from last N days (default 30)
    - skip: Pagination offset
    - limit: Results per page (max 100)

    Returns paginated list of predictions with tender details.
    """
    conn = await get_db_connection()
    try:
        query = """
        SELECT
            mp.id,
            mp.tender_id,
            mp.risk_score,
            mp.risk_level,
            mp.confidence,
            mp.model_scores,
            mp.top_features,
            mp.predicted_at,
            mp.model_version,
            t.title,
            t.procuring_entity,
            t.winner,
            t.estimated_value_mkd
        FROM ml_predictions mp
        JOIN tenders t ON mp.tender_id = t.tender_id
        WHERE mp.risk_score >= $1
          AND mp.predicted_at > NOW() - INTERVAL '1 day' * $2
        """
        params = [min_score, days]
        param_count = 2

        if risk_level:
            param_count += 1
            query += f" AND mp.risk_level = ${param_count}"
            params.append(risk_level)

        if institution:
            condition, search_params = build_bilingual_search_condition(
                't.procuring_entity', institution, param_count + 1
            )
            query += f" AND {condition}"
            params.extend(search_params)
            param_count += len(search_params)

        if winner:
            condition, search_params = build_bilingual_search_condition(
                't.winner', winner, param_count + 1
            )
            query += f" AND {condition}"
            params.extend(search_params)
            param_count += len(search_params)

        # Count query
        count_query = query.replace(
            "SELECT\n            mp.id,",
            "SELECT COUNT(*) FROM ("
        ) + ") subq"
        # Simpler count approach
        count_params = params.copy()

        # Get total count
        count_result = await conn.fetchval(f"""
            SELECT COUNT(*) FROM ml_predictions mp
            JOIN tenders t ON mp.tender_id = t.tender_id
            WHERE mp.risk_score >= $1
              AND mp.predicted_at > NOW() - INTERVAL '1 day' * $2
              {f"AND mp.risk_level = ${3}" if risk_level else ""}
        """, *params[:3] if risk_level else params[:2])

        # Add ordering and pagination
        query += f" ORDER BY mp.risk_score DESC, mp.predicted_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
        params.extend([limit, skip])

        rows = await conn.fetch(query, *params)

        predictions = []
        for row in rows:
            # Parse JSONB fields
            model_scores_raw = row['model_scores']
            if isinstance(model_scores_raw, str):
                import json
                model_scores = json.loads(model_scores_raw) if model_scores_raw else {}
            else:
                model_scores = model_scores_raw or {}

            top_features_raw = row['top_features']
            if isinstance(top_features_raw, str):
                import json
                top_features_data = json.loads(top_features_raw) if top_features_raw else None
            else:
                top_features_data = top_features_raw

            predictions.append(MLPredictionDetail(
                tender_id=row['tender_id'],
                risk_score=float(row['risk_score']),
                risk_level=row['risk_level'],
                confidence=float(row['confidence']) if row['confidence'] else 0.5,
                model_scores={k: float(v) for k, v in model_scores.items()},
                top_features=_build_feature_contributions(top_features_data),
                predicted_at=row['predicted_at'],
                model_version=row['model_version']
            ))

        return MLPredictionsListResponse(
            total=count_result or 0,
            skip=skip,
            limit=limit,
            predictions=predictions
        )

    except Exception as e:
        logger.error(f"Error listing predictions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list predictions: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


@router.get("/predictions/{tender_id}", response_model=MLPredictionResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_prediction(tender_id: str):
    """
    Get the latest ML prediction for a specific tender.

    Path Parameters:
    - tender_id: The tender ID

    Returns:
    - Most recent prediction with risk score, confidence, model scores, and feature importance
    - Returns 404 if no prediction exists for this tender
    """
    conn = await get_db_connection()
    try:
        # Get tender info
        tender = await conn.fetchrow("""
            SELECT tender_id, title, procuring_entity, winner,
                   estimated_value_mkd, status
            FROM tenders
            WHERE tender_id = $1
        """, tender_id)

        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Get latest prediction
        prediction_row = await conn.fetchrow("""
            SELECT
                tender_id, risk_score, risk_level, confidence,
                model_scores, top_features, feature_importance,
                predicted_at, model_version
            FROM ml_predictions
            WHERE tender_id = $1
            ORDER BY predicted_at DESC
            LIMIT 1
        """, tender_id)

        if not prediction_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No ML prediction found for tender {tender_id}. Use POST /api/corruption/predict/{tender_id} to generate one."
            )

        # Parse JSONB fields
        import json
        model_scores_raw = prediction_row['model_scores']
        if isinstance(model_scores_raw, str):
            model_scores = json.loads(model_scores_raw) if model_scores_raw else {}
        else:
            model_scores = model_scores_raw or {}

        top_features_raw = prediction_row['top_features']
        if isinstance(top_features_raw, str):
            top_features_data = json.loads(top_features_raw) if top_features_raw else None
        else:
            top_features_data = top_features_raw

        prediction = MLPredictionDetail(
            tender_id=prediction_row['tender_id'],
            risk_score=float(prediction_row['risk_score']),
            risk_level=prediction_row['risk_level'],
            confidence=float(prediction_row['confidence']) if prediction_row['confidence'] else 0.5,
            model_scores={k: float(v) for k, v in model_scores.items()},
            top_features=_build_feature_contributions(top_features_data),
            predicted_at=prediction_row['predicted_at'],
            model_version=prediction_row['model_version']
        )

        tender_info = {
            "title": tender['title'],
            "procuring_entity": tender['procuring_entity'],
            "winner": tender['winner'],
            "estimated_value_mkd": float(tender['estimated_value_mkd']) if tender['estimated_value_mkd'] else None,
            "status": tender['status']
        }

        return MLPredictionResponse(
            prediction=prediction,
            tender_info=tender_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prediction for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prediction: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


@router.post("/batch-predict", response_model=BatchPredictionResponse, dependencies=[Depends(require_admin)])
async def batch_predict(
    request: BatchPredictionRequest,
    background_tasks: BackgroundTasks
):
    """
    Run ML predictions on multiple tenders.

    This endpoint processes multiple tenders in a single batch, which is more
    efficient than calling the single prediction endpoint multiple times.

    Request Body:
    - tender_ids: List of tender IDs to analyze (max 100)
    - update_db: Whether to store predictions in database (default: True)

    Returns:
    - Batch summary with predictions for each tender
    - Failed tenders are noted separately

    Note: For large batches (>100), consider using the background prediction pipeline.
    """
    import uuid
    batch_id = str(uuid.uuid4())

    conn = await get_db_connection()
    try:
        # Verify all tenders exist
        tender_ids = request.tender_ids
        existing = await conn.fetch("""
            SELECT tender_id FROM tenders
            WHERE tender_id = ANY($1::varchar[])
        """, tender_ids)

        existing_ids = {r['tender_id'] for r in existing}
        missing_ids = set(tender_ids) - existing_ids

        if len(missing_ids) == len(tender_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="None of the specified tenders were found"
            )

        predictions = []
        failed_ids = list(missing_ids)
        high_risk_count = 0
        critical_count = 0

        # Try to use ML predictor for batch prediction
        try:
            predictor = await _get_or_create_predictor()
            valid_ids = list(existing_ids)

            # Process in batches of 50
            batch_size = 50
            for i in range(0, len(valid_ids), batch_size):
                batch_ids = valid_ids[i:i + batch_size]
                results = await predictor.predict_batch(batch_ids)

                for result in results:
                    # Store prediction if requested
                    if request.update_db:
                        try:
                            await _store_prediction(
                                conn,
                                tender_id=result.tender_id,
                                risk_score=result.risk_score,
                                risk_level=result.risk_level,
                                confidence=result.confidence,
                                model_scores=result.model_scores
                            )
                        except Exception as e:
                            logger.warning(f"Failed to store prediction for {result.tender_id}: {e}")

                    prediction = MLPredictionDetail(
                        tender_id=result.tender_id,
                        risk_score=round(result.risk_score, 2),
                        risk_level=result.risk_level,
                        confidence=round(result.confidence, 3),
                        model_scores={k: round(v, 2) for k, v in result.model_scores.items()},
                        top_features=None,
                        predicted_at=datetime.utcnow(),
                        model_version=ML_MODEL_VERSION
                    )
                    predictions.append(prediction)

                    if result.risk_level == 'critical':
                        critical_count += 1
                    elif result.risk_level == 'high':
                        high_risk_count += 1

            await predictor.cleanup()

        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"ML batch prediction failed, using fallback: {e}")
            # Fallback: use existing flags
            for tid in existing_ids:
                flags = await conn.fetch("""
                    SELECT score FROM corruption_flags
                    WHERE tender_id = $1 AND false_positive = FALSE
                """, tid)

                if flags:
                    risk_score = min(100, sum(f['score'] for f in flags))
                    risk_level = calculate_risk_level(risk_score)
                else:
                    risk_score = 0
                    risk_level = "minimal"

                prediction = MLPredictionDetail(
                    tender_id=tid,
                    risk_score=float(risk_score),
                    risk_level=risk_level,
                    confidence=0.5,
                    model_scores={"fallback": float(risk_score)},
                    top_features=None,
                    predicted_at=datetime.utcnow(),
                    model_version="fallback"
                )
                predictions.append(prediction)

                if risk_level == 'critical':
                    critical_count += 1
                elif risk_level == 'high':
                    high_risk_count += 1

        # Store batch record
        try:
            await conn.execute("""
                INSERT INTO ml_prediction_batches (
                    batch_id, started_at, completed_at, status,
                    total_tenders, processed_count, high_risk_count, critical_count,
                    failed_tender_ids, model_version
                ) VALUES ($1, NOW(), NOW(), 'completed', $2, $3, $4, $5, $6, $7)
            """,
                uuid.UUID(batch_id),
                len(tender_ids),
                len(predictions),
                high_risk_count,
                critical_count,
                failed_ids if failed_ids else None,
                ML_MODEL_VERSION
            )
        except Exception as e:
            logger.warning(f"Failed to store batch record: {e}")

        return BatchPredictionResponse(
            batch_id=batch_id,
            total_requested=len(tender_ids),
            total_processed=len(predictions),
            high_risk_count=high_risk_count,
            critical_count=critical_count,
            failed_count=len(failed_ids),
            predictions=predictions
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run batch prediction: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)
