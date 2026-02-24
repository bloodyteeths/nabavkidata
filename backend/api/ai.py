"""
AI API endpoints
CPV suggestions, requirement extraction, competitor analysis
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import os
import sys
import logging
import time
import asyncio

logger = logging.getLogger(__name__)

# Simple in-memory cache for company analysis
_company_cache: Dict[str, Any] = {}
_company_cache_times: Dict[str, float] = {}
COMPANY_CACHE_TTL = 300  # 5 minutes

def get_company_cached(company_name: str):
    """Get cached company analysis if not expired"""
    key = company_name.lower().strip()
    if key in _company_cache and time.time() - _company_cache_times.get(key, 0) < COMPANY_CACHE_TTL:
        return _company_cache[key]
    return None

def set_company_cached(company_name: str, value: Any):
    """Cache company analysis"""
    key = company_name.lower().strip()
    _company_cache[key] = value
    _company_cache_times[key] = time.time()

# Add backend path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.timezone import now_mk, today_mk, get_ai_date_context

# Add AI module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

from database import get_db
from models import Tender, TenderBidder, Supplier, User
from api.auth import get_current_user
from middleware.entitlements import require_module
from config.plans import ModuleName

router = APIRouter(prefix="/ai", tags=["ai"])

# Import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
except ImportError:
    GEMINI_AVAILABLE = False
    GEMINI_MODEL = 'gemini-2.0-flash'


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class CPVSuggestRequest(BaseModel):
    """Request for CPV code suggestions"""
    description: str
    title: Optional[str] = None
    category: Optional[str] = None
    limit: int = 5


class CPVSuggestion(BaseModel):
    """Single CPV suggestion"""
    cpv_code: str
    cpv_name: str
    confidence: float
    reason: str


class CPVSuggestResponse(BaseModel):
    """Response with CPV suggestions"""
    suggestions: List[CPVSuggestion]
    input_description: str


class ExtractRequirementsRequest(BaseModel):
    """Request for requirements extraction"""
    document_text: str
    tender_id: Optional[str] = None


class ExtractedRequirement(BaseModel):
    """Single extracted requirement"""
    requirement: str
    category: str  # technical, financial, legal, deadline, qualification
    importance: str  # mandatory, recommended, optional
    source_text: Optional[str] = None


class ExtractRequirementsResponse(BaseModel):
    """Response with extracted requirements"""
    requirements: List[ExtractedRequirement]
    total_found: int
    categories: dict


class CompetitorSummaryRequest(BaseModel):
    """Request for competitor summary"""
    tender_id: Optional[str] = None
    cpv_code: Optional[str] = None
    procuring_entity: Optional[str] = None
    limit: int = 10


class CompetitorInfo(BaseModel):
    """Single competitor info"""
    company_name: str
    tax_id: Optional[str] = None
    total_bids: int
    total_wins: int
    win_rate: float
    total_contract_value_mkd: Optional[float] = None
    avg_bid_discount: Optional[float] = None
    common_categories: List[str]


class CompetitorSummaryResponse(BaseModel):
    """Response with competitor summary"""
    competitors: List[CompetitorInfo]
    total_found: int
    market_summary: dict


# ============================================================================
# CPV CODE SUGGESTIONS
# ============================================================================

# Common CPV codes for Macedonian procurement
CPV_CODES_MK = {
    "33000000": "Medical equipment, pharmaceuticals and personal care products",
    "33100000": "Medical equipment",
    "33140000": "Medical consumables",
    "33600000": "Pharmaceutical products",
    "45000000": "Construction work",
    "45200000": "Works for complete or part construction",
    "45300000": "Building installation work",
    "45400000": "Building completion work",
    "50000000": "Repair and maintenance services",
    "50100000": "Repair and maintenance of vehicles",
    "50700000": "Repair and maintenance services of building installations",
    "60000000": "Transport services",
    "60100000": "Road transport services",
    "60400000": "Air transport services",
    "66000000": "Financial and insurance services",
    "66100000": "Banking services",
    "71000000": "Architectural and engineering services",
    "71300000": "Engineering services",
    "72000000": "IT services",
    "72200000": "Software programming",
    "72400000": "Internet services",
    "79000000": "Business services",
    "79100000": "Legal services",
    "79200000": "Accounting services",
    "79300000": "Market research",
    "79400000": "Consulting services",
    "79500000": "Office support services",
    "79600000": "Recruitment services",
    "79700000": "Investigation and security services",
    "80000000": "Education and training services",
    "85000000": "Health and social work services",
    "90000000": "Sewage and refuse disposal services",
    "92000000": "Recreational, cultural and sporting services",
    "98000000": "Other community and personal services",
    "09000000": "Petroleum products, fuel and electricity",
    "14000000": "Mining products",
    "15000000": "Food and beverages",
    "18000000": "Clothing and footwear",
    "22000000": "Printed matter",
    "30000000": "Office equipment",
    "31000000": "Electrical machinery",
    "32000000": "Radio and communication equipment",
    "34000000": "Transport equipment",
    "38000000": "Laboratory equipment",
    "39000000": "Furniture",
    "42000000": "Industrial machinery",
    "44000000": "Construction structures and materials",
    "48000000": "Software packages",
}


@router.post("/cpv-suggest", response_model=CPVSuggestResponse,
             dependencies=[Depends(require_module(ModuleName.RAG_SEARCH))])
async def suggest_cpv_codes(
    request: CPVSuggestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Suggest CPV codes based on tender description

    Uses AI to analyze description and suggest relevant CPV codes.
    Falls back to keyword matching if AI is unavailable.
    """
    if not request.description or len(request.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Description must be at least 10 characters"
        )

    suggestions = []

    # Try AI-based suggestion first
    if GEMINI_AVAILABLE:
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)

            prompt = f"""Analyze this procurement tender description and suggest the most relevant CPV (Common Procurement Vocabulary) codes.

Description: {request.description}
{f'Title: {request.title}' if request.title else ''}
{f'Category: {request.category}' if request.category else ''}

Return a JSON array of suggestions with this format:
[
  {{"cpv_code": "XXXXXXXX", "cpv_name": "Name in English", "confidence": 0.9, "reason": "Why this code fits"}}
]

Return up to {request.limit} suggestions, ordered by relevance.
Only include codes you're confident about (confidence > 0.5).
Use 8-digit CPV codes (main category level).
"""

            # Relaxed safety settings for business content
            response = model.generate_content(prompt)
            try:
                response_text = response.text
            except ValueError:
                response_text = "[]"

            # Parse JSON from response
            import json
            import re

            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                for item in parsed[:request.limit]:
                    suggestions.append(CPVSuggestion(
                        cpv_code=item.get('cpv_code', ''),
                        cpv_name=item.get('cpv_name', ''),
                        confidence=float(item.get('confidence', 0.5)),
                        reason=item.get('reason', '')
                    ))

        except Exception as e:
            print(f"AI CPV suggestion failed: {e}")
            # Fall through to keyword matching

    # Fallback: keyword-based matching
    if not suggestions:
        description_lower = request.description.lower()

        # Macedonian keyword mappings
        keyword_cpv_map = {
            ("медицин", "лек", "здравств", "болница"): "33000000",
            ("градеж", "изградба", "реконструк", "ремонт"): "45000000",
            ("превоз", "транспорт", "возил"): "60000000",
            ("софтвер", "информа", "систем", "компјутер"): "72000000",
            ("храна", "прехран", "намирниц"): "15000000",
            ("канцелари", "мебел", "опрема"): "39000000",
            ("обезбедув", "чување", "безбедност"): "79700000",
            ("чистење", "хигиен", "отпад"): "90000000",
            ("обука", "едукац", "семинар"): "80000000",
            ("правн", "адвокат", "застап"): "79100000",
            ("консулт", "совет", "експерт"): "79400000",
            ("осигур", "полис"): "66000000",
            ("гориво", "нафта", "бензин"): "09000000",
        }

        for keywords, cpv_code in keyword_cpv_map.items():
            if any(kw in description_lower for kw in keywords):
                cpv_name = CPV_CODES_MK.get(cpv_code, "Unknown")
                matched_keyword = next((kw for kw in keywords if kw in description_lower), "")
                suggestions.append(CPVSuggestion(
                    cpv_code=cpv_code,
                    cpv_name=cpv_name,
                    confidence=0.6,
                    reason=f"Keyword match: '{matched_keyword}'"
                ))

        # Limit and deduplicate
        seen_codes = set()
        unique_suggestions = []
        for s in suggestions:
            if s.cpv_code not in seen_codes:
                seen_codes.add(s.cpv_code)
                unique_suggestions.append(s)
        suggestions = unique_suggestions[:request.limit]

    return CPVSuggestResponse(
        suggestions=suggestions,
        input_description=request.description[:200]
    )


# ============================================================================
# REQUIREMENTS EXTRACTION
# ============================================================================

@router.post("/extract-requirements", response_model=ExtractRequirementsResponse,
             dependencies=[Depends(require_module(ModuleName.RAG_SEARCH))])
async def extract_requirements(
    request: ExtractRequirementsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extract requirements from tender document text

    Uses AI to identify and categorize requirements from tender documents.
    """
    if not request.document_text or len(request.document_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Document text must be at least 50 characters"
        )

    requirements = []
    categories = {
        "technical": 0,
        "financial": 0,
        "legal": 0,
        "deadline": 0,
        "qualification": 0,
        "other": 0
    }

    if GEMINI_AVAILABLE:
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)

            # Truncate text if too long
            doc_text = request.document_text[:15000]

            prompt = f"""Analyze this tender document and extract all requirements.

Document text:
{doc_text}

Extract requirements and categorize them. Return a JSON array:
[
  {{
    "requirement": "Clear description of the requirement",
    "category": "technical|financial|legal|deadline|qualification|other",
    "importance": "mandatory|recommended|optional",
    "source_text": "Original text snippet (max 100 chars)"
  }}
]

Focus on:
- Technical specifications and standards
- Financial requirements (deposits, guarantees, minimum turnover)
- Legal requirements (licenses, certificates, registrations)
- Deadlines (submission, delivery, validity)
- Qualification criteria (experience, staff, equipment)

Return maximum 20 most important requirements.
"""

            # Relaxed safety settings for business content
            response = model.generate_content(prompt)
            try:
                response_text = response.text
            except ValueError:
                response_text = "[]"

            # Parse JSON from response
            import json
            import re

            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                for item in parsed[:20]:
                    cat = item.get('category', 'other')
                    if cat in categories:
                        categories[cat] += 1
                    else:
                        categories['other'] += 1

                    requirements.append(ExtractedRequirement(
                        requirement=item.get('requirement', ''),
                        category=cat,
                        importance=item.get('importance', 'mandatory'),
                        source_text=item.get('source_text', '')[:100] if item.get('source_text') else None
                    ))

        except Exception as e:
            print(f"AI requirements extraction failed: {e}")
            # Return empty list with error message
            raise HTTPException(
                status_code=503,
                detail=f"Requirements extraction service unavailable: {str(e)}"
            )

    else:
        raise HTTPException(
            status_code=503,
            detail="AI service not available. Configure GEMINI_API_KEY."
        )

    return ExtractRequirementsResponse(
        requirements=requirements,
        total_found=len(requirements),
        categories=categories
    )


# ============================================================================
# COMPETITOR SUMMARY
# ============================================================================

@router.post("/competitor-summary", response_model=CompetitorSummaryResponse,
             dependencies=[Depends(require_module(ModuleName.COMPETITOR_TRACKING))])
async def get_competitor_summary(
    request: CompetitorSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get competitor analysis summary

    Analyzes bidding patterns and competition for specific tender, CPV code, or entity.
    """
    competitors = []
    market_summary = {
        "total_bidders_analyzed": 0,
        "average_win_rate": 0,
        "most_competitive_category": None,
        "total_market_value_mkd": 0
    }

    # Build query based on filters
    if request.tender_id:
        # Get competitors from specific tender
        bidder_query = select(TenderBidder).where(
            TenderBidder.tender_id == request.tender_id
        )
        result = await db.execute(bidder_query)
        bidders = result.scalars().all()

        for bidder in bidders:
            # Look up supplier record
            supplier_query = select(Supplier).where(
                Supplier.company_name.ilike(f"%{bidder.company_name}%")
            )
            result = await db.execute(supplier_query)
            supplier = result.scalar_one_or_none()

            if supplier:
                competitors.append(CompetitorInfo(
                    company_name=supplier.company_name,
                    tax_id=supplier.tax_id,
                    total_bids=supplier.total_bids or 0,
                    total_wins=supplier.total_wins or 0,
                    win_rate=float(supplier.win_rate or 0),
                    total_contract_value_mkd=float(supplier.total_contract_value_mkd) if supplier.total_contract_value_mkd else None,
                    avg_bid_discount=None,
                    common_categories=[]
                ))
            else:
                # Basic info from bidder record
                competitors.append(CompetitorInfo(
                    company_name=bidder.company_name or "Unknown",
                    tax_id=bidder.company_tax_id,
                    total_bids=1,
                    total_wins=1 if bidder.is_winner else 0,
                    win_rate=100.0 if bidder.is_winner else 0.0,
                    total_contract_value_mkd=float(bidder.bid_amount_mkd) if bidder.bid_amount_mkd else None,
                    avg_bid_discount=None,
                    common_categories=[]
                ))

    elif request.cpv_code:
        # Get top competitors by CPV code
        from sqlalchemy import text

        # Query suppliers who bid on tenders with this CPV code
        query = text("""
            SELECT
                s.company_name,
                s.tax_id,
                s.total_bids,
                s.total_wins,
                s.win_rate,
                s.total_contract_value_mkd
            FROM suppliers s
            WHERE s.supplier_id IN (
                SELECT DISTINCT tb.supplier_id
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE t.cpv_code LIKE :cpv_prefix
            )
            ORDER BY s.total_wins DESC NULLS LAST
            LIMIT :limit
        """)

        result = await db.execute(query, {
            "cpv_prefix": f"{request.cpv_code}%",
            "limit": request.limit
        })
        rows = result.fetchall()

        for row in rows:
            competitors.append(CompetitorInfo(
                company_name=row[0],
                tax_id=row[1],
                total_bids=row[2] or 0,
                total_wins=row[3] or 0,
                win_rate=float(row[4] or 0),
                total_contract_value_mkd=float(row[5]) if row[5] else None,
                avg_bid_discount=None,
                common_categories=[]
            ))

    else:
        # Get top suppliers overall
        supplier_query = select(Supplier).order_by(
            Supplier.total_wins.desc().nulls_last()
        ).limit(request.limit)

        result = await db.execute(supplier_query)
        suppliers = result.scalars().all()

        for supplier in suppliers:
            competitors.append(CompetitorInfo(
                company_name=supplier.company_name,
                tax_id=supplier.tax_id,
                total_bids=supplier.total_bids or 0,
                total_wins=supplier.total_wins or 0,
                win_rate=float(supplier.win_rate or 0),
                total_contract_value_mkd=float(supplier.total_contract_value_mkd) if supplier.total_contract_value_mkd else None,
                avg_bid_discount=None,
                common_categories=[]
            ))

    # Calculate market summary
    if competitors:
        market_summary["total_bidders_analyzed"] = len(competitors)
        market_summary["average_win_rate"] = sum(c.win_rate for c in competitors) / len(competitors)
        market_summary["total_market_value_mkd"] = sum(
            c.total_contract_value_mkd or 0 for c in competitors
        )

    return CompetitorSummaryResponse(
        competitors=competitors[:request.limit],
        total_found=len(competitors),
        market_summary=market_summary
    )


# ============================================================================
# HEALTH CHECK
# ============================================================================

# ============================================================================
# RAG CHAT ENDPOINT
# ============================================================================

class ChatRequest(BaseModel):
    """Request for RAG chat"""
    message: str
    tender_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None


class ChatResponse(BaseModel):
    """Response from RAG chat"""
    response: str
    sources: List[dict]
    confidence: str


@router.post("/chat", response_model=ChatResponse,
             dependencies=[Depends(require_module(ModuleName.RAG_SEARCH))])
async def rag_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RAG-based chat for tender questions

    Uses semantic search and SQL fallback to find relevant tenders,
    then generates an AI response based on the context.
    """
    if not request.message or len(request.message.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Message must be at least 3 characters"
        )

    if not GEMINI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AI service not available. Configure GEMINI_API_KEY."
        )

    # Check and consume credits/usage for AI messages
    from api.billing import SUBSCRIPTION_PLANS, use_trial_credit, UseCreditsRequest
    from datetime import datetime
    from sqlalchemy import text

    user_id = str(current_user.user_id) if current_user else None
    tier = current_user.subscription_tier if current_user else "free"

    # Check if user is in trial
    in_trial = False
    if current_user and hasattr(current_user, 'trial_ends_at') and current_user.trial_ends_at:
        if current_user.trial_ends_at > datetime.utcnow():
            in_trial = True

    if in_trial:
        # Check trial credits
        credits_result = await db.execute(
            text("""
                SELECT credit_id, total_credits, used_credits
                FROM trial_credits
                WHERE user_id = :user_id
                  AND credit_type = 'ai_messages'
                  AND expires_at > NOW()
            """),
            {"user_id": user_id}
        )
        credit_row = credits_result.fetchone()

        if credit_row:
            _, total, used = credit_row
            if used >= total:
                raise HTTPException(
                    status_code=402,
                    detail="Ги искористивте сите AI кредити. Надградете го вашиот план."
                )
        else:
            raise HTTPException(
                status_code=402,
                detail="Немате кредити за AI пораки. Надградете го вашиот план."
            )
    else:
        # Check daily limits for non-trial users
        plan = SUBSCRIPTION_PLANS.get(tier, SUBSCRIPTION_PLANS.get("free", {}))
        daily_limit = plan.get("limits", {}).get("rag_queries_per_day", 3)

        if daily_limit != -1:  # -1 means unlimited
            # Count today's usage
            today_usage = await db.execute(
                text("""
                    SELECT COUNT(*) FROM usage_tracking
                    WHERE user_id = :user_id
                      AND action_type = 'rag_query'
                      AND created_at >= CURRENT_DATE
                """),
                {"user_id": user_id}
            )
            current_count = today_usage.scalar() or 0

            if current_count >= daily_limit:
                raise HTTPException(
                    status_code=402,
                    detail=f"Дневниот лимит од {daily_limit} AI прашања е достигнат. Надградете за повеќе."
                )

    try:
        # Import RAG pipeline
        from rag_query import RAGQueryPipeline

        # Initialize and run RAG query
        pipeline = RAGQueryPipeline()
        answer = await pipeline.generate_answer(
            question=request.message,
            tender_id=request.tender_id,
            conversation_history=request.conversation_history,
            user_id=str(current_user.user_id) if current_user else None
        )

        # Format sources for response
        sources = [
            {
                "tender_id": s.tender_id,
                "doc_id": s.doc_id,
                "similarity": s.similarity,
                "title": s.chunk_metadata.get("tender_title", ""),
                "category": s.chunk_metadata.get("tender_category", "")
            }
            for s in answer.sources[:5]  # Limit to top 5 sources
        ]

        # Consume credit/usage after successful response
        if in_trial:
            await db.execute(
                text("""
                    UPDATE trial_credits
                    SET used_credits = used_credits + 1, updated_at = NOW()
                    WHERE user_id = :user_id
                      AND credit_type = 'ai_messages'
                      AND expires_at > NOW()
                """),
                {"user_id": user_id}
            )
            await db.commit()
        else:
            # Track usage for non-trial users
            await db.execute(
                text("""
                    INSERT INTO usage_tracking (user_id, action_type, details, created_at)
                    VALUES (:user_id, 'rag_query', :details, NOW())
                """),
                {"user_id": user_id, "details": f"Question: {request.message[:100]}"}
            )
            await db.commit()

        return ChatResponse(
            response=answer.answer,
            sources=sources,
            confidence=answer.confidence
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}"
        )


# ============================================================================
# COMPANY ANALYSIS - Deep competitor intelligence
# ============================================================================

class CompanyAnalysisRequest(BaseModel):
    """Request for deep company analysis"""
    company_name: str
    include_web_research: bool = True
    include_tender_history: bool = True
    include_specifications: bool = True


class CompanyAnalysisResponse(BaseModel):
    """Comprehensive company analysis response"""
    company_name: str
    summary: str
    tender_stats: dict
    recent_wins: List[dict]
    common_categories: List[dict]
    frequent_institutions: List[dict]
    product_specifications: List[dict]
    ai_insights: str
    analysis_timestamp: str


def normalize_category(category: str) -> str:
    """Normalize category names to Macedonian"""
    if not category:
        return "Непознато"
    cat_lower = category.lower().strip()
    # Map English to Macedonian
    if cat_lower in ('goods', 'стоки'):
        return 'Стоки'
    elif cat_lower in ('services', 'услуги'):
        return 'Услуги'
    elif cat_lower in ('works', 'работи'):
        return 'Работи'
    elif cat_lower in ('unknown', 'непознато', ''):
        return 'Непознато'
    return category  # Return as-is if not recognized


@router.post("/company-analysis", response_model=CompanyAnalysisResponse,
             dependencies=[Depends(require_module(ModuleName.RAG_SEARCH))])
async def analyze_company(
    request: CompanyAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deep AI-powered company analysis for competitor intelligence.
    Optimized with caching and combined queries for fast response.
    """
    company_name = request.company_name.strip()
    if not company_name or len(company_name) < 3:
        raise HTTPException(
            status_code=400,
            detail="Company name must be at least 3 characters"
        )

    # Check cache first
    cached = get_company_cached(company_name)
    if cached:
        return cached

    search_pattern = f"%{company_name}%"

    # Single optimized query combining all data needs
    combined_query = text("""
        WITH company_stats AS (
            -- Get stats from suppliers table (pre-calculated, fast)
            SELECT
                company_name,
                total_bids,
                total_wins,
                win_rate,
                total_contract_value_mkd
            FROM suppliers
            WHERE company_name ILIKE :search_pattern
            ORDER BY total_wins DESC
            LIMIT 1
        ),
        bidder_dates AS (
            -- Get date range from tender_bidders (only if needed)
            SELECT
                MIN(t.closing_date) as first_bid_date,
                MAX(t.closing_date) as last_bid_date
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE tb.company_name ILIKE :search_pattern
        )
        SELECT
            cs.company_name,
            cs.total_bids,
            cs.total_wins,
            cs.win_rate,
            cs.total_contract_value_mkd,
            bd.first_bid_date,
            bd.last_bid_date
        FROM company_stats cs
        CROSS JOIN bidder_dates bd
    """)

    # Recent wins query (optimized with index hint via ORDER BY)
    wins_query = text("""
        SELECT
            t.tender_id,
            t.title,
            t.procuring_entity,
            t.category,
            t.cpv_code,
            t.actual_value_mkd,
            t.closing_date
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :search_pattern
          AND tb.is_winner = TRUE
        ORDER BY t.closing_date DESC NULLS LAST
        LIMIT 10
    """)

    # Categories query
    categories_query = text("""
        SELECT
            COALESCE(t.category, 'Unknown') as category,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE tb.is_winner) as wins,
            COALESCE(SUM(CASE WHEN tb.is_winner THEN t.actual_value_mkd ELSE 0 END), 0) as won_value
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :search_pattern
        GROUP BY t.category
        ORDER BY count DESC
        LIMIT 10
    """)

    # Institutions query
    institutions_query = text("""
        SELECT
            t.procuring_entity,
            COUNT(*) as bid_count,
            COUNT(*) FILTER (WHERE tb.is_winner) as win_count
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name ILIKE :search_pattern
          AND t.procuring_entity IS NOT NULL
        GROUP BY t.procuring_entity
        ORDER BY win_count DESC, bid_count DESC
        LIMIT 10
    """)

    # Execute all queries in parallel
    stats_task = db.execute(combined_query, {"search_pattern": search_pattern})
    wins_task = db.execute(wins_query, {"search_pattern": search_pattern})
    cats_task = db.execute(categories_query, {"search_pattern": search_pattern})
    insts_task = db.execute(institutions_query, {"search_pattern": search_pattern})

    # Wait for all queries
    stats_result, wins_result, cats_result, insts_result = await asyncio.gather(
        stats_task, wins_task, cats_task, insts_task
    )

    # Process stats
    stats_row = stats_result.fetchone()
    if stats_row and stats_row.total_wins:
        tender_stats = {
            "total_bids": stats_row.total_bids or 0,
            "total_wins": stats_row.total_wins or 0,
            "win_rate": float(stats_row.win_rate) if stats_row.win_rate else 0,
            "avg_bid_value_mkd": None,
            "total_won_value_mkd": float(stats_row.total_contract_value_mkd) if stats_row.total_contract_value_mkd else None,
            "first_bid_date": str(stats_row.first_bid_date) if stats_row.first_bid_date else None,
            "last_bid_date": str(stats_row.last_bid_date) if stats_row.last_bid_date else None
        }
    else:
        tender_stats = {
            "total_bids": 0, "total_wins": 0, "win_rate": 0,
            "avg_bid_value_mkd": None, "total_won_value_mkd": None,
            "first_bid_date": None, "last_bid_date": None
        }

    # Process wins
    recent_wins = [
        {
            "tender_id": row[0],
            "title": row[1][:100] if row[1] else None,
            "procuring_entity": row[2],
            "category": normalize_category(row[3]) if row[3] else None,
            "cpv_code": row[4],
            "contract_value_mkd": float(row[5]) if row[5] else None,
            "date": str(row[6]) if row[6] else None
        }
        for row in wins_result.fetchall()
    ]

    # Process categories
    cat_map = {}
    for row in cats_result.fetchall():
        normalized_cat = normalize_category(row[0])
        if normalized_cat in cat_map:
            cat_map[normalized_cat]["bid_count"] += row[1]
            cat_map[normalized_cat]["win_count"] += row[2]
            cat_map[normalized_cat]["won_value_mkd"] += float(row[3]) if row[3] else 0
        else:
            cat_map[normalized_cat] = {
                "category": normalized_cat,
                "bid_count": row[1],
                "win_count": row[2],
                "won_value_mkd": float(row[3]) if row[3] else 0
            }
    common_categories = sorted(cat_map.values(), key=lambda x: x["bid_count"], reverse=True)

    # Process institutions
    frequent_institutions = [
        {
            "institution": row[0],
            "bid_count": row[1],
            "win_count": row[2],
            "avg_bid_mkd": None
        }
        for row in insts_result.fetchall()
    ]

    # Skip product specs for faster loading (rarely used)
    product_specifications = []

    # Build summary
    if tender_stats["total_bids"] > 0:
        summary = f"Компанијата {company_name} има {tender_stats['total_bids']} понуди со {tender_stats['win_rate']}% стапка на успешност."
        if tender_stats["total_won_value_mkd"]:
            summary += f" Вкупна вредност на договори: {tender_stats['total_won_value_mkd']:,.0f} МКД."
    else:
        summary = f"Не се пронајдени податоци за понуди од {company_name} во базата."

    # Generate detailed data-driven insights (no AI API call)
    ai_insights = ""
    if tender_stats["total_wins"] > 0:
        insights = []

        # Activity period
        if tender_stats.get("first_bid_date") and tender_stats.get("last_bid_date"):
            insights.append(f"Активен од {tender_stats['first_bid_date'][:10]} до {tender_stats['last_bid_date'][:10]}.")

        # Win rate analysis
        win_rate = tender_stats["win_rate"]
        total_wins = tender_stats["total_wins"]
        total_bids = tender_stats["total_bids"]
        if win_rate > 70:
            insights.append(f"Извонредно висока успешност: {total_wins} победи од {total_bids} понуди ({win_rate}%).")
        elif win_rate > 40:
            insights.append(f"Солидна успешност: {total_wins} победи од {total_bids} понуди ({win_rate}%).")
        else:
            insights.append(f"Активно учество: {total_wins} победи од {total_bids} понуди ({win_rate}%).")

        # Category specialization
        if common_categories:
            top_cat = common_categories[0]
            if top_cat["win_count"] > 0:
                cat_win_rate = round(top_cat["win_count"] / top_cat["bid_count"] * 100, 1) if top_cat["bid_count"] > 0 else 0
                insights.append(f"Најсилен во категорија '{top_cat['category']}' со {top_cat['win_count']} победи ({cat_win_rate}% успешност).")

        # Top client
        if frequent_institutions and frequent_institutions[0]["win_count"] > 0:
            top_inst = frequent_institutions[0]
            insights.append(f"Најчест клиент: {top_inst['institution'][:60]} ({top_inst['win_count']} договори).")

        # Contract value
        if tender_stats.get("total_won_value_mkd") and tender_stats["total_won_value_mkd"] > 0:
            avg_contract = tender_stats["total_won_value_mkd"] / max(total_wins, 1)
            if avg_contract > 10_000_000:
                insights.append(f"Просечна вредност на договор: {avg_contract/1_000_000:.1f}M МКД (големи проекти).")
            elif avg_contract > 1_000_000:
                insights.append(f"Просечна вредност на договор: {avg_contract/1_000_000:.1f}M МКД.")
            else:
                insights.append(f"Просечна вредност на договор: {avg_contract:,.0f} МКД.")

        # Recent activity from wins
        if recent_wins:
            recent_institutions = set([w["procuring_entity"] for w in recent_wins[:5] if w.get("procuring_entity")])
            if len(recent_institutions) == 1:
                insights.append(f"Последни победи сите од: {list(recent_institutions)[0][:50]}.")
            elif len(recent_institutions) >= 3:
                insights.append(f"Разновидни клиенти: {len(recent_institutions)} различни институции во последните победи.")

        ai_insights = " ".join(insights)

    response = CompanyAnalysisResponse(
        company_name=company_name,
        summary=summary,
        tender_stats=tender_stats,
        recent_wins=recent_wins,
        common_categories=common_categories,
        frequent_institutions=frequent_institutions,
        product_specifications=product_specifications,
        ai_insights=ai_insights,
        analysis_timestamp=now_mk().isoformat()
    )

    # Cache the result
    set_company_cached(company_name, response)

    return response


# ============================================================================
# ITEM-LEVEL PRICE RESEARCH
# ============================================================================

class ItemPriceResult(BaseModel):
    """Single item price result"""
    item_name: str
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    tender_id: str
    tender_title: str
    date: Optional[datetime] = None
    source: str  # "epazar", "nabavki", "document"


class ItemPriceSearchResponse(BaseModel):
    """Response with item price search results"""
    query: str
    results: List[ItemPriceResult]
    statistics: dict  # {min_price, max_price, avg_price, median_price, count}


@router.get("/item-prices", response_model=ItemPriceSearchResponse,
            dependencies=[Depends(require_module(ModuleName.DOCUMENT_EXTRACTION))])
async def search_item_prices(
    query: str = Query(..., min_length=3, description="Search term for item (e.g., 'CT Scanner')"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search for item prices across all tenders

    Searches:
    - items_data JSONB in epazar_tenders
    - raw_data_json for item mentions
    - Document content for price mentions

    Returns detailed price statistics for market research.
    """
    from sqlalchemy import text
    import statistics as stats_module

    results = []

    # 1. Search ePazar items_data
    epazar_query = text("""
        SELECT
            item->>'name' as item_name,
            (item->>'unit_price')::float as unit_price,
            (item->>'total_price')::float as total_price,
            (item->>'quantity')::int as quantity,
            item->>'unit' as unit,
            e.tender_id,
            e.title,
            e.publication_date
        FROM epazar_tenders e,
             jsonb_array_elements(items_data) as item
        WHERE (item->>'name' ILIKE :search1
           OR item->>'description' ILIKE :search2)
          AND items_data IS NOT NULL
        ORDER BY e.publication_date DESC NULLS LAST
        LIMIT :limit
    """)

    try:
        epazar_result = await db.execute(epazar_query, {
            "search1": f"%{query}%",
            "search2": f"%{query}%",
            "limit": limit
        })

        for row in epazar_result.fetchall():
            if row[0]:  # item_name exists
                results.append(ItemPriceResult(
                    item_name=row[0],
                    unit_price=float(row[1]) if row[1] else None,
                    total_price=float(row[2]) if row[2] else None,
                    quantity=int(row[3]) if row[3] else None,
                    unit=row[4],
                    tender_id=row[5],
                    tender_title=row[6][:150] if row[6] else "",
                    date=row[7],
                    source="epazar"
                ))
    except Exception as e:
        logger.error(f"ePazar item search failed: {e}")

    # 2. Search product_items table (from document extraction)
    product_items_query = text("""
        SELECT
            pi.name as item_name,
            pi.unit_price as unit_price,
            pi.total_price as total_price,
            pi.quantity::int as quantity,
            pi.unit,
            pi.tender_id,
            t.title,
            t.publication_date
        FROM product_items pi
        JOIN tenders t ON pi.tender_id = t.tender_id
        WHERE pi.name ILIKE :search
          AND pi.unit_price IS NOT NULL
        ORDER BY t.publication_date DESC NULLS LAST
        LIMIT :limit
    """)

    try:
        product_result = await db.execute(product_items_query, {
            "search": f"%{query}%",
            "limit": limit
        })

        for row in product_result.fetchall():
            if row[0]:  # item_name exists
                results.append(ItemPriceResult(
                    item_name=row[0],
                    unit_price=float(row[1]) if row[1] else None,
                    total_price=float(row[2]) if row[2] else None,
                    quantity=int(row[3]) if row[3] else None,
                    unit=row[4],
                    tender_id=row[5],
                    tender_title=row[6][:150] if row[6] else "",
                    date=row[7],
                    source="document"
                ))
    except Exception as e:
        logger.error(f"Product items search failed: {e}")

    # 3. Search raw_data_json from nabavki tenders
    nabavki_query = text("""
        SELECT
            t.tender_id,
            t.title,
            t.publication_date,
            t.raw_data_json
        FROM tenders t
        WHERE t.raw_data_json IS NOT NULL
          AND (
              t.raw_data_json::text ILIKE :search
              OR t.title ILIKE :search
          )
        ORDER BY t.publication_date DESC NULLS LAST
        LIMIT :limit
    """)

    try:
        nabavki_result = await db.execute(nabavki_query, {
            "search": f"%{query}%",
            "limit": limit // 2  # Limit raw JSON searches
        })

        import json
        for row in nabavki_result.fetchall():
            tender_id, title, pub_date, raw_json = row
            if raw_json:
                # Try to extract items from raw_data_json
                # This is tender-specific and may vary
                if isinstance(raw_json, dict):
                    # Check common item fields
                    for key in ['items', 'lots', 'products', 'stavki']:
                        if key in raw_json and isinstance(raw_json[key], list):
                            for item in raw_json[key][:5]:  # Limit items per tender
                                if isinstance(item, dict):
                                    item_name = item.get('name') or item.get('title') or item.get('description', '')
                                    if query.lower() in item_name.lower():
                                        unit_price = None
                                        total_price = None
                                        quantity = None

                                        # Extract price fields
                                        for price_key in ['unit_price', 'unitPrice', 'price', 'cena']:
                                            if price_key in item:
                                                try:
                                                    unit_price = float(item[price_key])
                                                except:
                                                    pass

                                        for total_key in ['total_price', 'totalPrice', 'total', 'vkupno']:
                                            if total_key in item:
                                                try:
                                                    total_price = float(item[total_key])
                                                except:
                                                    pass

                                        for qty_key in ['quantity', 'qty', 'kolicina']:
                                            if qty_key in item:
                                                try:
                                                    quantity = int(item[qty_key])
                                                except:
                                                    pass

                                        if unit_price or total_price:
                                            results.append(ItemPriceResult(
                                                item_name=item_name[:200],
                                                unit_price=unit_price,
                                                total_price=total_price,
                                                quantity=quantity,
                                                unit=item.get('unit') or item.get('merka'),
                                                tender_id=tender_id,
                                                tender_title=title[:150] if title else "",
                                                date=pub_date,
                                                source="nabavki"
                                            ))
    except Exception as e:
        logger.error(f"Nabavki raw JSON search failed: {e}")

    # Sort results by date (newest first)
    results.sort(key=lambda x: x.date if x.date else datetime.min, reverse=True)

    # Limit to requested size
    results = results[:limit]

    # Calculate statistics
    statistics = {
        "count": len(results),
        "min_price": None,
        "max_price": None,
        "avg_price": None,
        "median_price": None
    }

    if results:
        # Collect all unit prices
        unit_prices = [r.unit_price for r in results if r.unit_price and r.unit_price > 0]

        if unit_prices:
            statistics["min_price"] = float(min(unit_prices))
            statistics["max_price"] = float(max(unit_prices))
            statistics["avg_price"] = float(sum(unit_prices) / len(unit_prices))

            # Calculate median
            sorted_prices = sorted(unit_prices)
            n = len(sorted_prices)
            if n % 2 == 0:
                statistics["median_price"] = float((sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2)
            else:
                statistics["median_price"] = float(sorted_prices[n//2])

    return ItemPriceSearchResponse(
        query=query,
        results=results,
        statistics=statistics
    )


@router.get("/health")
async def ai_health_check():
    """
    Check AI service health

    Returns AI service status and configuration
    """
    return {
        "status": "healthy" if GEMINI_AVAILABLE else "degraded",
        "gemini_available": GEMINI_AVAILABLE,
        "gemini_api_key_configured": bool(os.getenv('GEMINI_API_KEY')),
        "service": "ai-api",
        "features": {
            "cpv_suggest": True,  # Always available (fallback to keyword matching)
            "extract_requirements": GEMINI_AVAILABLE,
            "competitor_summary": True,  # Always available (database query)
            "company_analysis": True,  # Deep competitor analysis
            "rag_chat": GEMINI_AVAILABLE,  # RAG-based chat
            "item_price_search": True  # Item-level price research
        }
    }
