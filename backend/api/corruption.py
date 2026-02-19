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
from utils.confidence import bootstrap_cri_confidence, compute_data_completeness, classify_uncertainty
from utils.weight_calibration import (
    get_current_weights as get_db_weights,
    compute_updated_weights,
    apply_weight_update,
    get_weight_history as fetch_weight_history,
    DEFAULT_CRI_WEIGHTS,
)
from utils.active_sampler import (
    get_queue_items,
    refresh_active_queue,
)

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


async def get_effective_cri_weights() -> Dict[str, float]:
    """
    Get CRI weights, checking DB for calibrated weights first.
    Falls back to hardcoded CRI_WEIGHTS if no DB weights are available.
    """
    try:
        pool = await get_asyncpg_pool()
        return await get_db_weights(pool)
    except Exception as e:
        logger.debug(f"Using hardcoded CRI_WEIGHTS (DB lookup failed: {e})")
        return dict(CRI_WEIGHTS)


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
    has_winner: bool = True
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
    confidence_interval: Optional[List[float]] = None  # [lower, upper] on 0-100 scale
    uncertainty: Optional[str] = None  # 'low', 'medium', 'high'
    data_completeness: Optional[float] = None  # 0.0-1.0 fraction of ML features present
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
            COALESCE(has_winner, winner IS NOT NULL) as has_winner,
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
                has_winner=row.get('has_winner', row['winner'] is not None),
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

@router.get("/tender/{tender_id:path}/analysis", response_model=TenderRiskAnalysis, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_tender_analysis(
    tender_id: str,
    include_ci: bool = Query(True, description="Include bootstrap confidence interval (adds ~20ms)")
):
    """
    Get detailed corruption risk analysis for a specific tender

    Query Parameters:
    - include_ci: Whether to compute bootstrap confidence interval (default: true).
                  Set to false for faster responses when CI is not needed.

    Returns:
    - All corruption flags with evidence
    - Risk score and level with optional confidence interval
    - Uncertainty classification and data completeness
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

        # Load effective CRI weights (DB-calibrated or hardcoded fallback)
        effective_weights = await get_effective_cri_weights()

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
                weight=effective_weights.get(flag_type, 1.0),
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
                w = effective_weights.get(ft, 1.0)
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

        # --- Confidence interval and uncertainty quantification ---
        ci_lower_val = None
        ci_upper_val = None
        uncertainty_val = None
        data_completeness_val = None

        if include_ci and type_max_scores:
            # Build flag_scores dict: {flag_type: max_score}
            flag_scores_for_ci = {ft: s for ft, (s, _w) in type_max_scores.items()}

            _cri, ci_lower_val, ci_upper_val = bootstrap_cri_confidence(
                flag_scores=flag_scores_for_ci,
                cri_weights=effective_weights,
                n_bootstrap=1000,
                confidence_level=0.90,
            )

            # Data completeness: check how many fields the tender has populated
            # Use tender metadata + flag evidence as a proxy for ML feature availability
            feature_proxy: Dict[str, Any] = {
                'title': tender['title'],
                'procuring_entity': tender['procuring_entity'],
                'winner': tender['winner'],
                'estimated_value_mkd': float(tender['estimated_value_mkd']) if tender['estimated_value_mkd'] else None,
                'status': tender['status'],
            }
            # Each flag type detected counts as evidence for ~7 features (112 / 15 types ~ 7)
            for ft, (s, _w) in type_max_scores.items():
                feature_proxy[f'flag_{ft}_score'] = s
            # Query additional tender fields for completeness estimate
            extra_fields = await conn.fetchrow("""
                SELECT
                    publication_date, closing_date, opening_date,
                    actual_value_mkd, num_bidders, cpv_code,
                    category, description, amendment_count,
                    has_lots, num_lots, evaluation_method
                FROM tenders WHERE tender_id = $1
            """, tender_id)
            if extra_fields:
                for col in extra_fields.keys():
                    feature_proxy[col] = extra_fields[col]

            data_completeness_val = round(compute_data_completeness(feature_proxy, total_features=112), 2)

            ci_width = ci_upper_val - ci_lower_val
            uncertainty_val = classify_uncertainty(ci_width, data_completeness_val)

        return TenderRiskAnalysis(
            tender_id=tender['tender_id'],
            title=tender['title'],
            procuring_entity=tender['procuring_entity'],
            winner=tender['winner'],
            estimated_value_mkd=tender['estimated_value_mkd'],
            status=tender['status'],
            risk_score=risk_score,
            risk_level=risk_level,
            confidence_interval=[ci_lower_val, ci_upper_val] if ci_lower_val is not None else None,
            uncertainty=uncertainty_val,
            data_completeness=data_completeness_val,
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

@router.post("/predict/{tender_id:path}", response_model=MLPredictionResponse)
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


@router.get("/predictions/{tender_id:path}", response_model=MLPredictionResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
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


# ============================================================================
# ACTIVE LEARNING SCHEMAS
# ============================================================================

class ReviewSubmission(BaseModel):
    """Submit an analyst review for a flagged tender."""
    tender_id: str = Field(..., description="Tender ID being reviewed")
    flag_id: Optional[int] = Field(None, description="Specific flag ID (optional)")
    analyst_verdict: str = Field(
        ...,
        pattern="^(confirmed_fraud|likely_fraud|uncertain|false_positive|not_reviewed)$",
        description="Analyst verdict"
    )
    confidence: int = Field(..., ge=1, le=5, description="Confidence level 1-5")
    evidence_notes: Optional[str] = Field(None, max_length=5000, description="Notes and evidence")
    review_source: str = Field(
        "manual",
        pattern="^(manual|active_learning|bulk_review)$",
        description="Source of review"
    )


class ReviewResponse(BaseModel):
    """Response after submitting a review."""
    review_id: int
    tender_id: str
    analyst_verdict: str
    confidence: int
    reviewed_at: datetime


class ReviewQueueItem(BaseModel):
    """Item in the active learning review queue."""
    queue_id: int
    tender_id: str
    priority_score: float
    selection_reason: str
    selected_at: Optional[str] = None
    title: Optional[str] = None
    procuring_entity: Optional[str] = None
    winner: Optional[str] = None
    estimated_value_mkd: Optional[float] = None
    status: Optional[str] = None
    risk_score: Optional[int] = None
    total_flags: Optional[int] = None
    flag_types: Optional[List[str]] = None
    max_severity: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    """Response for the review queue endpoint."""
    total: int
    items: List[ReviewQueueItem]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција."


class WeightHistoryItem(BaseModel):
    """A single CRI weight calibration history entry."""
    history_id: int
    weights: Dict[str, float]
    num_reviews_used: Optional[int] = None
    avg_agreement_rate: Optional[float] = None
    computed_at: Optional[str] = None
    applied: bool = False
    notes: Optional[str] = None


class WeightHistoryResponse(BaseModel):
    """Response for weight history endpoint."""
    current_weights: Dict[str, float]
    history: List[WeightHistoryItem]


class CalibrationResult(BaseModel):
    """Response for weight calibration trigger."""
    success: bool
    message: str
    new_weights: Optional[Dict[str, float]] = None
    num_reviews_used: Optional[int] = None
    avg_agreement_rate: Optional[float] = None
    error: Optional[str] = None


# ============================================================================
# ACTIVE LEARNING & REVIEW ENDPOINTS
# ============================================================================

@router.get("/review-queue", response_model=ReviewQueueResponse, dependencies=[Depends(require_admin)])
async def get_review_queue(
    limit: int = Query(20, ge=1, le=100, description="Number of items to return")
):
    """
    Get top-N tenders from the active learning queue for analyst review.

    The queue is populated by the active learning sampler which selects
    the most informative tenders to label, using three strategies:
    - **boundary**: tenders near the CRI decision boundary (~50 risk score)
    - **disagreement**: tenders where rule-based CRI and ML predictions disagree
    - **novel**: tenders with rare flag combinations not seen before

    Returns items sorted by priority score (highest first).
    """
    pool = await get_asyncpg_pool()
    try:
        items = await get_queue_items(pool, limit=limit, include_tender_info=True)

        queue_items = [
            ReviewQueueItem(**item)
            for item in items
        ]

        return ReviewQueueResponse(
            total=len(queue_items),
            items=queue_items,
        )

    except Exception as e:
        logger.error(f"Error fetching review queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch review queue: {str(e)}"
        )


@router.post("/reviews", response_model=ReviewResponse, dependencies=[Depends(require_admin)])
async def submit_review(review: ReviewSubmission):
    """
    Submit an analyst review for a flagged tender.

    This is the core active learning feedback loop:
    1. Analyst reviews a tender from the review queue
    2. Their verdict is stored in corruption_reviews
    3. The corresponding active_learning_queue item is marked as reviewed
    4. When enough reviews accumulate (50+), weight calibration can be triggered

    Verdicts:
    - **confirmed_fraud**: analyst confirms corruption indicators are real
    - **likely_fraud**: analyst thinks corruption is likely but not certain
    - **uncertain**: not enough evidence to decide
    - **false_positive**: the flags are incorrect / not indicative of corruption
    - **not_reviewed**: placeholder, should not normally be submitted
    """
    conn = await get_db_connection()
    try:
        # Verify tender exists
        tender = await conn.fetchval(
            "SELECT tender_id FROM tenders WHERE tender_id = $1",
            review.tender_id,
        )
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {review.tender_id} not found"
            )

        # Insert the review
        result = await conn.fetchrow("""
            INSERT INTO corruption_reviews
                (tender_id, flag_id, analyst_verdict, confidence,
                 evidence_notes, review_source)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING review_id, tender_id, analyst_verdict, confidence, reviewed_at
        """,
            review.tender_id,
            review.flag_id,
            review.analyst_verdict,
            review.confidence,
            review.evidence_notes,
            review.review_source,
        )

        # Also update the original corruption_flags reviewed status
        # if a false_positive verdict was given
        if review.analyst_verdict == 'false_positive':
            if review.flag_id:
                await conn.execute("""
                    UPDATE corruption_flags
                    SET reviewed = TRUE, false_positive = TRUE,
                        review_notes = $2, reviewed_at = NOW()
                    WHERE flag_id = $1::integer::uuid
                """, review.flag_id, review.evidence_notes or 'Marked as false positive via active learning')
            else:
                # Mark all flags for this tender as false positive
                await conn.execute("""
                    UPDATE corruption_flags
                    SET reviewed = TRUE, false_positive = TRUE,
                        review_notes = $2, reviewed_at = NOW()
                    WHERE tender_id = $1 AND false_positive = FALSE
                """, review.tender_id, review.evidence_notes or 'Marked as false positive via active learning')

        # Mark the active learning queue item as reviewed
        await conn.execute("""
            UPDATE active_learning_queue
            SET reviewed = TRUE
            WHERE tender_id = $1
        """, review.tender_id)

        return ReviewResponse(
            review_id=result['review_id'],
            tender_id=result['tender_id'],
            analyst_verdict=result['analyst_verdict'],
            confidence=result['confidence'],
            reviewed_at=result['reviewed_at'],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit review: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


@router.get("/weight-history", response_model=WeightHistoryResponse, dependencies=[Depends(require_admin)])
async def get_weight_history_endpoint(
    limit: int = Query(20, ge=1, le=100, description="Number of history entries")
):
    """
    Get CRI weight adjustment history.

    Shows the current active weights and a history of all calibration runs,
    including the number of reviews used, agreement rate, and whether the
    weights were applied.
    """
    pool = await get_asyncpg_pool()
    try:
        current = await get_effective_cri_weights()
        history_rows = await fetch_weight_history(pool, limit=limit)

        history_items = [
            WeightHistoryItem(**row)
            for row in history_rows
        ]

        return WeightHistoryResponse(
            current_weights=current,
            history=history_items,
        )

    except Exception as e:
        logger.error(f"Error fetching weight history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch weight history: {str(e)}"
        )


@router.post("/calibrate-weights", response_model=CalibrationResult, dependencies=[Depends(require_admin)])
async def trigger_weight_calibration():
    """
    Admin-only: trigger CRI weight recalculation from accumulated reviews.

    This runs logistic regression on all analyst reviews to learn which flag
    types are most predictive of actual corruption. Requirements:
    - At least 50 reviews with both fraud and non-fraud verdicts
    - Weight changes are capped at +/-20% per cycle for stability
    - New weights are stored in cri_weight_history and marked as applied

    The calibrated weights will immediately be used by the tender analysis
    endpoint for CRI score calculation.
    """
    pool = await get_asyncpg_pool()
    try:
        result = await compute_updated_weights(pool)

        if result.get('error') or result.get('weights') is None:
            return CalibrationResult(
                success=False,
                message="Calibration could not be completed",
                num_reviews_used=result.get('num_reviews', 0),
                error=result.get('error', 'Unknown error'),
            )

        # Apply the new weights
        applied = await apply_weight_update(
            pool,
            new_weights=result['weights'],
            num_reviews=result['num_reviews'],
            avg_agreement_rate=result['avg_agreement_rate'],
            notes="Triggered via admin API endpoint",
        )

        if not applied:
            return CalibrationResult(
                success=False,
                message="Weights computed but failed to apply",
                new_weights=result['weights'],
                num_reviews_used=result['num_reviews'],
                avg_agreement_rate=result['avg_agreement_rate'],
                error="Database update failed",
            )

        return CalibrationResult(
            success=True,
            message=f"CRI weights calibrated from {result['num_reviews']} reviews "
                    f"(agreement rate: {result['avg_agreement_rate']:.1%})",
            new_weights=result['weights'],
            num_reviews_used=result['num_reviews'],
            avg_agreement_rate=result['avg_agreement_rate'],
        )

    except Exception as e:
        logger.error(f"Error during weight calibration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calibrate weights: {str(e)}"
        )


@router.post("/refresh-review-queue", response_model=MessageResponse, dependencies=[Depends(require_admin)])
async def trigger_queue_refresh():
    """
    Admin-only: refresh the active learning review queue.

    Rebuilds the queue by selecting the most informative tenders for review
    using boundary, disagreement, and novelty strategies.
    Normally called by weekly cron, but can be triggered manually.
    """
    pool = await get_asyncpg_pool()
    try:
        count = await refresh_active_queue(pool)
        return MessageResponse(
            message=f"Active learning queue refreshed with {count} items",
            detail=f"Selected {count} tenders for review using boundary, disagreement, and novelty strategies"
        )
    except Exception as e:
        logger.error(f"Error refreshing review queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh review queue: {str(e)}"
        )


# ============================================================================
# ENTITY / NER SCHEMAS
# ============================================================================

class EntityMention(BaseModel):
    """Single entity mention from a document."""
    mention_id: int
    entity_text: str
    entity_type: str
    normalized_text: Optional[str] = None
    confidence: float = 1.0
    extraction_method: str = 'regex'
    context: Optional[str] = None
    tender_id: Optional[str] = None
    doc_id: Optional[str] = None

    class Config:
        from_attributes = True


class TenderEntitiesResponse(BaseModel):
    """Entities extracted from a tender's documents."""
    tender_id: str
    total_entities: int
    entities: List[EntityMention]
    summary: Dict[str, int]
    disclaimer: str = "Ентитетите се извлечени автоматски и може да содржат грешки."


class ConflictOfInterest(BaseModel):
    """Potential conflict of interest from entity analysis."""
    person_name: str
    institution: Optional[str] = None
    company: Optional[str] = None
    institution_tenders: Optional[List[str]] = None
    company_tenders: Optional[List[str]] = None
    mention_count: int = 0
    avg_confidence: Optional[float] = None


class ConflictsResponse(BaseModel):
    """Potential conflicts of interest list."""
    total: int
    conflicts: List[ConflictOfInterest]
    disclaimer: str = "Ова е автоматска анализа. Потенцијалните конфликти на интерес бараат дополнителна истрага."


class EntityNetworkResponse(BaseModel):
    """Entity co-occurrence network."""
    entity: Dict[str, Any]
    tenders: List[Dict[str, Any]]
    co_entities: List[Dict[str, Any]]


class EntityStatsResponse(BaseModel):
    """Aggregate entity statistics."""
    total_entities: int
    unique_entities: int
    by_type: Dict[str, int]
    by_method: Dict[str, int]
    documents_processed: int
    tenders_with_entities: int
    top_persons: List[Dict[str, Any]]
    top_orgs: List[Dict[str, Any]]
    last_processed: Optional[str] = None


# ============================================================================
# ENTITY / NER ENDPOINTS
# ============================================================================

@router.get("/entities/stats", response_model=EntityStatsResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_entity_stats():
    """
    Get aggregate statistics for extracted entities.

    Returns:
    - Total and unique entity counts
    - Breakdown by type (PERSON, ORG, MONEY, DATE, GPE, TAX_ID, LEGAL_REF, IBAN)
    - Breakdown by extraction method (regex, llm)
    - Top persons and organizations by mention count
    """
    try:
        from ai.corruption.nlp.entity_store import EntityStore
        store = EntityStore()
        pool = await get_asyncpg_pool()
        stats = await store.get_entity_stats(pool)
        return EntityStatsResponse(**stats)
    except ImportError as e:
        logger.error(f"NER module not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="NER module not available. Ensure ai.corruption.nlp is installed."
        )
    except Exception as e:
        logger.error(f"Error fetching entity stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch entity stats: {str(e)}"
        )


@router.get("/entities/conflicts", response_model=ConflictsResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_conflicts_of_interest(
    limit: int = Query(20, ge=1, le=100, description="Max conflicts to return"),
    min_mentions: int = Query(2, ge=1, le=50, description="Minimum mention count"),
    tender_id: Optional[str] = Query(None, description="Filter to conflicts involving this tender"),
):
    """
    Get potential conflicts of interest from entity analysis.

    A conflict is flagged when the same person name appears in documents
    from both a buyer institution and a winning company in different tenders.

    Query Parameters:
    - limit: Maximum number of conflicts to return (default 20)
    - min_mentions: Minimum total mentions for a conflict (default 2)
    - tender_id: Optional - only show conflicts involving this tender
    """
    try:
        from ai.corruption.nlp.entity_store import EntityStore
        store = EntityStore()
        pool = await get_asyncpg_pool()
        conflicts = await store.find_conflicts(
            pool,
            tender_id=tender_id,
            min_mentions=min_mentions,
            limit=limit,
        )

        conflict_items = []
        for c in conflicts:
            conflict_items.append(ConflictOfInterest(
                person_name=c.get('person_name', ''),
                institution=c.get('institution'),
                company=c.get('company'),
                institution_tenders=c.get('institution_tenders', []),
                company_tenders=c.get('company_tenders', []),
                mention_count=c.get('mention_count', 0),
                avg_confidence=float(c['avg_confidence']) if c.get('avg_confidence') else None,
            ))

        return ConflictsResponse(
            total=len(conflict_items),
            conflicts=conflict_items,
        )
    except ImportError as e:
        logger.error(f"NER module not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="NER module not available."
        )
    except Exception as e:
        logger.error(f"Error fetching conflicts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conflicts of interest: {str(e)}"
        )


@router.get("/entities/network/{entity_name:path}", response_model=EntityNetworkResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_entity_network(
    entity_name: str,
    entity_type: str = Query('PERSON', pattern="^(PERSON|ORG|MONEY|DATE|GPE|TAX_ID|LEGAL_REF|IBAN)$"),
    limit: int = Query(50, ge=1, le=200, description="Max co-occurring entities"),
):
    """
    Get entity co-occurrence network for a specific entity.

    Returns all tenders where this entity appears, plus other entities
    that co-occur in the same tenders (useful for network visualization).

    Path Parameters:
    - entity_name: The entity name to look up

    Query Parameters:
    - entity_type: Entity type (default PERSON)
    - limit: Max co-occurring entities to return (default 50)
    """
    try:
        from ai.corruption.nlp.entity_store import EntityStore
        store = EntityStore()
        pool = await get_asyncpg_pool()
        network = await store.get_entity_network(
            pool,
            entity_name=entity_name,
            entity_type=entity_type,
            limit=limit,
        )
        return EntityNetworkResponse(**network)
    except ImportError as e:
        logger.error(f"NER module not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="NER module not available."
        )
    except Exception as e:
        logger.error(f"Error fetching entity network: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch entity network: {str(e)}"
        )


@router.get("/entities/{tender_id:path}", response_model=TenderEntitiesResponse, dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_tender_entities(
    tender_id: str,
    entity_type: Optional[str] = Query(
        None,
        pattern="^(PERSON|ORG|MONEY|DATE|GPE|TAX_ID|LEGAL_REF|IBAN)$",
        description="Filter by entity type"
    ),
    limit: int = Query(200, ge=1, le=1000, description="Max entities to return"),
):
    """
    Get extracted entities for a specific tender.

    Returns all named entities found in the tender's documents,
    with optional filtering by entity type.

    Path Parameters:
    - tender_id: The tender ID

    Query Parameters:
    - entity_type: Optional filter (PERSON, ORG, MONEY, DATE, GPE, TAX_ID, LEGAL_REF, IBAN)
    - limit: Max entities to return (default 200)
    """
    conn = await get_db_connection()
    try:
        # Verify tender exists
        tender = await conn.fetchval(
            "SELECT tender_id FROM tenders WHERE tender_id = $1",
            tender_id,
        )
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Query entities
        query = """
            SELECT mention_id, entity_text, entity_type, normalized_text,
                   confidence, extraction_method, context,
                   tender_id, doc_id::text
            FROM entity_mentions
            WHERE tender_id = $1
        """
        params = [tender_id]
        param_count = 1

        if entity_type:
            param_count += 1
            query += f" AND entity_type = ${param_count}"
            params.append(entity_type)

        query += f" ORDER BY confidence DESC, entity_type, entity_text LIMIT ${param_count + 1}"
        params.append(limit)

        rows = await conn.fetch(query, *params)

        entities = []
        summary: Dict[str, int] = {}
        for row in rows:
            entities.append(EntityMention(
                mention_id=row['mention_id'],
                entity_text=row['entity_text'],
                entity_type=row['entity_type'],
                normalized_text=row['normalized_text'],
                confidence=float(row['confidence']) if row['confidence'] else 1.0,
                extraction_method=row['extraction_method'] or 'regex',
                context=row['context'],
                tender_id=row['tender_id'],
                doc_id=row['doc_id'],
            ))
            etype = row['entity_type']
            summary[etype] = summary.get(etype, 0) + 1

        return TenderEntitiesResponse(
            tender_id=tender_id,
            total_entities=len(entities),
            entities=entities,
            summary=summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching entities for tender {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tender entities: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# SPECIFICATION SIMILARITY SCHEMAS
# ============================================================================

class SimilarSpec(BaseModel):
    """A tender with a similar specification."""
    similar_tender_id: str
    similarity_score: float
    same_institution: bool = False
    same_winner: bool = False
    similar_title: Optional[str] = None
    similar_institution: Optional[str] = None
    similar_winner: Optional[str] = None


class SimilarSpecsResponse(BaseModel):
    """Response for similar specifications lookup."""
    tender_id: str
    similar_specs: List[SimilarSpec]
    total: int
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class CrossInstitutionClone(BaseModel):
    """A pair of near-identical specs from different institutions."""
    tender_id_1: str
    tender_id_2: str
    institution_1: Optional[str] = None
    institution_2: Optional[str] = None
    winner_1: Optional[str] = None
    winner_2: Optional[str] = None
    similarity: float
    common_winner: bool = False
    title_1: Optional[str] = None
    title_2: Optional[str] = None


class CrossInstitutionClonesResponse(BaseModel):
    """Response for cross-institution clone detection."""
    clones: List[CrossInstitutionClone]
    total: int
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class InstitutionSpecReuse(BaseModel):
    """Specification reuse statistics for an institution."""
    institution: str
    total_specs: int = 0
    unique_specs: int = 0
    reuse_rate: float = 0.0
    top_winner: Optional[str] = None
    top_winner_pct: float = 0.0


class SpecReuseStatsResponse(BaseModel):
    """Response for specification reuse statistics."""
    institutions: List[InstitutionSpecReuse]
    total: int
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class CopyPasteResult(BaseModel):
    """Result of copy-paste analysis between two tenders."""
    tender_id_1: str
    tender_id_2: str
    similarity_ratio: float
    copied_fraction: float
    is_suspicious: bool
    copied_sections: List[Dict[str, Any]]


# ============================================================================
# SPECIFICATION SIMILARITY ENDPOINTS
# ============================================================================

@router.get(
    "/spec-similarity/{tender_id:path}",
    response_model=SimilarSpecsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_similar_specs(
    tender_id: str,
    threshold: float = Query(0.85, ge=0.0, le=1.0, description="Minimum similarity score"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
):
    """
    Find tenders with similar specifications.

    Uses pgvector cosine similarity on document embeddings to find tenders
    whose specification documents are most similar to the given tender.

    Path Parameters:
    - tender_id: The tender ID to find similar specs for

    Query Parameters:
    - threshold: Minimum similarity score (0-1, default 0.85)
    - limit: Maximum number of results (default 10, max 50)

    Returns list of similar tenders with similarity scores and metadata.
    """
    pool = await get_asyncpg_pool()
    try:
        # Verify tender exists
        tender_exists = await pool.fetchval(
            "SELECT 1 FROM tenders WHERE tender_id = $1", tender_id
        )
        if not tender_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Check if tender has embeddings
        has_embeddings = await pool.fetchval(
            "SELECT 1 FROM embeddings WHERE tender_id = $1 LIMIT 1", tender_id
        )
        if not has_embeddings:
            return SimilarSpecsResponse(
                tender_id=tender_id,
                similar_specs=[],
                total=0,
            )

        # Try cached results first
        try:
            cached = await pool.fetch(
                """
                SELECT
                    CASE WHEN sp.tender_id_1 = $1 THEN sp.tender_id_2 ELSE sp.tender_id_1 END as similar_tender_id,
                    sp.similarity_score,
                    sp.same_institution,
                    sp.same_winner,
                    t.title as similar_title,
                    t.procuring_entity as similar_institution,
                    t.winner as similar_winner
                FROM spec_similarity_pairs sp
                JOIN tenders t ON t.tender_id = CASE WHEN sp.tender_id_1 = $1 THEN sp.tender_id_2 ELSE sp.tender_id_1 END
                WHERE (sp.tender_id_1 = $1 OR sp.tender_id_2 = $1)
                  AND sp.similarity_score >= $2
                ORDER BY sp.similarity_score DESC
                LIMIT $3
                """,
                tender_id,
                threshold,
                limit,
            )
            if cached:
                specs = [
                    SimilarSpec(
                        similar_tender_id=r["similar_tender_id"],
                        similarity_score=round(float(r["similarity_score"]), 4),
                        same_institution=r["same_institution"] or False,
                        same_winner=r["same_winner"] or False,
                        similar_title=r["similar_title"],
                        similar_institution=r["similar_institution"],
                        similar_winner=r["similar_winner"],
                    )
                    for r in cached
                ]
                return SimilarSpecsResponse(
                    tender_id=tender_id,
                    similar_specs=specs,
                    total=len(specs),
                )
        except Exception:
            # Table may not exist yet, fall through to live computation
            pass

        # Live computation using pgvector
        from ai.corruption.nlp.spec_similarity import SpecSimilarityAnalyzer
        analyzer = SpecSimilarityAnalyzer()
        results = await analyzer.find_similar_specs(
            pool, tender_id, threshold=threshold, limit=limit
        )

        specs = [SimilarSpec(**r) for r in results]

        return SimilarSpecsResponse(
            tender_id=tender_id,
            similar_specs=specs,
            total=len(specs),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar specs for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar specifications: {str(e)}"
        )


@router.get(
    "/spec-similarity-clones",
    response_model=CrossInstitutionClonesResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_cross_institution_clones(
    min_similarity: float = Query(0.92, ge=0.0, le=1.0, description="Minimum similarity"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
):
    """
    Find near-identical specs from different institutions (strongest rigging signal).

    Cross-institution specification clones are the strongest indicator of
    supplier-authored specifications. When different procuring entities publish
    nearly identical tender specifications, it often means the specifications
    were written by the intended winner.

    Query Parameters:
    - min_similarity: Minimum similarity score (0-1, default 0.92)
    - limit: Maximum number of pairs (default 50, max 200)

    Returns list of specification clone pairs with metadata.
    """
    pool = await get_asyncpg_pool()
    try:
        # Try cached results first
        try:
            cached = await pool.fetch(
                """
                SELECT
                    sp.tender_id_1, sp.tender_id_2, sp.similarity_score,
                    sp.same_winner,
                    t1.procuring_entity as institution_1,
                    t2.procuring_entity as institution_2,
                    t1.winner as winner_1, t2.winner as winner_2,
                    t1.title as title_1, t2.title as title_2
                FROM spec_similarity_pairs sp
                JOIN tenders t1 ON sp.tender_id_1 = t1.tender_id
                JOIN tenders t2 ON sp.tender_id_2 = t2.tender_id
                WHERE sp.cross_institution = TRUE
                  AND sp.similarity_score >= $1
                ORDER BY sp.similarity_score DESC
                LIMIT $2
                """,
                min_similarity,
                limit,
            )
            if cached:
                clones = [
                    CrossInstitutionClone(
                        tender_id_1=r["tender_id_1"],
                        tender_id_2=r["tender_id_2"],
                        institution_1=r["institution_1"],
                        institution_2=r["institution_2"],
                        winner_1=r["winner_1"],
                        winner_2=r["winner_2"],
                        similarity=round(float(r["similarity_score"]), 4),
                        common_winner=r["same_winner"] or False,
                        title_1=r["title_1"],
                        title_2=r["title_2"],
                    )
                    for r in cached
                ]
                return CrossInstitutionClonesResponse(
                    clones=clones,
                    total=len(clones),
                )
        except Exception:
            pass

        # Live computation
        from ai.corruption.nlp.spec_similarity import SpecSimilarityAnalyzer
        analyzer = SpecSimilarityAnalyzer()
        results = await analyzer.find_cross_institution_clones(
            pool, min_similarity=min_similarity, limit=limit
        )

        clones = [CrossInstitutionClone(**r) for r in results]

        return CrossInstitutionClonesResponse(
            clones=clones,
            total=len(clones),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding cross-institution clones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find specification clones: {str(e)}"
        )


@router.get(
    "/spec-reuse-stats",
    response_model=SpecReuseStatsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_spec_reuse_stats(
    limit: int = Query(20, ge=1, le=100, description="Maximum institutions"),
    min_reuse_rate: float = Query(0.0, ge=0.0, le=1.0, description="Minimum reuse rate"),
):
    """
    Get specification reuse statistics by institution.

    High specification reuse rate combined with a dominant winner is a strong
    indicator of procurement rigging. This endpoint returns institutions ranked
    by their specification reuse rate.

    Query Parameters:
    - limit: Maximum number of institutions (default 20, max 100)
    - min_reuse_rate: Minimum reuse rate filter (0-1, default 0)

    Returns list of institutions with reuse metrics.
    """
    pool = await get_asyncpg_pool()
    try:
        # Try cached results
        try:
            rows = await pool.fetch(
                """
                SELECT institution, total_specs, unique_specs,
                       reuse_rate, top_winner, top_winner_pct
                FROM institution_spec_reuse
                WHERE reuse_rate >= $1
                ORDER BY reuse_rate DESC, total_specs DESC
                LIMIT $2
                """,
                min_reuse_rate,
                limit,
            )

            if rows:
                institutions = [
                    InstitutionSpecReuse(
                        institution=r["institution"],
                        total_specs=r["total_specs"],
                        unique_specs=r["unique_specs"],
                        reuse_rate=round(float(r["reuse_rate"]), 4),
                        top_winner=r["top_winner"],
                        top_winner_pct=round(float(r["top_winner_pct"]), 2),
                    )
                    for r in rows
                ]
                return SpecReuseStatsResponse(
                    institutions=institutions,
                    total=len(institutions),
                )
        except Exception:
            pass

        # No cached data available
        return SpecReuseStatsResponse(
            institutions=[],
            total=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching spec reuse stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch specification reuse stats: {str(e)}"
        )


@router.get(
    "/spec-similarity/copy-paste/{tender_id_1:path}",
    response_model=CopyPasteResult,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def analyze_copy_paste(
    tender_id_1: str,
    tender_id_2: str = Query(..., description="Second tender ID to compare"),
):
    """
    Detailed copy-paste analysis between two tender specifications.

    Uses text diffing (SequenceMatcher) to identify copied sections between
    two tender documents. Returns the overall similarity ratio, the fraction
    of text that was copied, and the specific copied sections.

    Path Parameters:
    - tender_id_1: First tender ID

    Query Parameters:
    - tender_id_2: Second tender ID to compare against

    Returns detailed copy-paste analysis with copied sections.
    """
    pool = await get_asyncpg_pool()
    try:
        from ai.corruption.nlp.spec_similarity import SpecSimilarityAnalyzer
        analyzer = SpecSimilarityAnalyzer()

        # Get document texts for both tenders
        text1 = await analyzer.get_tender_document_text(pool, tender_id_1)
        text2 = await analyzer.get_tender_document_text(pool, tender_id_2)

        if not text1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No extracted documents found for tender {tender_id_1}"
            )
        if not text2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No extracted documents found for tender {tender_id_2}"
            )

        # Run copy-paste analysis
        result = await analyzer.detect_copy_paste(text1, text2)

        return CopyPasteResult(
            tender_id_1=tender_id_1,
            tender_id_2=tender_id_2,
            similarity_ratio=result["similarity_ratio"],
            copied_fraction=result["copied_fraction"],
            is_suspicious=result["is_suspicious"],
            copied_sections=result["copied_sections"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in copy-paste analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze copy-paste: {str(e)}"
        )


# ============================================================================
# DOCUMENT ANOMALY DETECTION SCHEMAS
# ============================================================================

class DocAnomaly(BaseModel):
    """Individual document anomaly."""
    anomaly_id: Optional[int] = None
    anomaly_type: str
    severity: str
    description: str
    evidence: Optional[Dict[str, Any]] = None


class DocAnomalyAnalysis(BaseModel):
    """Full document anomaly analysis for a tender."""
    tender_id: str
    total_documents: int
    anomalies: List[DocAnomaly]
    completeness_score: float
    timing_anomaly_score: float
    anomaly_count: int
    overall_risk_contribution: float
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class DocAnomalyStatsResponse(BaseModel):
    """Aggregate document anomaly statistics."""
    total_anomalies: int
    total_tenders_analyzed: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    avg_completeness_score: float
    avg_risk_contribution: float
    tenders_with_critical_anomalies: int
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class DocCompletenessItem(BaseModel):
    """Tender document completeness entry."""
    tender_id: str
    title: Optional[str] = None
    procuring_entity: Optional[str] = None
    total_documents: int
    expected_documents: int
    completeness_score: float
    anomaly_count: int
    timing_anomaly_score: float
    overall_risk_contribution: float
    computed_at: Optional[datetime] = None


class WorstDocCompletenessResponse(BaseModel):
    """Response for worst document completeness tenders."""
    total: int
    tenders: List[DocCompletenessItem]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


# ============================================================================
# DOCUMENT ANOMALY DETECTION ENDPOINTS
# ============================================================================

@router.get(
    "/doc-anomalies/stats",
    response_model=DocAnomalyStatsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_doc_anomaly_stats():
    """
    Get aggregate document anomaly statistics.

    Returns:
    - Total anomalies detected across all tenders
    - Breakdown by anomaly type and severity
    - Average completeness and risk scores
    - Count of tenders with critical anomalies

    Data is sourced from the document_anomalies and tender_doc_completeness tables,
    populated by the batch_doc_anomaly.py cron job.
    """
    conn = await get_db_connection()
    try:
        # Total anomalies and breakdowns
        total_anomalies = await conn.fetchval(
            "SELECT COUNT(*) FROM document_anomalies"
        ) or 0

        total_tenders = await conn.fetchval(
            "SELECT COUNT(*) FROM tender_doc_completeness"
        ) or 0

        # By type
        type_rows = await conn.fetch("""
            SELECT anomaly_type, COUNT(*) as cnt
            FROM document_anomalies
            GROUP BY anomaly_type
            ORDER BY cnt DESC
        """)
        by_type = {r['anomaly_type']: r['cnt'] for r in type_rows}

        # By severity
        sev_rows = await conn.fetch("""
            SELECT severity, COUNT(*) as cnt
            FROM document_anomalies
            GROUP BY severity
            ORDER BY cnt DESC
        """)
        by_severity = {r['severity']: r['cnt'] for r in sev_rows}

        # Average scores from tender_doc_completeness
        avg_row = await conn.fetchrow("""
            SELECT
                COALESCE(ROUND(AVG(completeness_score)::numeric, 3), 0) AS avg_completeness,
                COALESCE(ROUND(AVG(overall_risk_contribution)::numeric, 2), 0) AS avg_risk
            FROM tender_doc_completeness
        """)

        avg_completeness = float(avg_row['avg_completeness']) if avg_row else 0.0
        avg_risk = float(avg_row['avg_risk']) if avg_row else 0.0

        # Tenders with critical anomalies
        critical_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT tender_id)
            FROM document_anomalies
            WHERE severity = 'critical'
        """) or 0

        return DocAnomalyStatsResponse(
            total_anomalies=total_anomalies,
            total_tenders_analyzed=total_tenders,
            by_type=by_type,
            by_severity=by_severity,
            avg_completeness_score=avg_completeness,
            avg_risk_contribution=avg_risk,
            tenders_with_critical_anomalies=critical_count,
        )

    except Exception as e:
        logger.error(f"Error fetching doc anomaly stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document anomaly statistics: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


@router.get(
    "/doc-completeness/worst",
    response_model=WorstDocCompletenessResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_worst_doc_completeness(
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    min_risk: float = Query(0, ge=0, le=100, description="Minimum risk contribution"),
):
    """
    Get tenders with worst document completeness scores.

    Returns tenders ordered by overall risk contribution (descending),
    with the worst document health at the top. Useful for identifying
    tenders that may need document review.

    Query Parameters:
    - limit: Maximum number of results (default 20, max 100)
    - min_risk: Minimum overall risk contribution filter (0-100, default 0)
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch("""
            SELECT
                dc.tender_id,
                t.title,
                t.procuring_entity,
                dc.total_documents,
                dc.expected_documents,
                dc.completeness_score,
                dc.anomaly_count,
                dc.timing_anomaly_score,
                dc.overall_risk_contribution,
                dc.computed_at
            FROM tender_doc_completeness dc
            JOIN tenders t ON dc.tender_id = t.tender_id
            WHERE dc.overall_risk_contribution >= $1
            ORDER BY dc.overall_risk_contribution DESC, dc.completeness_score ASC
            LIMIT $2
        """, min_risk, limit)

        tenders = [
            DocCompletenessItem(
                tender_id=r['tender_id'],
                title=r['title'],
                procuring_entity=r['procuring_entity'],
                total_documents=r['total_documents'] or 0,
                expected_documents=r['expected_documents'] or 0,
                completeness_score=float(r['completeness_score'] or 0),
                anomaly_count=r['anomaly_count'] or 0,
                timing_anomaly_score=float(r['timing_anomaly_score'] or 0),
                overall_risk_contribution=float(r['overall_risk_contribution'] or 0),
                computed_at=r['computed_at'],
            )
            for r in rows
        ]

        return WorstDocCompletenessResponse(
            total=len(tenders),
            tenders=tenders,
        )

    except Exception as e:
        logger.error(f"Error fetching worst doc completeness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document completeness data: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


@router.get(
    "/doc-anomalies/{tender_id:path}",
    response_model=DocAnomalyAnalysis,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_document_anomalies(tender_id: str):
    """
    Get document anomaly analysis for a specific tender.

    Returns all detected document anomalies including missing documents,
    timing anomalies, file size issues, and content problems.

    If the tender has been analyzed by the batch processor, returns cached
    results. Otherwise, runs live analysis (slower but always available).

    Path Parameters:
    - tender_id: The tender ID to analyze
    """
    conn = await get_db_connection()
    try:
        # Verify tender exists
        tender_exists = await conn.fetchval(
            "SELECT 1 FROM tenders WHERE tender_id = $1", tender_id
        )
        if not tender_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found"
            )

        # Try cached results first
        cached_anomalies = None
        cached_completeness = None
        try:
            cached_anomalies = await conn.fetch("""
                SELECT anomaly_id, anomaly_type, severity, description, evidence
                FROM document_anomalies
                WHERE tender_id = $1
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    detected_at DESC
            """, tender_id)

            cached_completeness = await conn.fetchrow("""
                SELECT total_documents, completeness_score, anomaly_count,
                       timing_anomaly_score, overall_risk_contribution
                FROM tender_doc_completeness
                WHERE tender_id = $1
            """, tender_id)
        except Exception:
            # Tables may not exist yet
            pass

        if cached_completeness is not None:
            # Return cached results
            anomalies = []
            for r in (cached_anomalies or []):
                evidence_raw = r['evidence']
                if isinstance(evidence_raw, str):
                    import json
                    evidence = json.loads(evidence_raw) if evidence_raw else {}
                elif isinstance(evidence_raw, dict):
                    evidence = evidence_raw
                else:
                    evidence = {}

                anomalies.append(DocAnomaly(
                    anomaly_id=r['anomaly_id'],
                    anomaly_type=r['anomaly_type'],
                    severity=r['severity'],
                    description=r['description'],
                    evidence=evidence,
                ))

            return DocAnomalyAnalysis(
                tender_id=tender_id,
                total_documents=cached_completeness['total_documents'] or 0,
                anomalies=anomalies,
                completeness_score=float(cached_completeness['completeness_score'] or 0),
                timing_anomaly_score=float(cached_completeness['timing_anomaly_score'] or 0),
                anomaly_count=cached_completeness['anomaly_count'] or 0,
                overall_risk_contribution=float(cached_completeness['overall_risk_contribution'] or 0),
            )

        # No cached results -- run live analysis
        pool = await get_asyncpg_pool()
        try:
            from ai.corruption.nlp.doc_anomaly import DocumentAnomalyDetector
            detector = DocumentAnomalyDetector()
            result = await detector.analyze_tender_documents(pool, tender_id)

            anomalies = [
                DocAnomaly(
                    anomaly_type=a.get('type', 'unknown'),
                    severity=a.get('severity', 'medium'),
                    description=a.get('description', ''),
                    evidence=a.get('evidence'),
                )
                for a in result.get('anomalies', [])
            ]

            return DocAnomalyAnalysis(
                tender_id=tender_id,
                total_documents=result.get('total_documents', 0),
                anomalies=anomalies,
                completeness_score=result.get('completeness_score', 0),
                timing_anomaly_score=result.get('timing_anomaly_score', 0),
                anomaly_count=result.get('anomaly_count', 0),
                overall_risk_contribution=result.get('overall_risk_contribution', 0),
            )
        except ImportError:
            # AI module not available, return empty result
            logger.warning("DocumentAnomalyDetector not available, returning empty result")
            total_docs = await conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE tender_id = $1", tender_id
            ) or 0

            return DocAnomalyAnalysis(
                tender_id=tender_id,
                total_documents=total_docs,
                anomalies=[],
                completeness_score=1.0,
                timing_anomaly_score=0.0,
                anomaly_count=0,
                overall_risk_contribution=0.0,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching doc anomalies for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document anomalies: {str(e)}"
        )
    finally:
        pool = await get_asyncpg_pool()
        await pool.release(conn)


# ============================================================================
# SPECIFICATION RIGGING ANALYSIS SCHEMAS (Phase 2.1)
# ============================================================================

class BrandNameDetail(BaseModel):
    """A detected brand name in a specification."""
    brand: str
    context: str
    confidence: float


class QualificationDetail(BaseModel):
    """An extracted qualification requirement."""
    type: str
    value: str
    is_excessive: bool = False


class SpecAnalysisResult(BaseModel):
    """Specification rigging analysis result for a single tender."""
    tender_id: str
    doc_id: Optional[str] = None
    brand_names_detected: List[BrandNameDetail] = []
    brand_exclusivity_score: float = 0.0
    qualification_requirements: List[QualificationDetail] = []
    qualification_restrictiveness: float = 0.0
    complexity_score: Optional[float] = None
    vocabulary_richness: Optional[float] = None
    rigging_probability: Optional[float] = None
    risk_factors: List[str] = []
    analyzed_at: Optional[datetime] = None
    disclaimer: str = (
        "Оваа анализа е само за информативни цели и не претставува доказ за корупција. "
        "Потребна е дополнителна истрага."
    )


class SpecAnalysisStatsResponse(BaseModel):
    """Aggregate specification analysis statistics."""
    total_analyzed: int = 0
    avg_rigging_probability: float = 0.0
    high_risk_count: int = 0
    total_brands_detected: int = 0
    top_brand_offenders: List[Dict[str, Any]] = []
    excessive_qualifications_count: int = 0
    disclaimer: str = (
        "Оваа анализа е само за информативни цели и не претставува доказ за корупција. "
        "Потребна е дополнителна истрага."
    )


# ============================================================================
# SPECIFICATION RIGGING ANALYSIS ENDPOINTS (Phase 2.1)
# ============================================================================


@router.get(
    "/spec-analysis/stats",
    response_model=SpecAnalysisStatsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_spec_analysis_stats():
    """
    Get aggregate specification analysis statistics.

    Returns total analyzed documents, average rigging score,
    count of high-risk tenders, top brand-name offenders, etc.
    """
    import json
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'specification_analysis'
                )
            """)

            if not table_exists:
                return SpecAnalysisStatsResponse(
                    total_analyzed=0,
                    avg_rigging_probability=0.0,
                    high_risk_count=0,
                    total_brands_detected=0,
                    top_brand_offenders=[],
                    excessive_qualifications_count=0,
                )

            # Aggregate stats
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS total_analyzed,
                    COALESCE(AVG(rigging_probability), 0) AS avg_rigging,
                    COUNT(*) FILTER (WHERE rigging_probability > 0.5) AS high_risk,
                    COALESCE(SUM(jsonb_array_length(brand_names)), 0) AS total_brands,
                    COALESCE(
                        SUM(
                            (SELECT COUNT(*) FROM jsonb_array_elements(qualification_requirements) q
                             WHERE (q.value->>'is_excessive')::boolean = true)
                        ), 0
                    ) AS excessive_quals
                FROM specification_analysis
            """)

            total_analyzed = row['total_analyzed'] if row else 0
            avg_rigging = float(row['avg_rigging']) if row else 0.0
            high_risk = row['high_risk'] if row else 0
            total_brands = row['total_brands'] if row else 0
            excessive_quals = row['excessive_quals'] if row else 0

            # Top brand offenders (tenders with highest brand exclusivity)
            top_offenders_rows = await conn.fetch("""
                SELECT
                    sa.tender_id,
                    sa.brand_exclusivity_score,
                    sa.rigging_probability,
                    sa.brand_names,
                    t.title,
                    t.procuring_entity
                FROM specification_analysis sa
                LEFT JOIN tenders t ON sa.tender_id = t.tender_id
                WHERE sa.brand_exclusivity_score > 0.3
                ORDER BY sa.brand_exclusivity_score DESC
                LIMIT 10
            """)

            top_brand_offenders = []
            for r in top_offenders_rows:
                brands = r['brand_names']
                if isinstance(brands, str):
                    brands = json.loads(brands) if brands else []
                elif brands is None:
                    brands = []

                brand_list = [b.get('brand', '') for b in brands[:5]] if brands else []

                top_brand_offenders.append({
                    'tender_id': r['tender_id'],
                    'brand_exclusivity_score': round(float(r['brand_exclusivity_score']), 3),
                    'rigging_probability': round(float(r['rigging_probability']), 3) if r['rigging_probability'] else 0.0,
                    'brands': brand_list,
                    'title': r['title'],
                    'procuring_entity': r['procuring_entity'],
                })

            return SpecAnalysisStatsResponse(
                total_analyzed=total_analyzed,
                avg_rigging_probability=round(avg_rigging, 3),
                high_risk_count=high_risk,
                total_brands_detected=total_brands,
                top_brand_offenders=top_brand_offenders,
                excessive_qualifications_count=excessive_quals,
            )

    except Exception as e:
        logger.error(f"Error fetching spec analysis stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get spec analysis statistics: {str(e)}"
        )


@router.get(
    "/spec-analysis/{tender_id:path}",
    response_model=SpecAnalysisResult,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_spec_analysis(tender_id: str):
    """
    Get specification rigging analysis for a tender.

    Checks the specification_analysis table for cached results first.
    If no cached results exist, runs on-the-fly analysis on the
    tender's extracted documents.
    """
    import json
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'specification_analysis'
                )
            """)

            cached_row = None
            if table_exists:
                # Check for cached results
                cached_row = await conn.fetchrow("""
                    SELECT
                        sa.tender_id,
                        sa.doc_id::text AS doc_id,
                        sa.brand_names,
                        sa.brand_exclusivity_score,
                        sa.qualification_requirements,
                        sa.qualification_restrictiveness,
                        sa.complexity_score,
                        sa.vocabulary_richness,
                        sa.rigging_probability,
                        sa.risk_factors,
                        sa.analyzed_at
                    FROM specification_analysis sa
                    WHERE sa.tender_id = $1
                    ORDER BY sa.rigging_probability DESC NULLS LAST
                    LIMIT 1
                """, tender_id)

            if cached_row:
                # Parse JSONB fields
                brand_names_raw = cached_row['brand_names']
                if isinstance(brand_names_raw, str):
                    brand_names_raw = json.loads(brand_names_raw) if brand_names_raw else []
                elif brand_names_raw is None:
                    brand_names_raw = []

                qual_raw = cached_row['qualification_requirements']
                if isinstance(qual_raw, str):
                    qual_raw = json.loads(qual_raw) if qual_raw else []
                elif qual_raw is None:
                    qual_raw = []

                risk_factors_raw = cached_row['risk_factors']
                if isinstance(risk_factors_raw, str):
                    risk_factors_raw = json.loads(risk_factors_raw) if risk_factors_raw else []
                elif risk_factors_raw is None:
                    risk_factors_raw = []

                return SpecAnalysisResult(
                    tender_id=cached_row['tender_id'],
                    doc_id=cached_row['doc_id'],
                    brand_names_detected=[
                        BrandNameDetail(**b) for b in brand_names_raw
                    ],
                    brand_exclusivity_score=float(cached_row['brand_exclusivity_score'] or 0),
                    qualification_requirements=[
                        QualificationDetail(**q) for q in qual_raw
                    ],
                    qualification_restrictiveness=float(cached_row['qualification_restrictiveness'] or 0),
                    complexity_score=float(cached_row['complexity_score']) if cached_row['complexity_score'] is not None else None,
                    vocabulary_richness=float(cached_row['vocabulary_richness']) if cached_row['vocabulary_richness'] is not None else None,
                    rigging_probability=float(cached_row['rigging_probability']) if cached_row['rigging_probability'] is not None else None,
                    risk_factors=risk_factors_raw,
                    analyzed_at=cached_row['analyzed_at'],
                )

            # No cached result - attempt on-the-fly analysis
            doc_row = await conn.fetchrow("""
                SELECT doc_id, content_text
                FROM documents
                WHERE tender_id = $1
                  AND extraction_status = 'success'
                  AND content_text IS NOT NULL
                  AND LENGTH(content_text) > 100
                ORDER BY LENGTH(content_text) DESC
                LIMIT 1
            """, tender_id)

            if not doc_row or not doc_row['content_text']:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Не се пронајдени анализирани документи за тендер {tender_id}"
                )

            # Lazy import to avoid loading the analyzer at module level
            import sys as _sys
            import os as _os
            _ai_path = _os.path.join(
                _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                'ai', 'corruption', 'nlp'
            )
            if _ai_path not in _sys.path:
                _sys.path.insert(0, _ai_path)
            _ai_root = _os.path.join(
                _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                'ai'
            )
            if _ai_root not in _sys.path:
                _sys.path.insert(0, _ai_root)

            from spec_analyzer import SpecificationAnalyzer

            analyzer = SpecificationAnalyzer(use_gemini_fallback=False)
            result = await analyzer.analyze_specification(
                content_text=doc_row['content_text'],
                tender_id=tender_id,
            )

            # Cache the result if the table exists
            if table_exists:
                try:
                    await conn.execute("""
                        INSERT INTO specification_analysis (
                            tender_id, doc_id, brand_names, brand_exclusivity_score,
                            qualification_requirements, qualification_restrictiveness,
                            complexity_score, vocabulary_richness, rigging_probability,
                            risk_factors, analyzed_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                        ON CONFLICT (tender_id, doc_id) DO UPDATE SET
                            brand_names = EXCLUDED.brand_names,
                            brand_exclusivity_score = EXCLUDED.brand_exclusivity_score,
                            qualification_requirements = EXCLUDED.qualification_requirements,
                            qualification_restrictiveness = EXCLUDED.qualification_restrictiveness,
                            complexity_score = EXCLUDED.complexity_score,
                            vocabulary_richness = EXCLUDED.vocabulary_richness,
                            rigging_probability = EXCLUDED.rigging_probability,
                            risk_factors = EXCLUDED.risk_factors,
                            analyzed_at = NOW()
                    """,
                        tender_id,
                        doc_row['doc_id'],
                        json.dumps(result['brand_names_detected']),
                        result['brand_exclusivity_score'],
                        json.dumps(result['qualification_requirements']),
                        result['qualification_restrictiveness'],
                        result['complexity_score'],
                        result['vocabulary_richness'],
                        result['rigging_probability'],
                        json.dumps(result['risk_factors']),
                    )
                except Exception as cache_err:
                    logger.warning(f"Failed to cache spec analysis for {tender_id}: {cache_err}")

            return SpecAnalysisResult(
                tender_id=tender_id,
                doc_id=str(doc_row['doc_id']),
                brand_names_detected=[
                    BrandNameDetail(**b) for b in result['brand_names_detected']
                ],
                brand_exclusivity_score=result['brand_exclusivity_score'],
                qualification_requirements=[
                    QualificationDetail(**q) for q in result['qualification_requirements']
                ],
                qualification_restrictiveness=result['qualification_restrictiveness'],
                complexity_score=result['complexity_score'],
                vocabulary_richness=result['vocabulary_richness'],
                rigging_probability=result['rigging_probability'],
                risk_factors=result['risk_factors'],
                analyzed_at=datetime.utcnow(),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in spec analysis for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze specification: {str(e)}"
        )
