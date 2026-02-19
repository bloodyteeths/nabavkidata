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
import json
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
                evidence=json.loads(row['evidence']) if isinstance(row['evidence'], str) else (row['evidence'] or None),
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


# ============================================================================
# CAUSAL INFERENCE ENDPOINTS (Phase 3.2)
# ============================================================================

class CausalEffectDetail(BaseModel):
    """Single causal effect estimate for a procurement design choice"""
    treatment: str
    treatment_description: str
    ate: float  # Average Treatment Effect
    ci_lower: float
    ci_upper: float
    p_value: float
    n_treated: int
    n_control: int
    n_matched: int
    interpretation: str
    recommendation: str

    class Config:
        from_attributes = True


class CausalEffectsResponse(BaseModel):
    """Response containing all estimated causal effects"""
    effects: List[CausalEffectDetail]
    total: int
    methodology: str = (
        "Propensity score matching with bootstrap confidence intervals. "
        "Controls for confounders: estimated_value_mkd, institution_total_tenders, "
        "num_bidders, deadline_days, has_lots."
    )
    disclaimer: str = (
        "Каузалните проценки се базирани на набљудувачки податоци и "
        "пропенсити скор мечинг. Не претставуваат доказ за корупција."
    )


class PolicyRecommendationDetail(BaseModel):
    """Single policy recommendation"""
    recommendation: str
    estimated_impact: float  # Percentage points change
    confidence: str  # 'high', 'medium', 'low'
    evidence: Optional[Dict[str, Any]] = None
    treatment_name: Optional[str] = None
    institution: Optional[str] = None

    class Config:
        from_attributes = True


class PolicyRecommendationsResponse(BaseModel):
    """Response containing policy recommendations"""
    recommendations: List[PolicyRecommendationDetail]
    total: int
    institution: Optional[str] = None
    disclaimer: str = (
        "Препораките се базирани на статистичка анализа и не претставуваат "
        "правен совет. Потребна е дополнителна евалуација."
    )


class CausalFeatureComparison(BaseModel):
    """Comparison of a single feature's SHAP vs causal importance"""
    name: str
    treatment_name: Optional[str] = None
    shap_importance: float
    causal_effect: float
    p_value: float
    is_confounder: bool
    explanation: str


class CausalReportResponse(BaseModel):
    """Causal vs correlational feature importance report"""
    features: List[CausalFeatureComparison]
    n_shap_samples: int
    n_treatments_analyzed: int
    methodology_note: str
    disclaimer: str = (
        "Оваа анализа е само за информативни цели. Разликите меѓу "
        "корелациони и каузални ефекти може да варираат со нови податоци."
    )


@router.get(
    "/causal/effects",
    response_model=CausalEffectsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_causal_effects():
    """
    Get estimated causal effects of procurement design choices on corruption probability.

    Returns ATE (Average Treatment Effect) for each treatment:
    - short_deadline: Deadline < 15 days
    - single_bidder: Only one bidder submitted
    - high_value: Estimated value > 10M MKD
    - weekend_publication: Published on weekend

    Effects are pre-computed by the batch_causal.py cron job and cached in
    the causal_estimates table. If no cached results exist, returns empty list.
    """
    import json as _json
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'causal_estimates'
                )
            """)

            if not table_exists:
                return CausalEffectsResponse(effects=[], total=0)

            rows = await conn.fetch("""
                SELECT
                    treatment_name, treatment_description,
                    ate, ci_lower, ci_upper, p_value,
                    n_treated, n_control, n_matched,
                    interpretation, recommendation
                FROM causal_estimates
                ORDER BY ABS(ate) DESC
            """)

            effects = []
            for r in rows:
                effects.append(CausalEffectDetail(
                    treatment=r['treatment_name'],
                    treatment_description=r['treatment_description'] or '',
                    ate=float(r['ate']),
                    ci_lower=float(r['ci_lower'] or 0),
                    ci_upper=float(r['ci_upper'] or 0),
                    p_value=float(r['p_value'] or 1),
                    n_treated=r['n_treated'] or 0,
                    n_control=r['n_control'] or 0,
                    n_matched=r['n_matched'] or 0,
                    interpretation=r['interpretation'] or '',
                    recommendation=r['recommendation'] or '',
                ))

            return CausalEffectsResponse(
                effects=effects,
                total=len(effects),
            )

    except Exception as e:
        logger.error(f"Error fetching causal effects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get causal effects: {str(e)}"
        )


@router.get(
    "/causal/recommendations",
    response_model=PolicyRecommendationsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_policy_recommendations(
    institution: Optional[str] = Query(
        None,
        description="Institution name to filter recommendations. If not provided, returns global recommendations."
    ),
):
    """
    Get actionable policy recommendations based on causal analysis.

    Recommendations are derived from statistically significant causal effects
    and include estimated impact (percentage point change in corruption probability)
    and confidence level.

    Optionally filter by institution for scoped recommendations.
    """
    import json as _json
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'policy_recommendations'
                )
            """)

            if not table_exists:
                return PolicyRecommendationsResponse(
                    recommendations=[], total=0, institution=institution
                )

            # Build query
            if institution:
                rows = await conn.fetch("""
                    SELECT
                        recommendation, estimated_impact, confidence,
                        evidence, treatment_name, institution
                    FROM policy_recommendations
                    WHERE institution = $1
                    ORDER BY
                        CASE confidence
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            WHEN 'low' THEN 3
                            ELSE 4
                        END,
                        ABS(estimated_impact) DESC
                """, institution)
            else:
                rows = await conn.fetch("""
                    SELECT
                        recommendation, estimated_impact, confidence,
                        evidence, treatment_name, institution
                    FROM policy_recommendations
                    WHERE institution IS NULL
                    ORDER BY
                        CASE confidence
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            WHEN 'low' THEN 3
                            ELSE 4
                        END,
                        ABS(estimated_impact) DESC
                """)

            recommendations = []
            for r in rows:
                evidence = r['evidence']
                if isinstance(evidence, str):
                    evidence = _json.loads(evidence) if evidence else {}
                elif evidence is None:
                    evidence = {}

                recommendations.append(PolicyRecommendationDetail(
                    recommendation=r['recommendation'],
                    estimated_impact=float(r['estimated_impact'] or 0),
                    confidence=r['confidence'] or 'low',
                    evidence=evidence,
                    treatment_name=r['treatment_name'],
                    institution=r['institution'],
                ))

            return PolicyRecommendationsResponse(
                recommendations=recommendations,
                total=len(recommendations),
                institution=institution,
            )

    except Exception as e:
        logger.error(f"Error fetching policy recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get policy recommendations: {str(e)}"
        )


@router.get(
    "/causal/report",
    response_model=CausalReportResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_causal_report():
    """
    Get causal vs correlational feature importance comparison report.

    Compares SHAP-based (correlational) feature importance with propensity
    score matching-based (causal) importance. Identifies confounders
    (features that correlate with corruption but do not cause it) vs
    true causal factors (features that, when changed, actually affect
    corruption probability).
    """
    import json as _json
    pool = await get_asyncpg_pool()

    try:
        # Read causal estimates
        causal_data = {}
        async with pool.acquire() as conn:
            ce_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'causal_estimates'
                )
            """)

            if ce_exists:
                rows = await conn.fetch("""
                    SELECT treatment_name, ate, p_value, n_matched
                    FROM causal_estimates
                """)
                for r in rows:
                    causal_data[r['treatment_name']] = {
                        'ate': float(r['ate']),
                        'p_value': float(r['p_value'] or 1),
                        'n_matched': int(r['n_matched'] or 0),
                    }

        # Read SHAP importances
        shap_importances = {}
        async with pool.acquire() as conn:
            shap_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'ml_shap_cache'
                )
            """)

            if shap_exists:
                rows = await conn.fetch("""
                    SELECT shap_values
                    FROM ml_shap_cache
                    ORDER BY computed_at DESC
                    LIMIT 500
                """)

                if rows:
                    all_shap = {}
                    count = 0
                    for r in rows:
                        sv = r['shap_values']
                        if isinstance(sv, str):
                            sv = _json.loads(sv) if sv else {}
                        elif sv is None:
                            sv = {}
                        for feat, val in sv.items():
                            if feat not in all_shap:
                                all_shap[feat] = 0.0
                            all_shap[feat] += abs(float(val))
                        count += 1

                    if count > 0:
                        shap_importances = {
                            k: round(v / count, 6) for k, v in all_shap.items()
                        }

        # Map treatments to features
        treatment_to_feature = {
            'short_deadline': 'deadline_days',
            'single_bidder': 'num_bidders',
            'high_value': 'estimated_value_mkd',
            'weekend_publication': 'pub_weekend',
        }

        # Build comparison
        import numpy as _np
        features_report = []

        shap_values_list = list(shap_importances.values()) if shap_importances else [0]
        median_shap = float(_np.percentile(shap_values_list, 50)) if shap_values_list else 0.0

        for treatment_name, feature_name in treatment_to_feature.items():
            causal = causal_data.get(treatment_name, {})
            shap_imp = shap_importances.get(feature_name, 0.0)
            ate = causal.get('ate', 0.0)
            p_value = causal.get('p_value', 1.0)

            significant_causal = p_value < 0.05
            high_shap = shap_imp > median_shap if shap_importances else False

            if high_shap and not significant_causal:
                is_confounder = True
                explanation = (
                    f"'{feature_name}' has high SHAP importance ({shap_imp:.4f}) "
                    f"but NO significant causal effect (ATE={ate:.4f}, p={p_value:.3f}). "
                    f"This suggests it is a CONFOUNDER."
                )
            elif significant_causal and high_shap:
                is_confounder = False
                explanation = (
                    f"'{feature_name}' has both high SHAP importance ({shap_imp:.4f}) "
                    f"AND significant causal effect (ATE={ate:.4f}, p={p_value:.3f}). "
                    f"This is likely a TRUE CAUSE."
                )
            elif significant_causal and not high_shap:
                is_confounder = False
                explanation = (
                    f"'{feature_name}' has significant causal effect (ATE={ate:.4f}, "
                    f"p={p_value:.3f}) but low SHAP importance ({shap_imp:.4f}). "
                    f"Causal effect may be masked by confounders in SHAP."
                )
            else:
                is_confounder = False
                explanation = (
                    f"'{feature_name}' shows neither strong SHAP importance "
                    f"({shap_imp:.4f}) nor significant causal effect "
                    f"(ATE={ate:.4f}, p={p_value:.3f})."
                )

            features_report.append(CausalFeatureComparison(
                name=feature_name,
                treatment_name=treatment_name,
                shap_importance=round(shap_imp, 6),
                causal_effect=round(ate, 6),
                p_value=round(p_value, 4),
                is_confounder=is_confounder,
                explanation=explanation,
            ))

        features_report.sort(key=lambda x: abs(x.causal_effect), reverse=True)

        return CausalReportResponse(
            features=features_report,
            n_shap_samples=len(shap_importances),
            n_treatments_analyzed=len(causal_data),
            methodology_note=(
                "SHAP values measure correlational feature importance: how much each "
                "feature contributes to the model's prediction. Causal effects (ATE) "
                "measure the actual impact of changing a feature on the outcome, "
                "controlling for confounders via propensity score matching. "
                "Features with high SHAP but no causal effect are likely confounders. "
                "Features with significant causal effects are actionable targets for "
                "policy intervention."
            ),
        )

    except Exception as e:
        logger.error(f"Error generating causal report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate causal report: {str(e)}"
        )


# ============================================================================
# AutoML & Model Registry Endpoints (Phase 3.4)
# ============================================================================

@router.get("/ml/models")
async def get_model_registry():
    """
    Get registered model versions and their performance metrics.

    Returns all registered models with their active version,
    total version count, and best AUC-ROC score.
    """
    try:
        from ai.corruption.ml_models.model_registry import ModelRegistry
        pool = await get_asyncpg_pool()
        registry = ModelRegistry()
        models = await registry.list_all_models(pool)
        return {
            "models": models,
            "total": len(models),
        }
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Model registry not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching model registry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch model registry: {str(e)}"
        )


@router.get("/ml/models/{model_name}/history")
async def get_model_history(model_name: str, limit: int = Query(10, ge=1, le=100)):
    """
    Get training history for a specific model.

    Path Parameters:
    - model_name: 'xgboost' or 'random_forest'

    Query Parameters:
    - limit: max versions to return (default 10, max 100)
    """
    try:
        from ai.corruption.ml_models.model_registry import ModelRegistry
        pool = await get_asyncpg_pool()
        registry = ModelRegistry()
        history = await registry.get_model_history(pool, model_name, limit=limit)
        return {
            "model_name": model_name,
            "versions": history,
            "total": len(history),
        }
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Model registry not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching model history for {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch model history: {str(e)}"
        )


@router.get("/ml/models/{model_name}/active")
async def get_active_model(model_name: str):
    """
    Get the currently active model version and its full metadata.

    Path Parameters:
    - model_name: 'xgboost' or 'random_forest'
    """
    try:
        from ai.corruption.ml_models.model_registry import ModelRegistry
        pool = await get_asyncpg_pool()
        registry = ModelRegistry()
        active = await registry.get_active_model(pool, model_name)
        if not active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active model found for '{model_name}'"
            )
        return active
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Model registry not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching active model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch active model: {str(e)}"
        )


@router.get("/ml/models/{model_name}/compare")
async def compare_model_versions(
    model_name: str,
    v1: str = Query(..., description="First version ID"),
    v2: str = Query(..., description="Second version ID"),
):
    """
    Compare metrics between two model versions side-by-side.

    Query Parameters:
    - v1: first version_id
    - v2: second version_id
    """
    try:
        from ai.corruption.ml_models.model_registry import ModelRegistry
        pool = await get_asyncpg_pool()
        registry = ModelRegistry()
        comparison = await registry.compare_versions(pool, model_name, v1, v2)
        return comparison
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Model registry not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error comparing model versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare model versions: {str(e)}"
        )


@router.post("/ml/models/{model_name}/rollback", dependencies=[Depends(require_admin)])
async def rollback_model(
    model_name: str,
    version_id: Optional[str] = Query(None, description="Target version to rollback to (default: previous)")
):
    """
    Admin: Rollback to a previous model version.

    If version_id is provided, activates that specific version.
    Otherwise, activates the most recent non-active version.
    Also restores the archived joblib file if available.

    Path Parameters:
    - model_name: 'xgboost' or 'random_forest'

    Query Parameters:
    - version_id: specific version to restore (optional)
    """
    try:
        from ai.corruption.ml_models.model_registry import ModelRegistry
        pool = await get_asyncpg_pool()
        registry = ModelRegistry()
        result = await registry.rollback(pool, model_name, version_id=version_id)
        return {
            "message": f"Rolled back {model_name} to {result['rolled_back_to']}",
            **result,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Model registry not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error rolling back model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback model: {str(e)}"
        )


@router.get("/ml/drift")
async def get_data_drift_status():
    """
    Get latest data drift analysis.

    Returns the most recent drift check from the data_drift_log table,
    including per-feature PSI values and overall drift assessment.
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT drift_id, feature_psi, overall_drift, drift_level,
                       should_retrain, checked_at
                FROM data_drift_log
                ORDER BY checked_at DESC
                LIMIT 1
            """)

        if not row:
            return {
                "message": "No drift analysis available. Run a drift check first.",
                "drift_level": "unknown",
                "should_retrain": False,
            }

        import json as _json
        feature_psi = row['feature_psi']
        if isinstance(feature_psi, str):
            feature_psi = _json.loads(feature_psi)

        # Sort features by PSI descending
        sorted_features = sorted(
            feature_psi.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "drift_id": row['drift_id'],
            "overall_drift": float(row['overall_drift']) if row['overall_drift'] else 0.0,
            "drift_level": row['drift_level'],
            "should_retrain": row['should_retrain'],
            "checked_at": row['checked_at'].isoformat() if row['checked_at'] else None,
            "top_drifted_features": [
                {"feature": name, "psi": round(psi, 4)}
                for name, psi in sorted_features[:20]
            ],
            "total_features_checked": len(feature_psi),
        }
    except Exception as e:
        logger.error(f"Error fetching drift status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch drift status: {str(e)}"
        )


@router.post("/ml/drift/check", dependencies=[Depends(require_admin)])
async def run_drift_check(
    background_tasks: BackgroundTasks,
    window_days: int = Query(30, ge=7, le=365, description="Lookback window in days"),
):
    """
    Admin: Trigger a fresh data drift analysis.

    Runs asynchronously in the background. Check results with GET /ml/drift.

    Query Parameters:
    - window_days: comparison window (default 30)
    """
    async def _run_drift(window: int):
        try:
            from ai.corruption.ml_models.automl import AutoMLPipeline
            pool = await get_asyncpg_pool()
            pipeline = AutoMLPipeline()
            await pipeline.check_data_drift(pool, window_days=window)
        except Exception as exc:
            logger.error(f"Background drift check failed: {exc}")

    background_tasks.add_task(_run_drift, window_days)
    return {
        "message": f"Drift check started (window={window_days} days). Check GET /api/corruption/ml/drift for results.",
        "status": "running",
    }


@router.post("/ml/optimize", dependencies=[Depends(require_admin)])
async def trigger_optimization(
    background_tasks: BackgroundTasks,
    model_type: str = Query("xgboost", description="Model type to optimize"),
    n_trials: int = Query(30, ge=5, le=100, description="Number of Optuna trials"),
):
    """
    Admin: Trigger Bayesian hyperparameter optimization with Optuna.

    Runs asynchronously in the background. Results are stored in the
    optimization_runs table and can be queried via GET /ml/optimization-history.

    Query Parameters:
    - model_type: 'xgboost' or 'random_forest' (default 'xgboost')
    - n_trials: number of Optuna trials (default 30, max 100)
    """
    if model_type not in ('xgboost', 'random_forest'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model_type must be 'xgboost' or 'random_forest'"
        )

    async def _run_optimization(mtype: str, trials: int):
        try:
            from ai.corruption.ml_models.automl import AutoMLPipeline
            pool = await get_asyncpg_pool()
            pipeline = AutoMLPipeline()
            await pipeline.optimize(pool, model_type=mtype, n_trials=trials, triggered_by='manual')
        except Exception as exc:
            logger.error(f"Background optimization failed: {exc}")

    background_tasks.add_task(_run_optimization, model_type, n_trials)
    return {
        "message": f"Optimization started for {model_type} ({n_trials} trials). "
                   f"Check GET /api/corruption/ml/optimization-history for results.",
        "status": "running",
        "model_type": model_type,
        "n_trials": n_trials,
    }


@router.get("/ml/optimization-history")
async def get_optimization_history(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Get history of Optuna optimization runs.

    Query Parameters:
    - model_name: filter by model type (optional)
    - limit: max runs to return (default 10)
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            if model_name:
                rows = await conn.fetch("""
                    SELECT run_id, model_name, n_trials, best_params, best_score,
                           duration_seconds, triggered_by, completed_at
                    FROM optimization_runs
                    WHERE model_name = $1
                    ORDER BY completed_at DESC
                    LIMIT $2
                """, model_name, limit)
            else:
                rows = await conn.fetch("""
                    SELECT run_id, model_name, n_trials, best_params, best_score,
                           duration_seconds, triggered_by, completed_at
                    FROM optimization_runs
                    ORDER BY completed_at DESC
                    LIMIT $1
                """, limit)

        import json as _json
        results = []
        for row in rows:
            best_params = row['best_params']
            if isinstance(best_params, str):
                best_params = _json.loads(best_params)
            results.append({
                'run_id': row['run_id'],
                'model_name': row['model_name'],
                'n_trials': row['n_trials'],
                'best_params': best_params,
                'best_score': float(row['best_score']) if row['best_score'] else None,
                'duration_seconds': float(row['duration_seconds']) if row['duration_seconds'] else None,
                'triggered_by': row['triggered_by'],
                'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
            })

        return {
            "runs": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"Error fetching optimization history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch optimization history: {str(e)}"
        )


@router.get("/ml/retrain-status")
async def get_retrain_recommendation():
    """
    Check if model retraining is recommended.

    Evaluates three criteria:
    1. Data drift (PSI > 0.1 on key features)
    2. New labeled data (50+ new reviews since last training)
    3. Time since last training (> 30 days)

    Returns recommendation with urgency level and reasons.
    """
    try:
        from ai.corruption.ml_models.automl import AutoMLPipeline
        pool = await get_asyncpg_pool()
        pipeline = AutoMLPipeline()
        result = await pipeline.should_retrain(pool)
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"AutoML pipeline not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error checking retrain status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check retrain status: {str(e)}"
        )


# ============================================================================
# ADVERSARIAL ROBUSTNESS ENDPOINTS (Phase 3.3)
# ============================================================================


@router.get(
    "/robustness/fragile",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_fragile_predictions(
    limit: int = Query(20, ge=1, le=100),
    include_boundary: bool = Query(True, description="Include boundary cases"),
):
    """
    Get predictions most vulnerable to adversarial manipulation.

    Returns tenders whose ML predictions are fragile -- meaning small
    perturbations to input features could flip the classification.
    These deserve manual review.
    """
    import json as _json

    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if the adversarial_analysis table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'adversarial_analysis'
                )
            """)

            if not table_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Adversarial analysis table not found. Run migration 038_adversarial.sql first."
                )

            where_clause = ""
            if not include_boundary:
                where_clause = "WHERE is_boundary_case = FALSE"

            rows = await conn.fetch(f"""
                SELECT
                    aa.tender_id,
                    aa.model_name,
                    aa.robustness_score,
                    aa.robustness_level,
                    aa.robustness_margin,
                    aa.vulnerable_features,
                    aa.is_boundary_case,
                    aa.prediction,
                    aa.adversarial_resistance,
                    aa.recommendations,
                    aa.analyzed_at,
                    t.title,
                    t.procuring_entity,
                    t.winner,
                    t.estimated_value_mkd,
                    t.status
                FROM adversarial_analysis aa
                LEFT JOIN tenders t ON aa.tender_id = t.tender_id
                {where_clause}
                ORDER BY aa.robustness_score ASC
                LIMIT $1
            """, limit)

            results = []
            for row in rows:
                vulnerable_features = row['vulnerable_features']
                if isinstance(vulnerable_features, str):
                    vulnerable_features = _json.loads(vulnerable_features) if vulnerable_features else []

                recommendations = row['recommendations']
                if isinstance(recommendations, str):
                    recommendations = _json.loads(recommendations) if recommendations else []

                results.append({
                    'tender_id': row['tender_id'],
                    'title': row['title'],
                    'procuring_entity': row['procuring_entity'],
                    'winner': row['winner'],
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'status': row['status'],
                    'model_name': row['model_name'],
                    'robustness_score': row['robustness_score'],
                    'robustness_level': row['robustness_level'],
                    'robustness_margin': row['robustness_margin'],
                    'vulnerable_features': vulnerable_features,
                    'is_boundary_case': row['is_boundary_case'],
                    'prediction': row['prediction'],
                    'adversarial_resistance': row['adversarial_resistance'],
                    'recommendations': recommendations,
                    'analyzed_at': row['analyzed_at'].isoformat() if row['analyzed_at'] else None,
                })

            return {
                'total': len(results),
                'fragile_predictions': results,
                'disclaimer': (
                    "Fragile predictions are those where small changes in tender data "
                    "could flip the ML classification. These tenders warrant manual review."
                ),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching fragile predictions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch fragile predictions: {str(e)}"
        )


@router.get(
    "/robustness/{tender_id:path}",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_prediction_robustness(tender_id: str):
    """
    Get adversarial robustness analysis for a tender's risk prediction.

    If a cached analysis exists in the database, returns that.
    Otherwise, runs on-the-fly analysis using the ML model and
    FeatureExtractor.
    """
    import json as _json
    import sys as _sys
    from pathlib import Path as _Path

    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if the adversarial_analysis table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'adversarial_analysis'
                )
            """)

            # Try cached result first
            cached = None
            if table_exists:
                cached = await conn.fetchrow("""
                    SELECT * FROM adversarial_analysis
                    WHERE tender_id = $1
                """, tender_id)

            if cached:
                vulnerable_features = cached['vulnerable_features']
                if isinstance(vulnerable_features, str):
                    vulnerable_features = _json.loads(vulnerable_features) if vulnerable_features else []

                recommendations = cached['recommendations']
                if isinstance(recommendations, str):
                    recommendations = _json.loads(recommendations) if recommendations else []

                return {
                    'tender_id': cached['tender_id'],
                    'model_name': cached['model_name'],
                    'robustness_score': cached['robustness_score'],
                    'robustness_level': cached['robustness_level'],
                    'robustness_margin': cached['robustness_margin'],
                    'vulnerable_features': vulnerable_features,
                    'is_boundary_case': cached['is_boundary_case'],
                    'prediction': cached['prediction'],
                    'adversarial_resistance': cached['adversarial_resistance'],
                    'recommendations': recommendations,
                    'analyzed_at': cached['analyzed_at'].isoformat() if cached['analyzed_at'] else None,
                    'source': 'cached',
                }

        # No cached result -- run on-the-fly analysis
        # Verify tender exists
        async with pool.acquire() as conn:
            tender_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM tenders WHERE tender_id = $1)", tender_id
            )
            if not tender_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tender {tender_id} not found"
                )

        # Import and run adversarial analysis
        try:
            _sys.path.insert(0, str(_Path(__file__).parent.parent.parent / "ai" / "corruption"))
            from features.feature_extractor import FeatureExtractor
            from ai.corruption.ml_models.adversarial import AdversarialAnalyzer
        except ImportError as ie:
            logger.error(f"Failed to import adversarial modules: {ie}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Adversarial analysis module not available. Check server configuration."
            )

        # Extract features
        extractor = FeatureExtractor(pool)
        try:
            fv = await extractor.extract_features(tender_id, include_metadata=False)
        except Exception as fe:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not extract features for tender {tender_id}: {str(fe)}"
            )

        # Run robustness analysis
        analyzer = AdversarialAnalyzer()
        try:
            analyzer.load_model('xgboost')
        except FileNotFoundError:
            try:
                analyzer.load_model('random_forest')
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No trained ML model found. Train models first."
                )

        result = analyzer.assess_prediction_robustness(fv.feature_array)

        # Cache the result if table exists
        if table_exists:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO adversarial_analysis (
                            tender_id, model_name, robustness_score, robustness_level,
                            robustness_margin, vulnerable_features, is_boundary_case,
                            prediction, adversarial_resistance, recommendations, analyzed_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                        ON CONFLICT (tender_id) DO UPDATE SET
                            model_name = EXCLUDED.model_name,
                            robustness_score = EXCLUDED.robustness_score,
                            robustness_level = EXCLUDED.robustness_level,
                            robustness_margin = EXCLUDED.robustness_margin,
                            vulnerable_features = EXCLUDED.vulnerable_features,
                            is_boundary_case = EXCLUDED.is_boundary_case,
                            prediction = EXCLUDED.prediction,
                            adversarial_resistance = EXCLUDED.adversarial_resistance,
                            recommendations = EXCLUDED.recommendations,
                            analyzed_at = NOW()
                    """,
                        tender_id,
                        result['model_name'],
                        result['robustness_score'],
                        result['robustness_level'],
                        result['robustness_margin'],
                        _json.dumps(result['vulnerable_features']),
                        result['is_boundary_case'],
                        result['prediction'],
                        result['adversarial_resistance'],
                        _json.dumps(result['recommendations']),
                    )
            except Exception as cache_err:
                logger.warning(f"Failed to cache robustness analysis for {tender_id}: {cache_err}")

        return {
            'tender_id': tender_id,
            'model_name': result['model_name'],
            'robustness_score': result['robustness_score'],
            'robustness_level': result['robustness_level'],
            'robustness_margin': result['robustness_margin'],
            'vulnerable_features': result['vulnerable_features'],
            'is_boundary_case': result['is_boundary_case'],
            'prediction': result['prediction'],
            'adversarial_resistance': result['adversarial_resistance'],
            'recommendations': result['recommendations'],
            'gameable_vulnerabilities': result.get('gameable_vulnerabilities', []),
            'total_flippable_features': result.get('total_flippable_features', 0),
            'easiest_flip_feature': result.get('easiest_flip_feature'),
            'analyzed_at': datetime.utcnow().isoformat(),
            'source': 'computed',
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in robustness analysis for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze prediction robustness: {str(e)}"
        )


# ============================================================================
# TEMPORAL RISK ANALYSIS ENDPOINTS (Phase 3.1)
# ============================================================================

class TemporalProfileResponse(BaseModel):
    """Temporal risk profile for an entity."""
    entity: str
    entity_type: str
    total_tenders: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    temporal_features: Dict[str, Any]
    change_points: List[Dict[str, Any]]
    trajectory: Dict[str, Any]
    summary_stats: Dict[str, Any]
    computed_at: Optional[str] = None
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class EscalatingEntityItem(BaseModel):
    """Entity with escalating risk trajectory."""
    entity_name: str
    entity_type: str
    trajectory: str
    trajectory_confidence: Optional[float] = None
    trajectory_description: Optional[str] = None
    risk_trend_slope: Optional[float] = None
    risk_volatility: Optional[float] = None
    tender_count: int = 0
    last_change_point_date: Optional[str] = None
    summary_stats: Optional[Dict[str, Any]] = None


class EscalatingEntitiesResponse(BaseModel):
    """List of entities with escalating risk."""
    total: int
    entities: List[EscalatingEntityItem]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


class ChangePointItem(BaseModel):
    """Entity with a recent behavioral change point."""
    entity_name: str
    entity_type: str
    last_change_point_date: Optional[str] = None
    trajectory: Optional[str] = None
    trajectory_confidence: Optional[float] = None
    risk_trend_slope: Optional[float] = None
    change_points: Optional[List[Dict[str, Any]]] = None
    tender_count: int = 0


class RecentChangePointsResponse(BaseModel):
    """Entities with recent behavioral change points."""
    total: int
    days_lookback: int
    entities: List[ChangePointItem]
    disclaimer: str = "Оваа анализа е само за информативни цели и не претставува доказ за корупција. Потребна е дополнителна истрага."


@router.get(
    "/temporal/escalating",
    response_model=EscalatingEntitiesResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_escalating_entities(
    entity_type: str = Query("institution", description="Entity type: institution or company"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Get entities with escalating risk trajectories.

    Returns institutions or companies whose risk is trending upward,
    ordered by steepest risk trend slope. Requires pre-computed
    temporal profiles (run batch_temporal.py first).
    """
    import json as _json

    pool = await get_asyncpg_pool()
    try:
        async with pool.acquire() as conn:
            # Check if the table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'entity_temporal_profiles'
                )
            """)
            if not table_exists:
                return EscalatingEntitiesResponse(total=0, entities=[])

            rows = await conn.fetch(
                """
                SELECT
                    entity_name, entity_type, trajectory,
                    trajectory_confidence, trajectory_description,
                    risk_trend_slope, risk_volatility,
                    tender_count,
                    last_change_point_date,
                    summary_stats
                FROM entity_temporal_profiles
                WHERE entity_type = $1
                  AND trajectory IN ('escalating', 'new_pattern', 'stable_high')
                ORDER BY risk_trend_slope DESC NULLS LAST
                LIMIT $2
                """,
                entity_type,
                limit,
            )

            entities = []
            for row in rows:
                stats_raw = row["summary_stats"]
                if isinstance(stats_raw, str):
                    stats = _json.loads(stats_raw) if stats_raw else {}
                elif isinstance(stats_raw, dict):
                    stats = stats_raw
                else:
                    stats = {}

                entities.append(
                    EscalatingEntityItem(
                        entity_name=row["entity_name"],
                        entity_type=row["entity_type"],
                        trajectory=row["trajectory"] or "unknown",
                        trajectory_confidence=row["trajectory_confidence"],
                        trajectory_description=row["trajectory_description"],
                        risk_trend_slope=row["risk_trend_slope"],
                        risk_volatility=row["risk_volatility"],
                        tender_count=row["tender_count"] or 0,
                        last_change_point_date=(
                            row["last_change_point_date"].isoformat()
                            if row["last_change_point_date"]
                            else None
                        ),
                        summary_stats=stats,
                    )
                )

            return EscalatingEntitiesResponse(
                total=len(entities),
                entities=entities,
            )

    except Exception as e:
        logger.error(f"Error fetching escalating entities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch escalating entities: {str(e)}",
        )


@router.get(
    "/temporal/change-points",
    response_model=RecentChangePointsResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_recent_change_points(
    days: int = Query(90, ge=1, le=730, description="Lookback window in days"),
    entity_type: str = Query("institution", description="Entity type: institution or company"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Get entities with recent behavioral change points.

    Returns institutions or companies where a CUSUM-detected change point
    (sudden shift in risk pattern) occurred within the specified number of days.
    """
    import json as _json
    from datetime import timedelta as _td

    pool = await get_asyncpg_pool()
    try:
        async with pool.acquire() as conn:
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'entity_temporal_profiles'
                )
            """)
            if not table_exists:
                return RecentChangePointsResponse(
                    total=0, days_lookback=days, entities=[]
                )

            cutoff_date = (datetime.utcnow() - _td(days=days)).date()

            rows = await conn.fetch(
                """
                SELECT
                    entity_name, entity_type,
                    last_change_point_date,
                    trajectory, trajectory_confidence,
                    risk_trend_slope,
                    change_points,
                    tender_count
                FROM entity_temporal_profiles
                WHERE entity_type = $1
                  AND last_change_point_date IS NOT NULL
                  AND last_change_point_date >= $2
                ORDER BY last_change_point_date DESC
                LIMIT $3
                """,
                entity_type,
                cutoff_date,
                limit,
            )

            entities = []
            for row in rows:
                cp_raw = row["change_points"]
                if isinstance(cp_raw, str):
                    cps = _json.loads(cp_raw) if cp_raw else []
                elif isinstance(cp_raw, list):
                    cps = cp_raw
                else:
                    cps = []

                entities.append(
                    ChangePointItem(
                        entity_name=row["entity_name"],
                        entity_type=row["entity_type"],
                        last_change_point_date=(
                            row["last_change_point_date"].isoformat()
                            if row["last_change_point_date"]
                            else None
                        ),
                        trajectory=row["trajectory"],
                        trajectory_confidence=row["trajectory_confidence"],
                        risk_trend_slope=row["risk_trend_slope"],
                        change_points=cps,
                        tender_count=row["tender_count"] or 0,
                    )
                )

            return RecentChangePointsResponse(
                total=len(entities),
                days_lookback=days,
                entities=entities,
            )

    except Exception as e:
        logger.error(f"Error fetching change points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch change points: {str(e)}",
        )


@router.get(
    "/temporal/{entity_name:path}",
    response_model=TemporalProfileResponse,
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_temporal_profile(
    entity_name: str,
    entity_type: str = Query("institution", description="Entity type: institution or company"),
    live: bool = Query(False, description="If true, compute fresh profile instead of using cached"),
    window_days: int = Query(730, ge=30, le=2555, description="Lookback window in days"),
):
    """
    Get temporal risk profile for an institution or company.

    By default, returns the pre-computed profile from entity_temporal_profiles.
    Set live=true to compute a fresh profile on-the-fly (slower but always current).

    Path Parameters:
    - entity_name: Name of the institution or company

    Query Parameters:
    - entity_type: 'institution' or 'company' (default: institution)
    - live: Compute fresh profile instead of using cached (default: false)
    - window_days: Lookback window in days (default: 730)
    """
    import json as _json

    pool = await get_asyncpg_pool()

    try:
        # If not live, try to load cached profile first
        if not live:
            async with pool.acquire() as conn:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'entity_temporal_profiles'
                    )
                """)

                if table_exists:
                    row = await conn.fetchrow(
                        """
                        SELECT
                            entity_name, entity_type,
                            temporal_features, trajectory,
                            trajectory_confidence, trajectory_description,
                            trajectory_recommendation,
                            change_points, summary_stats,
                            tender_count, period_start, period_end,
                            computed_at
                        FROM entity_temporal_profiles
                        WHERE entity_name = $1 AND entity_type = $2
                        """,
                        entity_name,
                        entity_type,
                    )

                    if row:
                        # Parse JSONB fields
                        tf_raw = row["temporal_features"]
                        if isinstance(tf_raw, str):
                            tf = _json.loads(tf_raw) if tf_raw else {}
                        elif isinstance(tf_raw, dict):
                            tf = tf_raw
                        else:
                            tf = {}

                        cp_raw = row["change_points"]
                        if isinstance(cp_raw, str):
                            cps = _json.loads(cp_raw) if cp_raw else []
                        elif isinstance(cp_raw, list):
                            cps = cp_raw
                        else:
                            cps = []

                        ss_raw = row["summary_stats"]
                        if isinstance(ss_raw, str):
                            ss = _json.loads(ss_raw) if ss_raw else {}
                        elif isinstance(ss_raw, dict):
                            ss = ss_raw
                        else:
                            ss = {}

                        return TemporalProfileResponse(
                            entity=row["entity_name"],
                            entity_type=row["entity_type"],
                            total_tenders=row["tender_count"] or 0,
                            period_start=(
                                row["period_start"].isoformat()
                                if row["period_start"]
                                else None
                            ),
                            period_end=(
                                row["period_end"].isoformat()
                                if row["period_end"]
                                else None
                            ),
                            temporal_features=tf,
                            change_points=cps,
                            trajectory={
                                "trajectory": row["trajectory"] or "unknown",
                                "confidence": row["trajectory_confidence"] or 0.0,
                                "description": row["trajectory_description"] or "",
                                "recommendation": row["trajectory_recommendation"] or "",
                            },
                            summary_stats=ss,
                            computed_at=(
                                row["computed_at"].isoformat()
                                if row["computed_at"]
                                else None
                            ),
                        )

        # Compute live profile
        try:
            from ai.corruption.ml_models.temporal_analyzer import TemporalAnalyzer
        except ImportError:
            # Fallback: try adding parent paths for server deployment
            import sys as _sys
            from pathlib import Path as _Path
            _sys.path.insert(0, str(_Path(__file__).parent.parent.parent / "ai" / "corruption"))
            from ml_models.temporal_analyzer import TemporalAnalyzer

        analyzer = TemporalAnalyzer()
        profile = await analyzer.get_entity_risk_profile(
            pool, entity_name, entity_type, window_days
        )

        return TemporalProfileResponse(
            entity=profile["entity"],
            entity_type=profile["entity_type"],
            total_tenders=profile["total_tenders"],
            period_start=profile.get("period_start"),
            period_end=profile.get("period_end"),
            temporal_features=profile.get("temporal_features", {}),
            change_points=profile.get("change_points", []),
            trajectory=profile.get("trajectory", {}),
            summary_stats=profile.get("summary_stats", {}),
            computed_at=profile.get("computed_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in temporal profile for {entity_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get temporal profile: {str(e)}",
        )


# ============================================================================
# CONFORMAL PREDICTION / CALIBRATION ENDPOINTS (Phase 3.5)
# ============================================================================


@router.get(
    "/calibration/status",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_calibration_status():
    """
    Get current model calibration quality metrics.

    Returns the latest conformal calibration parameters, ECE/MCE metrics,
    and whether the model is currently well-calibrated.
    """
    import json
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if tables exist
            tables_exist = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'conformal_calibration'
                )
            """)

            if not tables_exist:
                return {
                    "status": "not_calibrated",
                    "message": "Conformal calibration tables not yet created. "
                               "Run migration 040_conformal.sql first.",
                    "calibration": None,
                    "latest_check": None,
                    "prediction_stats": None,
                }

            # Get latest conformal calibration parameters
            cal_row = await conn.fetchrow("""
                SELECT
                    model_name, alpha, quantile_threshold,
                    platt_a, platt_b, calibration_set_size,
                    ece, mce, is_well_calibrated, fitted_at
                FROM conformal_calibration
                ORDER BY fitted_at DESC
                LIMIT 1
            """)

            # Get latest calibration check
            check_row = await conn.fetchrow("""
                SELECT
                    model_name, ece, mce,
                    coverage_actual, coverage_target,
                    n_samples, drift_detected, checked_at
                FROM calibration_checks
                ORDER BY checked_at DESC
                LIMIT 1
            """)

            # Get calibrated prediction stats
            stats_row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_calibrated,
                    AVG(calibrated_probability) as avg_calibrated_prob,
                    AVG(set_width) as avg_set_width,
                    MIN(calibrated_at) as earliest_calibration,
                    MAX(calibrated_at) as latest_calibration
                FROM calibrated_predictions
            """)

            if not cal_row:
                return {
                    "status": "not_calibrated",
                    "message": "No conformal calibration has been performed yet. "
                               "Run batch_calibrate.py to calibrate risk scores.",
                    "calibration": None,
                    "latest_check": None,
                    "prediction_stats": None,
                }

            calibration = {
                "model_name": cal_row['model_name'],
                "alpha": float(cal_row['alpha']),
                "coverage_level": round(1 - float(cal_row['alpha']), 2),
                "quantile_threshold": float(cal_row['quantile_threshold']) if cal_row['quantile_threshold'] else None,
                "platt_a": float(cal_row['platt_a']) if cal_row['platt_a'] else None,
                "platt_b": float(cal_row['platt_b']) if cal_row['platt_b'] else None,
                "calibration_set_size": cal_row['calibration_set_size'],
                "ece": float(cal_row['ece']) if cal_row['ece'] else None,
                "mce": float(cal_row['mce']) if cal_row['mce'] else None,
                "is_well_calibrated": cal_row['is_well_calibrated'],
                "fitted_at": cal_row['fitted_at'].isoformat() if cal_row['fitted_at'] else None,
            }

            latest_check = None
            if check_row:
                latest_check = {
                    "model_name": check_row['model_name'],
                    "ece": float(check_row['ece']) if check_row['ece'] else None,
                    "mce": float(check_row['mce']) if check_row['mce'] else None,
                    "coverage_actual": float(check_row['coverage_actual']) if check_row['coverage_actual'] else None,
                    "coverage_target": float(check_row['coverage_target']) if check_row['coverage_target'] else None,
                    "n_samples": check_row['n_samples'],
                    "drift_detected": check_row['drift_detected'],
                    "checked_at": check_row['checked_at'].isoformat() if check_row['checked_at'] else None,
                }

            prediction_stats = None
            if stats_row and stats_row['total_calibrated']:
                prediction_stats = {
                    "total_calibrated": stats_row['total_calibrated'],
                    "avg_calibrated_probability": round(float(stats_row['avg_calibrated_prob']), 4) if stats_row['avg_calibrated_prob'] else None,
                    "avg_set_width": round(float(stats_row['avg_set_width']), 4) if stats_row['avg_set_width'] else None,
                    "earliest_calibration": stats_row['earliest_calibration'].isoformat() if stats_row['earliest_calibration'] else None,
                    "latest_calibration": stats_row['latest_calibration'].isoformat() if stats_row['latest_calibration'] else None,
                }

            return {
                "status": "calibrated" if calibration['is_well_calibrated'] else "needs_recalibration",
                "calibration": calibration,
                "latest_check": latest_check,
                "prediction_stats": prediction_stats,
            }

    except Exception as e:
        logger.error(f"Error fetching calibration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calibration status: {str(e)}"
        )


@router.get(
    "/calibrated/{tender_id:path}",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_calibrated_prediction(tender_id: str):
    """
    Get calibrated risk prediction with coverage guarantee for a specific tender.

    Returns the raw model score, Platt-scaled calibrated probability,
    and conformal prediction interval with coverage guarantee.
    """
    import json
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'calibrated_predictions'
                )
            """)

            if not table_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Calibrated predictions table not yet created. "
                           "Run migration 040_conformal.sql first."
                )

            row = await conn.fetchrow("""
                SELECT
                    cp.tender_id,
                    cp.raw_score,
                    cp.calibrated_probability,
                    cp.prediction_lower,
                    cp.prediction_upper,
                    cp.set_width,
                    cp.model_name,
                    cp.calibrated_at,
                    t.title,
                    t.procuring_entity,
                    t.winner,
                    t.estimated_value_mkd,
                    t.status,
                    mp.risk_score as original_risk_score,
                    mp.risk_level as original_risk_level
                FROM calibrated_predictions cp
                JOIN tenders t ON cp.tender_id = t.tender_id
                LEFT JOIN ml_predictions mp ON cp.tender_id = mp.tender_id
                    AND mp.model_version = cp.model_name
                WHERE cp.tender_id = $1
            """, tender_id)

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No calibrated prediction found for tender {tender_id}. "
                           f"Run batch calibration first."
                )

            # Get calibration parameters for context
            cal_row = await conn.fetchrow("""
                SELECT alpha, quantile_threshold, is_well_calibrated
                FROM conformal_calibration
                WHERE model_name = $1
                ORDER BY fitted_at DESC
                LIMIT 1
            """, row['model_name'] or 'xgboost_rf_v1')

            # Determine calibrated risk level
            cal_prob = float(row['calibrated_probability'])
            if cal_prob >= 0.8:
                cal_risk_level = "critical"
            elif cal_prob >= 0.6:
                cal_risk_level = "high"
            elif cal_prob >= 0.4:
                cal_risk_level = "medium"
            elif cal_prob >= 0.2:
                cal_risk_level = "low"
            else:
                cal_risk_level = "minimal"

            result = {
                "tender_id": row['tender_id'],
                "title": row['title'],
                "procuring_entity": row['procuring_entity'],
                "winner": row['winner'],
                "estimated_value_mkd": float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                "status": row['status'],
                "raw_score": float(row['raw_score']),
                "calibrated_probability": cal_prob,
                "calibrated_risk_level": cal_risk_level,
                "prediction_interval": {
                    "lower": float(row['prediction_lower']),
                    "upper": float(row['prediction_upper']),
                    "width": float(row['set_width']),
                },
                "original_risk_score": float(row['original_risk_score']) if row['original_risk_score'] else None,
                "original_risk_level": row['original_risk_level'],
                "model_name": row['model_name'],
                "calibrated_at": row['calibrated_at'].isoformat() if row['calibrated_at'] else None,
            }

            if cal_row:
                result["coverage_guarantee"] = {
                    "coverage_level": round(1 - float(cal_row['alpha']), 2),
                    "alpha": float(cal_row['alpha']),
                    "conformal_quantile": float(cal_row['quantile_threshold']) if cal_row['quantile_threshold'] else None,
                    "is_well_calibrated": cal_row['is_well_calibrated'],
                }

            result["disclaimer"] = (
                "Калибрираната веројатност дава статистички гарантирани "
                "интервали на предвидување. Оваа анализа е само за "
                "информативни цели."
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching calibrated prediction for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calibrated prediction: {str(e)}"
        )


@router.get(
    "/calibration/history",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_calibration_history(
    limit: int = Query(default=20, ge=1, le=100, description="Number of checks to return"),
):
    """
    Get calibration check history over time.

    Returns a time series of calibration quality metrics (ECE, MCE, coverage)
    for monitoring drift.
    """
    pool = await get_asyncpg_pool()

    try:
        async with pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'calibration_checks'
                )
            """)

            if not table_exists:
                return {
                    "checks": [],
                    "summary": {
                        "total_checks": 0,
                        "drift_alerts": 0,
                        "avg_ece": None,
                        "latest_ece": None,
                        "latest_drift": None,
                    },
                }

            rows = await conn.fetch("""
                SELECT
                    check_id, model_name, ece, mce,
                    coverage_actual, coverage_target,
                    n_samples, drift_detected, checked_at
                FROM calibration_checks
                ORDER BY checked_at DESC
                LIMIT $1
            """, limit)

            checks = []
            for row in rows:
                checks.append({
                    "check_id": row['check_id'],
                    "model_name": row['model_name'],
                    "ece": float(row['ece']) if row['ece'] else None,
                    "mce": float(row['mce']) if row['mce'] else None,
                    "coverage_actual": float(row['coverage_actual']) if row['coverage_actual'] else None,
                    "coverage_target": float(row['coverage_target']) if row['coverage_target'] else None,
                    "n_samples": row['n_samples'],
                    "drift_detected": row['drift_detected'],
                    "checked_at": row['checked_at'].isoformat() if row['checked_at'] else None,
                })

            # Compute summary
            if checks:
                ece_values = [c['ece'] for c in checks if c['ece'] is not None]
                drift_count = sum(1 for c in checks if c['drift_detected'])
                summary = {
                    "total_checks": len(checks),
                    "drift_alerts": drift_count,
                    "avg_ece": round(sum(ece_values) / len(ece_values), 4) if ece_values else None,
                    "latest_ece": checks[0]['ece'] if checks else None,
                    "latest_drift": checks[0]['drift_detected'] if checks else None,
                }
            else:
                summary = {
                    "total_checks": 0,
                    "drift_alerts": 0,
                    "avg_ece": None,
                    "latest_ece": None,
                    "latest_drift": None,
                }

            return {
                "checks": checks,
                "summary": summary,
            }

    except Exception as e:
        logger.error(f"Error fetching calibration history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calibration history: {str(e)}"
        )


# ============================================================================
# PHASE 4.2: INVESTIGATION CASE MANAGEMENT ENDPOINTS
# ============================================================================


@router.post("/investigations/cases", dependencies=[Depends(require_admin)])
async def create_investigation_case(body: dict):
    """
    Create a new investigation case.

    Body Parameters:
    - title (str, required): Case title
    - description (str, optional): Case description
    - priority (str, optional): low, medium, high, critical (default: medium)
    - assigned_to (str, optional): Username of assigned analyst
    - created_by (str, optional): Username of case creator
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        title = body.get("title")
        if not title or not str(title).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'title' is required and cannot be empty"
            )

        case = await manager.create_case(
            pool=pool,
            title=str(title).strip(),
            description=body.get("description"),
            priority=body.get("priority", "medium"),
            assigned_to=body.get("assigned_to"),
            created_by=body.get("created_by"),
        )
        return case

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating investigation case: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create investigation case: {str(e)}"
        )


@router.get("/investigations/cases", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def list_investigation_cases(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: open, in_progress, review, closed, archived"),
    priority: Optional[str] = Query(None, description="Filter by priority: low, medium, high, critical"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned analyst"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    List investigation cases with pagination and filters.

    Query Parameters:
    - status: Filter by case status
    - priority: Filter by priority level
    - assigned_to: Filter by assigned analyst
    - page: Page number (default 1)
    - page_size: Results per page (default 20, max 100)
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        offset = (page - 1) * page_size

        cases, total = await manager.list_cases(
            pool=pool,
            status=status_filter,
            priority=priority,
            assigned_to=assigned_to,
            offset=offset,
            limit=page_size,
        )

        return {
            "cases": cases,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error listing investigation cases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list investigation cases: {str(e)}"
        )


@router.get("/investigations/dashboard", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_investigations_dashboard():
    """
    Get investigation dashboard summary.

    Returns aggregate statistics across all investigation cases:
    - Total cases and breakdown by status/priority
    - Open case count
    - Total attached tenders, entities, evidence items
    - Assigned analyst workloads
    - Recent activity feed
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        dashboard = await manager.get_dashboard(pool)
        return dashboard

    except Exception as e:
        logger.error(f"Error fetching investigations dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch investigations dashboard: {str(e)}"
        )


@router.get("/investigations/cases/{case_id}", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_investigation_case(case_id: int):
    """
    Get full investigation case details.

    Returns the case with all attached tenders (with risk scores),
    entities, evidence summary, and recent notes.

    Path Parameters:
    - case_id: The investigation case ID
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        case = await manager.get_case(pool, case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case {case_id} not found"
            )
        return case

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching investigation case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch investigation case: {str(e)}"
        )


@router.patch("/investigations/cases/{case_id}", dependencies=[Depends(require_admin)])
async def update_investigation_case(case_id: int, body: dict):
    """
    Update case status, priority, assignment, title, or description.

    Path Parameters:
    - case_id: The investigation case ID

    Body Parameters (all optional):
    - status: open, in_progress, review, closed, archived
    - priority: low, medium, high, critical
    - assigned_to: Username of analyst
    - title: Updated case title
    - description: Updated case description
    - actor: Username performing the update (for audit trail)
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        actor = body.pop("actor", None)

        case = await manager.update_case(
            pool=pool,
            case_id=case_id,
            updates=body,
            actor=actor,
        )
        return case

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating investigation case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update investigation case: {str(e)}"
        )


@router.post("/investigations/cases/{case_id}/tenders", dependencies=[Depends(require_admin)])
async def add_case_tender(case_id: int, body: dict):
    """
    Attach a tender to an investigation case.

    Path Parameters:
    - case_id: The investigation case ID

    Body Parameters:
    - tender_id (str, required): The tender ID to attach
    - role (str, optional): suspect, reference, or control (default: suspect)
    - notes (str, optional): Notes about this tender's relevance
    - actor (str, optional): Username performing the action
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        tender_id = body.get("tender_id")
        if not tender_id or not str(tender_id).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'tender_id' is required"
            )

        result = await manager.attach_tender(
            pool=pool,
            case_id=case_id,
            tender_id=str(tender_id).strip(),
            role=body.get("role", "suspect"),
            notes=body.get("notes"),
            actor=body.get("actor"),
        )
        return result

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        if "already attached" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding tender to case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add tender to case: {str(e)}"
        )


@router.delete("/investigations/cases/{case_id}/tenders/{tender_id}", dependencies=[Depends(require_admin)])
async def remove_case_tender(case_id: int, tender_id: str):
    """
    Remove a tender from an investigation case.

    Path Parameters:
    - case_id: The investigation case ID
    - tender_id: The tender ID to remove
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        removed = await manager.remove_tender(
            pool=pool,
            case_id=case_id,
            tender_id=tender_id,
        )

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} is not attached to case {case_id}"
            )

        return {"message": f"Tender {tender_id} removed from case {case_id}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing tender {tender_id} from case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove tender from case: {str(e)}"
        )


@router.post("/investigations/cases/{case_id}/entities", dependencies=[Depends(require_admin)])
async def add_case_entity(case_id: int, body: dict):
    """
    Attach an entity (company, institution, person) to an investigation case.

    Path Parameters:
    - case_id: The investigation case ID

    Body Parameters:
    - entity_id (str, required): Unique identifier for the entity
    - entity_type (str, required): company, institution, or person
    - entity_name (str, optional): Human-readable entity name
    - role (str, optional): suspect, witness, victim, or reference (default: suspect)
    - actor (str, optional): Username performing the action
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        entity_id = body.get("entity_id")
        entity_type = body.get("entity_type")
        if not entity_id or not str(entity_id).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'entity_id' is required"
            )
        if not entity_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'entity_type' is required (company, institution, or person)"
            )

        result = await manager.attach_entity(
            pool=pool,
            case_id=case_id,
            entity_id=str(entity_id).strip(),
            entity_type=entity_type,
            entity_name=body.get("entity_name"),
            role=body.get("role", "suspect"),
            actor=body.get("actor"),
        )
        return result

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        if "already attached" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding entity to case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add entity to case: {str(e)}"
        )


@router.post("/investigations/cases/{case_id}/evidence", dependencies=[Depends(require_admin)])
async def add_case_evidence(case_id: int, body: dict):
    """
    Add evidence to an investigation case.

    Path Parameters:
    - case_id: The investigation case ID

    Body Parameters:
    - evidence_type (str, required): flag, anomaly, relationship, document, or manual
    - description (str, required): Human-readable description of the evidence
    - source_module (str, optional): Module that produced this (corruption, collusion, temporal, etc.)
    - source_id (str, optional): ID of the source record
    - severity (str, optional): low, medium, high, critical (default: medium)
    - metadata (dict, optional): Additional structured data
    - actor (str, optional): Username adding the evidence
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        evidence_type = body.get("evidence_type")
        description = body.get("description")
        if not evidence_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'evidence_type' is required (flag, anomaly, relationship, document, manual)"
            )
        if not description or not str(description).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'description' is required"
            )

        result = await manager.add_evidence(
            pool=pool,
            case_id=case_id,
            evidence_type=evidence_type,
            source_module=body.get("source_module"),
            source_id=body.get("source_id"),
            description=str(description).strip(),
            severity=body.get("severity", "medium"),
            metadata=body.get("metadata"),
            actor=body.get("actor"),
        )
        return result

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding evidence to case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add evidence to case: {str(e)}"
        )


@router.get("/investigations/cases/{case_id}/evidence-chain", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_evidence_chain(case_id: int):
    """
    Get the synthesized evidence chain for an investigation case.

    Aggregates evidence from all corruption detection modules:
    - Corruption flags for attached tenders
    - Risk scores and levels
    - Company relationships and collusion indicators
    - GNN-based collusion predictions
    - Temporal risk profiles
    - Manually added evidence items

    Returns a structured chain with an auto-generated narrative summary.

    Path Parameters:
    - case_id: The investigation case ID
    """
    try:
        from ai.corruption.investigation.evidence_linker import EvidenceLinker
        linker = EvidenceLinker()
        pool = await get_asyncpg_pool()

        chain = await linker.build_evidence_chain(pool, case_id)
        return chain

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        logger.error(f"Error building evidence chain for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build evidence chain: {str(e)}"
        )


@router.post("/investigations/cases/{case_id}/notes", dependencies=[Depends(require_admin)])
async def add_case_note(case_id: int, body: dict):
    """
    Add an analyst note to an investigation case.

    Path Parameters:
    - case_id: The investigation case ID

    Body Parameters:
    - author (str, required): Username of the note author
    - content (str, required): Note content text
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        author = body.get("author")
        content = body.get("content")
        if not author or not str(author).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'author' is required"
            )
        if not content or not str(content).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'content' is required"
            )

        result = await manager.add_note(
            pool=pool,
            case_id=case_id,
            author=str(author).strip(),
            content=str(content).strip(),
        )
        return result

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding note to case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add note to case: {str(e)}"
        )


@router.get("/investigations/cases/{case_id}/timeline", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_case_timeline(case_id: int, limit: int = Query(50, ge=1, le=200)):
    """
    Get the activity timeline for an investigation case.

    Returns a chronological audit trail of all actions taken on the case:
    created, status_changed, tender_added, entity_added, evidence_added,
    note_added, etc.

    Path Parameters:
    - case_id: The investigation case ID

    Query Parameters:
    - limit: Maximum number of entries (default 50, max 200)
    """
    try:
        from ai.corruption.investigation.case_manager import CaseManager
        manager = CaseManager()
        pool = await get_asyncpg_pool()

        # Verify case exists first
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM investigation_cases WHERE case_id = $1", case_id
            )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation case {case_id} not found"
            )

        timeline = await manager.get_timeline(pool, case_id, limit=limit)
        return {
            "case_id": case_id,
            "entries": timeline,
            "count": len(timeline),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeline for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch case timeline: {str(e)}"
        )


# ============================================================================
# PHASE 4.3: COUNTERFACTUAL EXPLANATION ENDPOINTS
# ============================================================================


@router.get(
    "/counterfactuals/{tender_id:path}",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_counterfactuals(
    tender_id: str,
    top_k: int = Query(default=5, ge=1, le=10),
):
    """Get counterfactual explanations for a tender's risk score.

    Returns what would need to change for the tender to not be flagged as
    high-risk.  Results are cached in PostgreSQL so subsequent requests are
    instantaneous.
    """
    import json as _json
    import sys as _sys
    from pathlib import Path as _Path

    pool = await get_asyncpg_pool()

    try:
        # Lazy imports to avoid import-time dependency on ai.corruption
        _explainability_dir = str(
            _Path(__file__).parent.parent.parent / "ai" / "corruption" / "explainability"
        )
        if _explainability_dir not in _sys.path:
            _sys.path.insert(0, _explainability_dir)

        from counterfactual_cache import CounterfactualCache
        from counterfactual_engine import CounterfactualEngine

        # --- 1. Check cache first ---
        cached = await CounterfactualCache.get_cached(pool, tender_id)
        if cached:
            logger.info(f"Returning {len(cached)} cached counterfactuals for {tender_id}")
            return {
                "tender_id": tender_id,
                "counterfactuals": cached[:top_k],
                "cached": True,
                "total": len(cached[:top_k]),
            }

        # --- 2. Fetch risk score ---
        async with pool.acquire() as conn:
            score_row = await conn.fetchrow(
                "SELECT risk_score FROM tender_risk_scores WHERE tender_id = $1",
                tender_id,
            )
            if not score_row or score_row['risk_score'] is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No risk score found for tender {tender_id}",
                )
            risk_score = float(score_row['risk_score'])

            # --- 3. Fetch features from corruption_flags ---
            flag_rows = await conn.fetch(
                """
                SELECT flag_type, MAX(score) AS max_score
                FROM corruption_flags
                WHERE tender_id = $1
                  AND (false_positive IS NULL OR false_positive = false)
                GROUP BY flag_type
                """,
                tender_id,
            )

            features: Dict[str, Any] = {}
            for row in flag_rows:
                ft = row['flag_type']
                score_val = float(row['max_score']) if row['max_score'] is not None else 0.0
                feat_def = CounterfactualEngine.FEATURE_DEFS.get(ft, {})
                if feat_def.get('type') == 'binary':
                    features[ft] = 1 if score_val > 0 else 0
                else:
                    features[ft] = score_val

            # Tender metadata
            tender_row = await conn.fetchrow(
                "SELECT num_bidders, estimated_value_mkd FROM tenders WHERE tender_id = $1",
                tender_id,
            )
            if tender_row:
                features['num_bidders'] = (
                    int(tender_row['num_bidders']) if tender_row['num_bidders'] else 1
                )
                features['estimated_value_mkd'] = (
                    float(tender_row['estimated_value_mkd'])
                    if tender_row['estimated_value_mkd']
                    else 0.0
                )

        if not features:
            return {
                "tender_id": tender_id,
                "counterfactuals": [],
                "cached": False,
                "total": 0,
                "message": "No corruption flags found for this tender",
            }

        # --- 4. Generate counterfactuals ---
        engine = CounterfactualEngine(target_score=30.0)
        counterfactuals = engine.generate(
            original_features=features,
            original_score=risk_score,
            top_k=top_k,
        )

        # --- 5. Cache results ---
        await CounterfactualCache.save(pool, tender_id, risk_score, counterfactuals)

        # --- 6. Return ---
        return {
            "tender_id": tender_id,
            "counterfactuals": counterfactuals,
            "cached": False,
            "total": len(counterfactuals),
            "original_score": risk_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating counterfactuals for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate counterfactual explanations: {str(e)}",
        )


@router.get(
    "/counterfactuals/{tender_id:path}/actionable",
    dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))],
)
async def get_actionable_counterfactuals(tender_id: str):
    """Get only actionable/feasible counterfactual changes for a tender.

    Filters counterfactuals to those with feasibility > 0.6 and enriches
    each change with human-readable descriptions and direction metadata.
    """
    import sys as _sys
    from pathlib import Path as _Path

    pool = await get_asyncpg_pool()

    try:
        _explainability_dir = str(
            _Path(__file__).parent.parent.parent / "ai" / "corruption" / "explainability"
        )
        if _explainability_dir not in _sys.path:
            _sys.path.insert(0, _explainability_dir)

        from counterfactual_cache import CounterfactualCache
        from counterfactual_engine import CounterfactualEngine

        # Fetch all counterfactuals (cached or freshly generated)
        cached = await CounterfactualCache.get_cached(pool, tender_id)

        if not cached:
            # Generate fresh counterfactuals
            async with pool.acquire() as conn:
                score_row = await conn.fetchrow(
                    "SELECT risk_score FROM tender_risk_scores WHERE tender_id = $1",
                    tender_id,
                )
                if not score_row or score_row['risk_score'] is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No risk score found for tender {tender_id}",
                    )
                risk_score = float(score_row['risk_score'])

                flag_rows = await conn.fetch(
                    """
                    SELECT flag_type, MAX(score) AS max_score
                    FROM corruption_flags
                    WHERE tender_id = $1
                      AND (false_positive IS NULL OR false_positive = false)
                    GROUP BY flag_type
                    """,
                    tender_id,
                )

                features: Dict[str, Any] = {}
                for row in flag_rows:
                    ft = row['flag_type']
                    score_val = float(row['max_score']) if row['max_score'] is not None else 0.0
                    feat_def = CounterfactualEngine.FEATURE_DEFS.get(ft, {})
                    if feat_def.get('type') == 'binary':
                        features[ft] = 1 if score_val > 0 else 0
                    else:
                        features[ft] = score_val

                tender_row = await conn.fetchrow(
                    "SELECT num_bidders, estimated_value_mkd FROM tenders WHERE tender_id = $1",
                    tender_id,
                )
                if tender_row:
                    features['num_bidders'] = (
                        int(tender_row['num_bidders']) if tender_row['num_bidders'] else 1
                    )
                    features['estimated_value_mkd'] = (
                        float(tender_row['estimated_value_mkd'])
                        if tender_row['estimated_value_mkd']
                        else 0.0
                    )

            if not features:
                return {
                    "tender_id": tender_id,
                    "actionable_counterfactuals": [],
                    "total": 0,
                    "message": "No corruption flags found for this tender",
                }

            engine = CounterfactualEngine(target_score=30.0)
            cached = engine.generate(
                original_features=features,
                original_score=risk_score,
                top_k=5,
            )
            await CounterfactualCache.save(pool, tender_id, risk_score, cached)

        # Filter to actionable only (feasibility > 0.6)
        engine = CounterfactualEngine()
        actionable = engine.get_actionable_changes(cached)

        return {
            "tender_id": tender_id,
            "actionable_counterfactuals": actionable,
            "total": len(actionable),
            "total_before_filter": len(cached) if cached else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching actionable counterfactuals for {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get actionable counterfactuals: {str(e)}",
        )


@router.post(
    "/counterfactuals/batch",
    dependencies=[Depends(require_admin)],
)
async def batch_generate_counterfactuals(body: dict):
    """Batch generate counterfactuals for multiple tenders (admin only).

    Request body:
        {
            "tender_ids": ["123/2024", "456/2024", ...],
            "target_score": 30.0,   // optional, default 30
            "top_k": 5              // optional, default 5
        }

    If tender_ids is not provided, processes the top 50 high-risk tenders
    without cached counterfactuals.
    """
    import sys as _sys
    from pathlib import Path as _Path

    pool = await get_asyncpg_pool()

    try:
        _explainability_dir = str(
            _Path(__file__).parent.parent.parent / "ai" / "corruption" / "explainability"
        )
        if _explainability_dir not in _sys.path:
            _sys.path.insert(0, _explainability_dir)

        from counterfactual_cache import CounterfactualCache
        from counterfactual_engine import CounterfactualEngine

        tender_ids = body.get('tender_ids', [])
        target_score = float(body.get('target_score', 30.0))
        top_k_param = int(body.get('top_k', 5))

        # If no specific tenders, auto-select high-risk ones without cached CFs
        if not tender_ids:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT trs.tender_id
                    FROM tender_risk_scores trs
                    WHERE trs.risk_score >= 60
                      AND NOT EXISTS (
                          SELECT 1 FROM counterfactual_explanations ce
                          WHERE ce.tender_id = trs.tender_id
                      )
                    ORDER BY trs.risk_score DESC
                    LIMIT 50
                    """,
                )
                tender_ids = [row['tender_id'] for row in rows]

        if not tender_ids:
            return {
                "message": "No tenders to process",
                "processed": 0,
                "failed": 0,
                "total_counterfactuals": 0,
            }

        engine = CounterfactualEngine(target_score=target_score)
        processed = 0
        failed = 0
        total_cfs = 0
        results_summary: List[Dict[str, Any]] = []

        for tid in tender_ids:
            try:
                async with pool.acquire() as conn:
                    score_row = await conn.fetchrow(
                        "SELECT risk_score FROM tender_risk_scores WHERE tender_id = $1",
                        tid,
                    )
                    if not score_row or score_row['risk_score'] is None:
                        results_summary.append({
                            "tender_id": tid,
                            "status": "skipped",
                            "reason": "no risk score",
                        })
                        failed += 1
                        continue

                    risk_score = float(score_row['risk_score'])

                    flag_rows = await conn.fetch(
                        """
                        SELECT flag_type, MAX(score) AS max_score
                        FROM corruption_flags
                        WHERE tender_id = $1
                          AND (false_positive IS NULL OR false_positive = false)
                        GROUP BY flag_type
                        """,
                        tid,
                    )

                    features: Dict[str, Any] = {}
                    for row in flag_rows:
                        ft = row['flag_type']
                        score_val = float(row['max_score']) if row['max_score'] is not None else 0.0
                        feat_def = CounterfactualEngine.FEATURE_DEFS.get(ft, {})
                        if feat_def.get('type') == 'binary':
                            features[ft] = 1 if score_val > 0 else 0
                        else:
                            features[ft] = score_val

                    tender_row = await conn.fetchrow(
                        "SELECT num_bidders, estimated_value_mkd FROM tenders WHERE tender_id = $1",
                        tid,
                    )
                    if tender_row:
                        features['num_bidders'] = (
                            int(tender_row['num_bidders']) if tender_row['num_bidders'] else 1
                        )
                        features['estimated_value_mkd'] = (
                            float(tender_row['estimated_value_mkd'])
                            if tender_row['estimated_value_mkd']
                            else 0.0
                        )

                if not features:
                    results_summary.append({
                        "tender_id": tid,
                        "status": "skipped",
                        "reason": "no features",
                    })
                    failed += 1
                    continue

                counterfactuals = engine.generate(
                    original_features=features,
                    original_score=risk_score,
                    top_k=top_k_param,
                )

                if counterfactuals:
                    await CounterfactualCache.save(pool, tid, risk_score, counterfactuals)
                    total_cfs += len(counterfactuals)

                processed += 1
                results_summary.append({
                    "tender_id": tid,
                    "status": "ok",
                    "risk_score": risk_score,
                    "counterfactuals_generated": len(counterfactuals),
                })

            except Exception as e:
                logger.error(f"Batch counterfactual failed for {tid}: {e}")
                failed += 1
                results_summary.append({
                    "tender_id": tid,
                    "status": "error",
                    "reason": str(e),
                })

        return {
            "message": f"Processed {processed} tenders, {failed} failed",
            "processed": processed,
            "failed": failed,
            "total_counterfactuals": total_cfs,
            "details": results_summary,
        }

    except Exception as e:
        logger.error(f"Batch counterfactual generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch counterfactual generation failed: {str(e)}",
        )


# ============================================================================
# PHASE 4.4: CORRUPTION ALERT PIPELINE ENDPOINTS
# ============================================================================
# These endpoints manage alert subscriptions and alert delivery for the
# real-time corruption alert pipeline. They live under the /api/corruption
# router prefix, so full paths are:
#   /api/corruption/alerts/subscriptions
#   /api/corruption/alerts
#   /api/corruption/alerts/{alert_id}/read
#   /api/corruption/alerts/evaluate
#   /api/corruption/alerts/stats
#   /api/corruption/alerts/rules
# ============================================================================


@router.get("/alerts/rules", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def list_alert_rules():
    """
    List all available alert rule types with their metadata.

    Returns a list of rule definitions that users can subscribe to,
    including rule_type, name, description, and default_severity.
    """
    try:
        from ai.corruption.alerts.alert_rules import list_available_rules
        rules = list_available_rules()
        return {"rules": rules, "total": len(rules)}
    except Exception as e:
        logger.error(f"Error listing alert rules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert rules: {str(e)}"
        )


@router.get("/alerts/subscriptions", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def list_alert_subscriptions(
    user_id: str = Query(..., description="User ID to list subscriptions for"),
    active_only: bool = Query(True, description="Only show active subscriptions"),
):
    """
    List a user's alert subscriptions.

    Query Parameters:
    - user_id (str, required): The user whose subscriptions to list
    - active_only (bool, optional): If true, only return active subscriptions (default: true)

    Returns:
    - subscriptions: List of subscription objects
    - total: Total count
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            if active_only:
                rows = await conn.fetch("""
                    SELECT
                        subscription_id, user_id, rule_type, rule_config,
                        severity_filter, active, created_at, updated_at
                    FROM corruption_alert_subscriptions
                    WHERE user_id = $1 AND active = TRUE
                    ORDER BY created_at DESC
                """, user_id)
            else:
                rows = await conn.fetch("""
                    SELECT
                        subscription_id, user_id, rule_type, rule_config,
                        severity_filter, active, created_at, updated_at
                    FROM corruption_alert_subscriptions
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """, user_id)

            subscriptions = []
            for row in rows:
                sub = dict(row)
                # Handle JSONB rule_config
                rc = sub.get('rule_config')
                if isinstance(rc, str):
                    import json as _json
                    try:
                        sub['rule_config'] = _json.loads(rc) if rc else {}
                    except (ValueError, TypeError):
                        sub['rule_config'] = {}
                elif not isinstance(rc, dict):
                    sub['rule_config'] = {}

                # Convert datetimes for serialization
                for dt_field in ('created_at', 'updated_at'):
                    if isinstance(sub.get(dt_field), datetime):
                        sub[dt_field] = sub[dt_field].isoformat()

                subscriptions.append(sub)

            return {
                "subscriptions": subscriptions,
                "total": len(subscriptions),
            }

    except Exception as e:
        logger.error(f"Error listing alert subscriptions for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert subscriptions: {str(e)}"
        )


@router.post("/alerts/subscriptions", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def create_alert_subscription(body: dict):
    """
    Create a new alert subscription.

    Body Parameters:
    - user_id (str, required): User ID
    - rule_type (str, required): One of: high_risk_score, single_bidder_high_value,
      watched_entity, multiple_flags, repeat_pattern, escalating_risk
    - rule_config (dict, optional): Rule-specific configuration. Examples:
        - high_risk_score: {"threshold": 80}
        - single_bidder_high_value: {"value_threshold": 10000000}
        - watched_entity: {"watched_entities": ["Company A", "Institution B"]}
        - multiple_flags: {"flag_threshold": 4}
        - repeat_pattern: {"repeat_threshold": 5}
        - escalating_risk: {}
    - severity_filter (str, optional): Minimum severity to receive alerts
      (low, medium, high, critical). NULL means all.

    Returns:
    - The created subscription object with subscription_id
    """
    try:
        import json as _json
        from ai.corruption.alerts.alert_rules import AVAILABLE_RULES, create_rule

        user_id = body.get("user_id")
        rule_type = body.get("rule_type")
        rule_config = body.get("rule_config", {})
        severity_filter = body.get("severity_filter")

        # Validation
        if not user_id or not str(user_id).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'user_id' is required"
            )

        if not rule_type or rule_type not in AVAILABLE_RULES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field 'rule_type' must be one of: {list(AVAILABLE_RULES.keys())}"
            )

        if severity_filter and severity_filter not in ('low', 'medium', 'high', 'critical'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'severity_filter' must be one of: low, medium, high, critical"
            )

        # Validate rule_config by attempting to create the rule
        try:
            create_rule(rule_type, rule_config or {})
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid rule_config: {ve}"
            )

        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Check for duplicate active subscription (same user + rule_type + config)
            existing = await conn.fetchval("""
                SELECT subscription_id FROM corruption_alert_subscriptions
                WHERE user_id = $1 AND rule_type = $2 AND active = TRUE
                  AND rule_config = $3::jsonb
            """, str(user_id).strip(), rule_type, _json.dumps(rule_config or {}, default=str))

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Active subscription already exists (id={existing}) for this user/rule/config"
                )

            row = await conn.fetchrow("""
                INSERT INTO corruption_alert_subscriptions
                    (user_id, rule_type, rule_config, severity_filter)
                VALUES ($1, $2, $3::jsonb, $4)
                RETURNING subscription_id, user_id, rule_type, rule_config,
                          severity_filter, active, created_at, updated_at
            """, str(user_id).strip(), rule_type,
                _json.dumps(rule_config or {}, default=str),
                severity_filter)

            result = dict(row)
            rc = result.get('rule_config')
            if isinstance(rc, str):
                try:
                    result['rule_config'] = _json.loads(rc) if rc else {}
                except (ValueError, TypeError):
                    result['rule_config'] = {}
            for dt_field in ('created_at', 'updated_at'):
                if isinstance(result.get(dt_field), datetime):
                    result[dt_field] = result[dt_field].isoformat()

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating alert subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert subscription: {str(e)}"
        )


@router.patch("/alerts/subscriptions/{subscription_id}", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def update_alert_subscription(subscription_id: int, body: dict):
    """
    Update an alert subscription (toggle active, change config, severity filter).

    Path Parameters:
    - subscription_id: The subscription ID to update

    Body Parameters (all optional):
    - active (bool): Enable/disable the subscription
    - rule_config (dict): Updated rule configuration
    - severity_filter (str): Updated minimum severity filter
    """
    try:
        import json as _json

        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Verify subscription exists
            existing = await conn.fetchrow("""
                SELECT subscription_id, user_id, rule_type, rule_config,
                       severity_filter, active
                FROM corruption_alert_subscriptions
                WHERE subscription_id = $1
            """, subscription_id)

            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Subscription {subscription_id} not found"
                )

            # Build update fields
            updates = []
            params = []
            param_idx = 0

            if 'active' in body:
                param_idx += 1
                updates.append(f"active = ${param_idx}")
                params.append(bool(body['active']))

            if 'rule_config' in body:
                rule_config = body['rule_config']
                # Validate the new config
                from ai.corruption.alerts.alert_rules import create_rule as _create_rule
                try:
                    _create_rule(existing['rule_type'], rule_config or {})
                except ValueError as ve:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid rule_config: {ve}"
                    )
                param_idx += 1
                updates.append(f"rule_config = ${param_idx}::jsonb")
                params.append(_json.dumps(rule_config or {}, default=str))

            if 'severity_filter' in body:
                sf = body['severity_filter']
                if sf is not None and sf not in ('low', 'medium', 'high', 'critical'):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="severity_filter must be one of: low, medium, high, critical (or null)"
                    )
                param_idx += 1
                updates.append(f"severity_filter = ${param_idx}")
                params.append(sf)

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid fields to update. Accepted: active, rule_config, severity_filter"
                )

            updates.append("updated_at = NOW()")
            param_idx += 1
            params.append(subscription_id)

            set_clause = ", ".join(updates)
            row = await conn.fetchrow(f"""
                UPDATE corruption_alert_subscriptions
                SET {set_clause}
                WHERE subscription_id = ${param_idx}
                RETURNING subscription_id, user_id, rule_type, rule_config,
                          severity_filter, active, created_at, updated_at
            """, *params)

            result = dict(row)
            rc = result.get('rule_config')
            if isinstance(rc, str):
                try:
                    result['rule_config'] = _json.loads(rc) if rc else {}
                except (ValueError, TypeError):
                    result['rule_config'] = {}
            for dt_field in ('created_at', 'updated_at'):
                if isinstance(result.get(dt_field), datetime):
                    result[dt_field] = result[dt_field].isoformat()

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert subscription {subscription_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update alert subscription: {str(e)}"
        )


@router.delete("/alerts/subscriptions/{subscription_id}", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def delete_alert_subscription(subscription_id: int, user_id: str = Query(..., description="User ID for ownership verification")):
    """
    Delete (deactivate) an alert subscription.

    Path Parameters:
    - subscription_id: The subscription ID to delete

    Query Parameters:
    - user_id: The user ID (must own the subscription)

    Note: This soft-deletes by setting active=FALSE rather than removing the row,
    preserving the audit trail of historical subscriptions.
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE corruption_alert_subscriptions
                SET active = FALSE, updated_at = NOW()
                WHERE subscription_id = $1 AND user_id = $2
            """, subscription_id, user_id)

            if result == 'UPDATE 0':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Subscription {subscription_id} not found for user {user_id}"
                )

            return {
                "message": f"Subscription {subscription_id} deactivated",
                "subscription_id": subscription_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert subscription {subscription_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete alert subscription: {str(e)}"
        )


@router.get("/alerts", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def list_corruption_alerts(
    user_id: str = Query(..., description="User ID to list alerts for"),
    unread_only: bool = Query(False, description="Only show unread alerts"),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$", description="Filter by severity"),
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    List corruption alerts for a user with pagination and filters.

    Query Parameters:
    - user_id (str, required): The user whose alerts to list
    - unread_only (bool, optional): Only return unread alerts (default: false)
    - severity (str, optional): Filter by severity level
    - rule_type (str, optional): Filter by rule type
    - page (int, optional): Page number (default: 1)
    - page_size (int, optional): Results per page (default: 20, max: 100)

    Returns:
    - alerts: List of alert objects
    - total: Total matching alerts
    - page, page_size, total_pages: Pagination metadata
    - unread_count: Total unread alerts for this user
    """
    try:
        import json as _json

        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Build WHERE clause
            conditions = ["user_id = $1"]
            params: list = [user_id]
            param_idx = 1

            if unread_only:
                conditions.append("read = FALSE")

            if severity:
                param_idx += 1
                conditions.append(f"severity = ${param_idx}")
                params.append(severity)

            if rule_type:
                param_idx += 1
                conditions.append(f"rule_type = ${param_idx}")
                params.append(rule_type)

            where_clause = " AND ".join(conditions)

            # Count total matching
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM corruption_alert_log WHERE {where_clause}",
                *params
            )

            # Count unread (always for this user, regardless of filters)
            unread_count = await conn.fetchval(
                "SELECT COUNT(*) FROM corruption_alert_log WHERE user_id = $1 AND read = FALSE",
                user_id
            )

            # Fetch page
            offset = (page - 1) * page_size
            param_idx += 1
            limit_param = param_idx
            param_idx += 1
            offset_param = param_idx

            rows = await conn.fetch(
                f"""
                SELECT
                    alert_id, subscription_id, user_id, tender_id,
                    rule_type, severity, title, details,
                    read, read_at, created_at
                FROM corruption_alert_log
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${limit_param} OFFSET ${offset_param}
                """,
                *params, page_size, offset
            )

            alerts = []
            for row in rows:
                alert = dict(row)
                # Handle JSONB details
                details = alert.get('details')
                if isinstance(details, str):
                    try:
                        alert['details'] = _json.loads(details) if details else {}
                    except (ValueError, TypeError):
                        alert['details'] = {}
                elif not isinstance(details, dict):
                    alert['details'] = {}

                # Convert datetimes for serialization
                for dt_field in ('read_at', 'created_at'):
                    if isinstance(alert.get(dt_field), datetime):
                        alert[dt_field] = alert[dt_field].isoformat()

                alerts.append(alert)

            return {
                "alerts": alerts,
                "total": total or 0,
                "unread_count": unread_count or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": ((total or 0) + page_size - 1) // page_size if page_size > 0 else 0,
            }

    except Exception as e:
        logger.error(f"Error listing corruption alerts for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list corruption alerts: {str(e)}"
        )


@router.patch("/alerts/{alert_id}/read", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def mark_alert_read(
    alert_id: int,
    user_id: str = Query(..., description="User ID for ownership verification"),
):
    """
    Mark a corruption alert as read.

    Path Parameters:
    - alert_id: The alert ID to mark as read

    Query Parameters:
    - user_id: The user ID (must own the alert)

    Returns:
    - Success message with updated alert_id
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE corruption_alert_log
                SET read = TRUE, read_at = NOW()
                WHERE alert_id = $1 AND user_id = $2 AND read = FALSE
            """, alert_id, user_id)

            if result == 'UPDATE 0':
                # Check if alert exists at all
                exists = await conn.fetchval(
                    "SELECT 1 FROM corruption_alert_log WHERE alert_id = $1 AND user_id = $2",
                    alert_id, user_id
                )
                if not exists:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Alert {alert_id} not found for user {user_id}"
                    )
                # Alert exists but was already read
                return {
                    "message": f"Alert {alert_id} was already read",
                    "alert_id": alert_id,
                    "already_read": True,
                }

            return {
                "message": f"Alert {alert_id} marked as read",
                "alert_id": alert_id,
                "already_read": False,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert {alert_id} as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark alert as read: {str(e)}"
        )


@router.patch("/alerts/mark-all-read", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def mark_all_alerts_read(
    user_id: str = Query(..., description="User ID"),
):
    """
    Mark all unread corruption alerts as read for a user.

    Query Parameters:
    - user_id: The user whose alerts to mark as read

    Returns:
    - Count of alerts marked as read
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE corruption_alert_log
                SET read = TRUE, read_at = NOW()
                WHERE user_id = $1 AND read = FALSE
            """, user_id)

            # Parse 'UPDATE N' to get count
            try:
                count = int(result.split()[-1])
            except (ValueError, IndexError):
                count = 0

            return {
                "message": f"Marked {count} alerts as read",
                "marked_count": count,
                "user_id": user_id,
            }

    except Exception as e:
        logger.error(f"Error marking all alerts read for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all alerts as read: {str(e)}"
        )


@router.post("/alerts/evaluate", dependencies=[Depends(require_admin)])
async def trigger_alert_evaluation(background_tasks: BackgroundTasks):
    """
    Admin: Manually trigger alert evaluation for new tenders.

    This runs the alert evaluation pipeline which:
    1. Finds all tenders with risk scores updated since the last evaluation
    2. Evaluates each tender against all active alert subscriptions
    3. Generates alerts for matching subscriptions
    4. Updates the last evaluation timestamp

    The evaluation runs in the background. The response returns immediately
    with a confirmation message.

    Returns:
    - message: Confirmation that evaluation has been triggered
    - note: Information about background execution
    """
    try:
        from ai.corruption.alerts.corruption_alerter import CorruptionAlerter

        pool = await get_asyncpg_pool()

        # Check active subscription count for the response
        async with pool.acquire() as conn:
            sub_count = await conn.fetchval(
                "SELECT COUNT(*) FROM corruption_alert_subscriptions WHERE active = TRUE"
            )
            last_eval = await conn.fetchval(
                "SELECT value FROM corruption_alert_state WHERE key = 'last_evaluation'"
            )

        if sub_count == 0:
            return {
                "message": "No active subscriptions. Evaluation skipped.",
                "active_subscriptions": 0,
                "last_evaluation": last_eval,
            }

        async def _run_evaluation():
            """Background task to run alert evaluation."""
            try:
                alerter = CorruptionAlerter()
                eval_pool = await get_asyncpg_pool()
                summary = await alerter.evaluate_new_tenders(eval_pool)
                logger.info(
                    f"Alert evaluation complete: {summary['evaluated']} tenders, "
                    f"{summary['alerts_generated']} alerts generated"
                )
            except Exception as exc:
                logger.error(f"Background alert evaluation failed: {exc}")

        background_tasks.add_task(_run_evaluation)

        return {
            "message": "Alert evaluation triggered in background",
            "active_subscriptions": sub_count or 0,
            "last_evaluation": last_eval,
            "note": "Evaluation is running asynchronously. Check /api/corruption/alerts/stats for results.",
        }

    except Exception as e:
        logger.error(f"Error triggering alert evaluation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger alert evaluation: {str(e)}"
        )


@router.get("/alerts/stats", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_alert_stats(
    user_id: Optional[str] = Query(None, description="User ID for user-scoped stats. Omit for global stats."),
):
    """
    Get corruption alert statistics.

    Query Parameters:
    - user_id (str, optional): If provided, returns stats scoped to this user.
      If omitted, returns global alert statistics.

    Returns:
    - total_alerts: Total alert count
    - unread_count: Unread alert count
    - by_severity: Breakdown by severity level
    - by_rule_type: Breakdown by rule type
    - recent_24h: Alerts in last 24 hours
    - recent_7d: Alerts in last 7 days
    - subscriptions_count: Active subscription count
    - last_evaluation: Timestamp of last alert evaluation run
    """
    try:
        from ai.corruption.alerts.corruption_alerter import CorruptionAlerter

        alerter = CorruptionAlerter()
        pool = await get_asyncpg_pool()
        stats = await alerter.get_stats(pool, user_id=user_id)
        return stats

    except Exception as e:
        logger.error(f"Error fetching alert stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alert statistics: {str(e)}"
        )


# ============================================================================
# PHASE 4.1: RELATIONSHIP GRAPH ENDPOINTS
# ============================================================================


@router.get("/graph/stats", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_graph_stats():
    """
    Get relationship graph summary statistics.

    Returns node count, edge count, edge type breakdown, community count,
    and average degree from the cached unified graph data.
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Edge statistics by type
            edge_stats = await conn.fetch("""
                SELECT
                    edge_type,
                    COUNT(*) AS edge_count,
                    COUNT(DISTINCT source_id) AS unique_sources,
                    COUNT(DISTINCT target_id) AS unique_targets,
                    AVG(weight) AS avg_weight,
                    SUM(tender_count) AS total_tenders,
                    SUM(total_value) AS total_value
                FROM unified_edges
                GROUP BY edge_type
                ORDER BY edge_count DESC
            """)

            # Node statistics from centrality cache
            node_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS node_count,
                    COUNT(DISTINCT community_id) AS community_count,
                    AVG(degree) AS avg_degree,
                    MAX(degree) AS max_degree,
                    AVG(pagerank) AS avg_pagerank,
                    MAX(pagerank) AS max_pagerank,
                    AVG(betweenness) AS avg_betweenness,
                    MAX(betweenness) AS max_betweenness
                FROM entity_centrality_cache
            """)

            # Node type breakdown
            node_type_rows = await conn.fetch("""
                SELECT entity_type, COUNT(*) AS count
                FROM entity_centrality_cache
                GROUP BY entity_type
                ORDER BY count DESC
            """)

            # Total edge count
            total_edges_row = await conn.fetchrow(
                "SELECT COUNT(*) AS total FROM unified_edges"
            )

            # Build edge type details
            edge_types = {}
            for row in edge_stats:
                edge_types[row["edge_type"]] = {
                    "count": row["edge_count"],
                    "unique_sources": row["unique_sources"],
                    "unique_targets": row["unique_targets"],
                    "avg_weight": round(float(row["avg_weight"] or 0), 4),
                    "total_tenders": row["total_tenders"] or 0,
                    "total_value": float(row["total_value"] or 0),
                }

            # Build node type breakdown
            node_types = {}
            for row in node_type_rows:
                node_types[row["entity_type"]] = row["count"]

            return {
                "node_count": node_stats["node_count"] if node_stats else 0,
                "edge_count": total_edges_row["total"] if total_edges_row else 0,
                "edge_types": edge_types,
                "node_types": node_types,
                "communities": node_stats["community_count"] if node_stats else 0,
                "avg_degree": round(float(node_stats["avg_degree"] or 0), 2) if node_stats else 0,
                "max_degree": node_stats["max_degree"] if node_stats else 0,
                "avg_pagerank": round(float(node_stats["avg_pagerank"] or 0), 8) if node_stats else 0,
                "max_pagerank": round(float(node_stats["max_pagerank"] or 0), 8) if node_stats else 0,
                "avg_betweenness": round(float(node_stats["avg_betweenness"] or 0), 8) if node_stats else 0,
                "max_betweenness": round(float(node_stats["max_betweenness"] or 0), 8) if node_stats else 0,
            }

    except Exception as e:
        logger.error(f"Error fetching graph stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph stats: {str(e)}"
        )


@router.get("/graph/entity/{entity_id}/neighborhood", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_entity_neighborhood(
    entity_id: str,
    hops: int = Query(default=2, ge=1, le=3),
):
    """
    Get the subgraph around an entity within N hops.

    Uses BFS traversal on the unified_edges table to find all connected
    entities within the specified hop distance. Each node is enriched with
    centrality metrics from the cache.

    Parameters:
    - entity_id: The central entity identifier (company or institution name)
    - hops: Number of hops to traverse (1-3, default 2)
    """
    import json as _json

    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # BFS traversal using iterative frontier expansion
            visited = {entity_id: 0}  # entity_id -> depth
            frontier = {entity_id}

            for depth in range(1, hops + 1):
                if not frontier:
                    break

                # Find all neighbors of the current frontier
                neighbors_rows = await conn.fetch("""
                    SELECT DISTINCT
                        CASE
                            WHEN source_id = ANY($1::text[]) THEN target_id
                            ELSE source_id
                        END AS neighbor,
                        CASE
                            WHEN source_id = ANY($1::text[]) THEN target_type
                            ELSE source_type
                        END AS neighbor_type
                    FROM unified_edges
                    WHERE source_id = ANY($1::text[]) OR target_id = ANY($1::text[])
                """, list(frontier))

                next_frontier = set()
                for row in neighbors_rows:
                    neighbor = row["neighbor"]
                    if neighbor not in visited:
                        visited[neighbor] = depth
                        next_frontier.add(neighbor)

                frontier = next_frontier

            # Build node list enriched with centrality data
            node_ids = list(visited.keys())
            nodes = []

            if node_ids:
                centrality_rows = await conn.fetch("""
                    SELECT entity_id, entity_type, pagerank, betweenness, degree, community_id
                    FROM entity_centrality_cache
                    WHERE entity_id = ANY($1::text[])
                """, node_ids)

                centrality_map = {}
                for row in centrality_rows:
                    centrality_map[row["entity_id"]] = {
                        "type": row["entity_type"],
                        "pagerank": round(float(row["pagerank"] or 0), 6),
                        "betweenness": round(float(row["betweenness"] or 0), 6),
                        "degree": row["degree"] or 0,
                        "community_id": row["community_id"],
                    }

                for node_id, depth in visited.items():
                    centrality = centrality_map.get(node_id, {})
                    nodes.append({
                        "id": node_id,
                        "type": centrality.get("type", "unknown"),
                        "depth": depth,
                        "pagerank": centrality.get("pagerank", 0),
                        "betweenness": centrality.get("betweenness", 0),
                        "degree": centrality.get("degree", 0),
                        "community_id": centrality.get("community_id"),
                    })

            # Get all edges between nodes in the subgraph
            edges = []
            if node_ids:
                edge_rows = await conn.fetch("""
                    SELECT source_id, source_type, target_id, target_type,
                           edge_type, weight, tender_count, total_value, metadata
                    FROM unified_edges
                    WHERE source_id = ANY($1::text[]) AND target_id = ANY($1::text[])
                """, node_ids)

                for row in edge_rows:
                    metadata = row["metadata"]
                    if isinstance(metadata, str):
                        metadata = _json.loads(metadata) if metadata else {}
                    elif metadata is None:
                        metadata = {}

                    edges.append({
                        "source": row["source_id"],
                        "source_type": row["source_type"],
                        "target": row["target_id"],
                        "target_type": row["target_type"],
                        "edge_type": row["edge_type"],
                        "weight": float(row["weight"] or 0),
                        "tender_count": row["tender_count"] or 0,
                        "total_value": float(row["total_value"] or 0),
                        "metadata": metadata,
                    })

            return {
                "center": entity_id,
                "hops": hops,
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges),
            }

    except Exception as e:
        logger.error(f"Error fetching neighborhood for {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch entity neighborhood: {str(e)}"
        )


@router.get("/graph/entity/{entity_id}/connections", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_entity_connections(entity_id: str):
    """
    Get all direct connections for an entity.

    Returns a list of connected entities with edge types, weights,
    relationship metadata, and centrality metrics.

    Parameters:
    - entity_id: The entity identifier (company or institution name)
    """
    import json as _json

    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Get all edges involving this entity
            rows = await conn.fetch("""
                SELECT source_id, source_type, target_id, target_type,
                       edge_type, weight, tender_count, total_value, metadata
                FROM unified_edges
                WHERE source_id = $1 OR target_id = $1
                ORDER BY weight DESC
            """, entity_id)

            # Group by connected entity
            connections = {}
            for row in rows:
                if row["source_id"] == entity_id:
                    other_id = row["target_id"]
                    other_type = row["target_type"]
                    direction = "outgoing"
                else:
                    other_id = row["source_id"]
                    other_type = row["source_type"]
                    direction = "incoming"

                metadata = row["metadata"]
                if isinstance(metadata, str):
                    metadata = _json.loads(metadata) if metadata else {}
                elif metadata is None:
                    metadata = {}

                edge_info = {
                    "edge_type": row["edge_type"],
                    "weight": float(row["weight"] or 0),
                    "tender_count": row["tender_count"] or 0,
                    "total_value": float(row["total_value"] or 0),
                    "direction": direction,
                    "metadata": metadata,
                }

                if other_id not in connections:
                    connections[other_id] = {
                        "connected_entity": other_id,
                        "connected_entity_type": other_type,
                        "edges": [],
                        "total_weight": 0,
                    }

                connections[other_id]["edges"].append(edge_info)
                connections[other_id]["total_weight"] += float(row["weight"] or 0)

            # Enrich connected entities with centrality data
            connected_ids = list(connections.keys())
            if connected_ids:
                centrality_rows = await conn.fetch("""
                    SELECT entity_id, pagerank, betweenness, degree, community_id
                    FROM entity_centrality_cache
                    WHERE entity_id = ANY($1::text[])
                """, connected_ids)

                centrality_map = {
                    row["entity_id"]: {
                        "pagerank": round(float(row["pagerank"] or 0), 6),
                        "betweenness": round(float(row["betweenness"] or 0), 6),
                        "degree": row["degree"] or 0,
                        "community_id": row["community_id"],
                    }
                    for row in centrality_rows
                }

                for other_id, conn_info in connections.items():
                    c = centrality_map.get(other_id, {})
                    conn_info["pagerank"] = c.get("pagerank", 0)
                    conn_info["betweenness"] = c.get("betweenness", 0)
                    conn_info["degree"] = c.get("degree", 0)
                    conn_info["community_id"] = c.get("community_id")

            # Get the entity's own centrality
            entity_centrality = await conn.fetchrow("""
                SELECT entity_type, pagerank, betweenness, degree, community_id
                FROM entity_centrality_cache
                WHERE entity_id = $1
            """, entity_id)

            entity_info = {}
            if entity_centrality:
                entity_info = {
                    "entity_type": entity_centrality["entity_type"],
                    "pagerank": round(float(entity_centrality["pagerank"] or 0), 6),
                    "betweenness": round(float(entity_centrality["betweenness"] or 0), 6),
                    "degree": entity_centrality["degree"] or 0,
                    "community_id": entity_centrality["community_id"],
                }

            # Sort connections by total weight descending
            sorted_connections = sorted(
                connections.values(),
                key=lambda c: c["total_weight"],
                reverse=True,
            )

            return {
                "entity_id": entity_id,
                "entity_info": entity_info,
                "connections": sorted_connections,
                "total_connections": len(sorted_connections),
            }

    except Exception as e:
        logger.error(f"Error fetching connections for {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch entity connections: {str(e)}"
        )


@router.get("/graph/path/{source_id}/{target_id}", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_shortest_path(source_id: str, target_id: str):
    """
    Find the shortest path between two entities in the relationship graph.

    Loads the unified_edges into an in-memory graph and computes the shortest
    path using Dijkstra's algorithm with inverse weight (stronger connections
    = shorter distance).

    Parameters:
    - source_id: Starting entity identifier
    - target_id: Destination entity identifier
    """
    import json as _json

    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Verify both entities exist in the graph
            source_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM unified_edges WHERE source_id = $1 OR target_id = $1)",
                source_id,
            )
            target_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM unified_edges WHERE source_id = $1 OR target_id = $1)",
                target_id,
            )

            if not source_exists or not target_exists:
                return {
                    "found": False,
                    "source": source_id,
                    "target": target_id,
                    "path": [],
                    "edges": [],
                    "hop_count": 0,
                    "error": "One or both entities not found in the graph",
                }

            # Load all edges for in-memory path computation
            edge_rows = await conn.fetch("""
                SELECT source_id, source_type, target_id, target_type,
                       edge_type, weight, tender_count, total_value, metadata
                FROM unified_edges
            """)

            if not edge_rows:
                return {
                    "found": False,
                    "source": source_id,
                    "target": target_id,
                    "path": [],
                    "edges": [],
                    "hop_count": 0,
                    "error": "Graph is empty",
                }

            # Build edge list for RelationshipGraph
            edges = []
            for row in edge_rows:
                metadata = row["metadata"]
                if isinstance(metadata, str):
                    metadata = _json.loads(metadata) if metadata else {}
                elif metadata is None:
                    metadata = {}

                edges.append({
                    "source_id": row["source_id"],
                    "source_type": row["source_type"],
                    "target_id": row["target_id"],
                    "target_type": row["target_type"],
                    "edge_type": row["edge_type"],
                    "weight": float(row["weight"] or 1.0),
                    "tender_count": row["tender_count"] or 0,
                    "total_value": float(row["total_value"] or 0),
                    "metadata": metadata,
                })

            # Build in-memory graph and compute shortest path
            try:
                from ai.corruption.graph.relationship_graph import RelationshipGraph
            except ImportError:
                import sys as _sys
                from pathlib import Path as _Path
                _ai_path = str(_Path(__file__).parent.parent.parent / "ai" / "corruption")
                if _ai_path not in _sys.path:
                    _sys.path.insert(0, _ai_path)
                from graph.relationship_graph import RelationshipGraph

            graph = RelationshipGraph(edges)
            path_result = graph.shortest_path(source_id, target_id)

            # Enrich path nodes with centrality data
            if path_result["found"] and path_result["path"]:
                path_nodes = path_result["path"]
                centrality_rows = await conn.fetch("""
                    SELECT entity_id, entity_type, pagerank, betweenness, degree
                    FROM entity_centrality_cache
                    WHERE entity_id = ANY($1::text[])
                """, path_nodes)

                centrality_map = {
                    row["entity_id"]: row for row in centrality_rows
                }
                node_details = []
                for node_id in path_nodes:
                    crow = centrality_map.get(node_id)
                    if crow:
                        node_details.append({
                            "id": node_id,
                            "type": crow["entity_type"],
                            "pagerank": round(float(crow["pagerank"] or 0), 6),
                            "betweenness": round(float(crow["betweenness"] or 0), 6),
                            "degree": crow["degree"] or 0,
                        })
                    else:
                        node_details.append({
                            "id": node_id,
                            "type": "unknown",
                            "pagerank": 0,
                            "betweenness": 0,
                            "degree": 0,
                        })

                path_result["path_details"] = node_details

            path_result["source"] = source_id
            path_result["target"] = target_id
            return path_result

    except Exception as e:
        logger.error(f"Error finding path from {source_id} to {target_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find shortest path: {str(e)}"
        )


@router.get("/graph/gatekeepers", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_gatekeepers(
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get entities with highest betweenness centrality (network gatekeepers).

    Gatekeepers are entities that bridge different parts of the procurement
    network. High betweenness centrality indicates an entity that controls
    information or transaction flow between otherwise disconnected groups.

    Parameters:
    - limit: Maximum number of gatekeepers to return (1-100, default 20)
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    ec.entity_id,
                    ec.entity_type,
                    ec.entity_name,
                    ec.pagerank,
                    ec.betweenness,
                    ec.degree,
                    ec.in_degree,
                    ec.out_degree,
                    ec.community_id,
                    ec.updated_at,
                    (SELECT COUNT(*) FROM unified_edges
                     WHERE source_id = ec.entity_id
                        OR target_id = ec.entity_id
                    ) AS total_edges,
                    (SELECT COUNT(DISTINCT edge_type) FROM unified_edges
                     WHERE source_id = ec.entity_id
                        OR target_id = ec.entity_id
                    ) AS edge_type_diversity
                FROM entity_centrality_cache ec
                WHERE ec.betweenness > 0
                ORDER BY ec.betweenness DESC
                LIMIT $1
            """, limit)

            gatekeepers = []
            for row in rows:
                gatekeepers.append({
                    "entity_id": row["entity_id"],
                    "entity_type": row["entity_type"],
                    "entity_name": row["entity_name"],
                    "betweenness": round(float(row["betweenness"] or 0), 6),
                    "pagerank": round(float(row["pagerank"] or 0), 6),
                    "degree": row["degree"] or 0,
                    "in_degree": row["in_degree"] or 0,
                    "out_degree": row["out_degree"] or 0,
                    "community_id": row["community_id"],
                    "total_edges": row["total_edges"] or 0,
                    "edge_type_diversity": row["edge_type_diversity"] or 0,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                })

            return {
                "gatekeepers": gatekeepers,
                "total": len(gatekeepers),
                "description": (
                    "Entities with highest betweenness centrality "
                    "-- network bridges/gatekeepers"
                ),
            }

    except Exception as e:
        logger.error(f"Error fetching gatekeepers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch gatekeepers: {str(e)}"
        )


@router.get("/graph/revolving-doors", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_revolving_doors(
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Detect entities appearing on both buyer and supplier sides.

    "Revolving door" entities appear as both the source (buyer/institution)
    and target (supplier/company) in buyer_supplier edges. This can indicate
    conflicts of interest or entities operating on both sides of procurement.

    Parameters:
    - limit: Maximum number of results to return (1-100, default 20)
    """
    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                WITH buyers AS (
                    SELECT
                        source_id AS entity_id,
                        COUNT(*) AS buyer_edge_count,
                        SUM(total_value) AS buyer_total_value,
                        SUM(tender_count) AS buyer_tender_count
                    FROM unified_edges
                    WHERE edge_type = 'buyer_supplier'
                    GROUP BY source_id
                ),
                suppliers AS (
                    SELECT
                        target_id AS entity_id,
                        COUNT(*) AS supplier_edge_count,
                        SUM(total_value) AS supplier_total_value,
                        SUM(tender_count) AS supplier_tender_count
                    FROM unified_edges
                    WHERE edge_type = 'buyer_supplier'
                    GROUP BY target_id
                )
                SELECT
                    b.entity_id,
                    b.buyer_edge_count,
                    b.buyer_total_value,
                    b.buyer_tender_count,
                    s.supplier_edge_count,
                    s.supplier_total_value,
                    s.supplier_tender_count,
                    COALESCE(ec.entity_type, 'unknown') AS entity_type,
                    COALESCE(ec.pagerank, 0) AS pagerank,
                    COALESCE(ec.betweenness, 0) AS betweenness,
                    COALESCE(ec.degree, 0) AS degree,
                    ec.community_id
                FROM buyers b
                JOIN suppliers s ON b.entity_id = s.entity_id
                LEFT JOIN entity_centrality_cache ec
                    ON ec.entity_id = b.entity_id
                ORDER BY (b.buyer_edge_count + s.supplier_edge_count) DESC
                LIMIT $1
            """, limit)

            revolving_doors = []
            for row in rows:
                revolving_doors.append({
                    "entity_id": row["entity_id"],
                    "entity_type": row["entity_type"],
                    "buyer_edge_count": row["buyer_edge_count"],
                    "buyer_total_value": float(row["buyer_total_value"] or 0),
                    "buyer_tender_count": row["buyer_tender_count"] or 0,
                    "supplier_edge_count": row["supplier_edge_count"],
                    "supplier_total_value": float(row["supplier_total_value"] or 0),
                    "supplier_tender_count": row["supplier_tender_count"] or 0,
                    "combined_edge_count": (
                        row["buyer_edge_count"] + row["supplier_edge_count"]
                    ),
                    "pagerank": round(float(row["pagerank"] or 0), 6),
                    "betweenness": round(float(row["betweenness"] or 0), 6),
                    "degree": row["degree"] or 0,
                    "community_id": row["community_id"],
                    "risk_indicator": (
                        "Entity appears as both buyer and supplier "
                        "in procurement network"
                    ),
                })

            return {
                "revolving_doors": revolving_doors,
                "total": len(revolving_doors),
                "description": (
                    "Entities appearing on both buyer and supplier "
                    "sides of procurement relationships"
                ),
            }

    except Exception as e:
        logger.error(f"Error detecting revolving doors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect revolving doors: {str(e)}"
        )


@router.get("/graph/clusters", dependencies=[Depends(require_module(ModuleName.RISK_ANALYSIS))])
async def get_graph_clusters(
    min_size: int = Query(default=3, ge=2, le=50),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Get detected communities/clusters in the relationship graph.

    Returns clusters from the precomputed community detection results
    stored in entity_centrality_cache. Clusters with fewer members
    than min_size are excluded.

    Parameters:
    - min_size: Minimum members for a cluster (2-50, default 3)
    - limit: Maximum clusters to return (1-200, default 50)
    """
    import json as _json

    try:
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # Get community membership
            community_rows = await conn.fetch("""
                SELECT
                    community_id,
                    entity_id,
                    entity_type,
                    entity_name,
                    pagerank,
                    betweenness,
                    degree
                FROM entity_centrality_cache
                WHERE community_id IS NOT NULL
                ORDER BY community_id, pagerank DESC
            """)

            # Group by community
            communities = {}
            for row in community_rows:
                cid = row["community_id"]
                if cid not in communities:
                    communities[cid] = {
                        "community_id": cid,
                        "members": [],
                        "total_pagerank": 0,
                        "total_betweenness": 0,
                        "total_degree": 0,
                    }

                communities[cid]["members"].append({
                    "entity_id": row["entity_id"],
                    "entity_type": row["entity_type"],
                    "entity_name": row["entity_name"],
                    "pagerank": round(float(row["pagerank"] or 0), 6),
                    "betweenness": round(float(row["betweenness"] or 0), 6),
                    "degree": row["degree"] or 0,
                })
                communities[cid]["total_pagerank"] += float(
                    row["pagerank"] or 0
                )
                communities[cid]["total_betweenness"] += float(
                    row["betweenness"] or 0
                )
                communities[cid]["total_degree"] += (row["degree"] or 0)

            # Filter by min_size and build response
            clusters = []
            for cid, data in communities.items():
                member_count = len(data["members"])
                if member_count < min_size:
                    continue

                # Entity type breakdown
                type_counts = {}
                for m in data["members"]:
                    t = m["entity_type"]
                    type_counts[t] = type_counts.get(t, 0) + 1

                # Internal edges for this cluster
                member_ids = [m["entity_id"] for m in data["members"]]
                internal_edge_rows = await conn.fetch("""
                    SELECT edge_type,
                           COUNT(*) AS cnt,
                           SUM(weight) AS total_weight,
                           SUM(total_value) AS total_value
                    FROM unified_edges
                    WHERE source_id = ANY($1::text[])
                      AND target_id = ANY($1::text[])
                    GROUP BY edge_type
                """, member_ids)

                edge_type_summary = {}
                total_internal_edges = 0
                for erow in internal_edge_rows:
                    edge_type_summary[erow["edge_type"]] = {
                        "count": erow["cnt"],
                        "total_weight": round(
                            float(erow["total_weight"] or 0), 2
                        ),
                        "total_value": float(erow["total_value"] or 0),
                    }
                    total_internal_edges += erow["cnt"]

                # Cluster density
                max_edges = member_count * (member_count - 1) / 2
                density = (
                    total_internal_edges / max_edges if max_edges > 0 else 0
                )

                clusters.append({
                    "community_id": cid,
                    "member_count": member_count,
                    "members": data["members"][:20],
                    "total_members": member_count,
                    "entity_type_breakdown": type_counts,
                    "internal_edges": total_internal_edges,
                    "edge_type_summary": edge_type_summary,
                    "density": round(density, 4),
                    "avg_pagerank": round(
                        data["total_pagerank"] / member_count, 8
                    ),
                    "avg_betweenness": round(
                        data["total_betweenness"] / member_count, 8
                    ),
                    "avg_degree": round(
                        data["total_degree"] / member_count, 2
                    ),
                })

            # Sort by member count descending
            clusters.sort(key=lambda c: c["member_count"], reverse=True)
            clusters = clusters[:limit]

            return {
                "clusters": clusters,
                "total": len(clusters),
                "min_size_filter": min_size,
                "description": (
                    "Detected communities/clusters in the "
                    "procurement relationship graph"
                ),
            }

    except Exception as e:
        logger.error(f"Error fetching graph clusters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph clusters: {str(e)}"
        )
