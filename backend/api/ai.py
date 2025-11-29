"""
AI API endpoints
CPV suggestions, requirement extraction, competitor analysis
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel
import os
import sys

# Add AI module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

from database import get_db
from models import Tender, TenderBidder, Supplier, User
from api.auth import get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])

# Import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = bool(os.getenv('GEMINI_API_KEY'))
    if GEMINI_AVAILABLE:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
except ImportError:
    GEMINI_AVAILABLE = False


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


@router.post("/cpv-suggest", response_model=CPVSuggestResponse)
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
            model = genai.GenerativeModel('gemini-1.5-flash')

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

            response = model.generate_content(prompt)
            response_text = response.text

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

@router.post("/extract-requirements", response_model=ExtractRequirementsResponse)
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
            model = genai.GenerativeModel('gemini-1.5-flash')

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

            response = model.generate_content(prompt)
            response_text = response.text

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

@router.post("/competitor-summary", response_model=CompetitorSummaryResponse)
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


@router.post("/chat", response_model=ChatResponse)
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
            "rag_chat": GEMINI_AVAILABLE  # RAG-based chat
        }
    }
