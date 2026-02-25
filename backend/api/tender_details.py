"""
Tender Details API endpoints
Extended tender information: bidders, lots, amendments, documents
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

from database import get_db
from models import Tender, User
from middleware.rbac import get_optional_user
from middleware.entitlements import check_price_view_quota
from utils.timezone import get_ai_date_context

router = APIRouter(prefix="/tenders", tags=["tender-details"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class BidderResponse(BaseModel):
    """Bidder information for a tender"""
    bidder_id: str
    company_name: str
    tax_id: Optional[str] = None
    bid_amount_mkd: Optional[Decimal] = None
    bid_amount_eur: Optional[Decimal] = None
    rank: Optional[int] = None
    is_winner: bool = False
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None
    bid_date: Optional[datetime] = None


class BiddersListResponse(BaseModel):
    """List of bidders for a tender"""
    tender_id: str
    total_bidders: int
    winner: Optional[str] = None
    bidders: List[BidderResponse]


class LotResponse(BaseModel):
    """Lot information for a dividable tender"""
    lot_id: str
    lot_number: int
    title: str
    description: Optional[str] = None
    estimated_value_mkd: Optional[Decimal] = None
    actual_value_mkd: Optional[Decimal] = None
    cpv_code: Optional[str] = None
    status: Optional[str] = None
    winner: Optional[str] = None


class LotsListResponse(BaseModel):
    """List of lots for a tender"""
    tender_id: str
    has_lots: bool
    total_lots: int
    lots: List[LotResponse]


class AmendmentResponse(BaseModel):
    """Amendment/modification record"""
    amendment_id: str
    amendment_number: int
    amendment_date: datetime
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None


class AmendmentsListResponse(BaseModel):
    """List of amendments for a tender"""
    tender_id: str
    total_amendments: int
    amendments: List[AmendmentResponse]


class DocumentResponse(BaseModel):
    """Document attached to a tender"""
    doc_id: str
    tender_id: Optional[str] = None
    doc_type: Optional[str] = None
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    extraction_status: str = "pending"
    has_content: bool = False
    uploaded_at: Optional[datetime] = None
    # Legacy field names for backwards compatibility
    document_id: Optional[str] = None
    filename: Optional[str] = None
    download_url: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class DocumentsListResponse(BaseModel):
    """List of documents for a tender"""
    tender_id: str
    total_documents: int
    total: Optional[int] = None  # Alias for frontend compatibility
    documents: List[DocumentResponse]
    documents_by_category: dict


# ============================================================================
# BIDDERS ENDPOINT
# ============================================================================

@router.get("/by-id/{tender_number}/{tender_year}/bidders", response_model=BiddersListResponse)
async def get_tender_bidders(
    tender_number: str,
    tender_year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all bidders/participants for a tender

    Parameters:
    - tender_number: The tender number part (e.g., "21307")
    - tender_year: The tender year part (e.g., "2025")

    Returns:
    - List of all bidders with their bid amounts
    - Winner indication
    - Disqualification status if applicable
    """
    tender_id = f"{tender_number}/{tender_year}"
    # Verify tender exists
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender_row = tender.scalar_one_or_none()
    if not tender_row:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Query bidders from tender_bidders table
    bidders_query = text("""
        SELECT
            bidder_id::text, company_name, company_tax_id,
            bid_amount_mkd, bid_amount_eur,
            rank, is_winner, disqualified,
            disqualification_reason, created_at
        FROM tender_bidders
        WHERE tender_id = :tender_id
        ORDER BY rank NULLS LAST, is_winner DESC
    """)

    result = await db.execute(bidders_query, {"tender_id": tender_id})
    rows = result.fetchall()

    bidders = [
        BidderResponse(
            bidder_id=str(row.bidder_id),
            company_name=row.company_name,
            tax_id=row.company_tax_id,
            bid_amount_mkd=row.bid_amount_mkd,
            bid_amount_eur=row.bid_amount_eur,
            rank=row.rank,
            is_winner=row.is_winner or False,
            is_disqualified=row.disqualified or False,
            disqualification_reason=row.disqualification_reason,
            bid_date=row.created_at
        )
        for row in rows
    ]

    return BiddersListResponse(
        tender_id=tender_id,
        total_bidders=len(bidders),
        winner=tender_row.winner,
        bidders=bidders
    )


# ============================================================================
# LOTS ENDPOINT
# ============================================================================

@router.get("/by-id/{tender_number}/{tender_year}/lots", response_model=LotsListResponse)
async def get_tender_lots(
    tender_number: str,
    tender_year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get lot breakdown for a dividable tender

    Parameters:
    - tender_number: The tender number part (e.g., "21307")
    - tender_year: The tender year part (e.g., "2025")

    Returns:
    - List of all lots with values and status
    - Empty list if tender is not dividable
    """
    tender_id = f"{tender_number}/{tender_year}"
    # Verify tender exists
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender_row = tender.scalar_one_or_none()
    if not tender_row:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Query lots from tender_lots table
    lots_query = text("""
        SELECT
            lot_id::text, lot_number, lot_title, lot_description,
            estimated_value_mkd, actual_value_mkd,
            cpv_code, winner
        FROM tender_lots
        WHERE tender_id = :tender_id
        ORDER BY lot_number
    """)

    result = await db.execute(lots_query, {"tender_id": tender_id})
    rows = result.fetchall()

    lots = [
        LotResponse(
            lot_id=str(row.lot_id),
            lot_number=row.lot_number,
            title=row.lot_title,
            description=row.lot_description,
            estimated_value_mkd=row.estimated_value_mkd,
            actual_value_mkd=row.actual_value_mkd,
            cpv_code=row.cpv_code,
            status=None,  # status column doesn't exist in schema
            winner=row.winner
        )
        for row in rows
    ]

    return LotsListResponse(
        tender_id=tender_id,
        has_lots=tender_row.has_lots or False,
        total_lots=len(lots),
        lots=lots
    )


# ============================================================================
# AMENDMENTS ENDPOINT
# ============================================================================

@router.get("/by-id/{tender_number}/{tender_year}/amendments", response_model=AmendmentsListResponse)
async def get_tender_amendments(
    tender_number: str,
    tender_year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get amendment/modification history for a tender

    Parameters:
    - tender_number: The tender number part (e.g., "21307")
    - tender_year: The tender year part (e.g., "2025")

    Returns:
    - List of all amendments with field changes
    - Chronologically ordered
    """
    tender_id = f"{tender_number}/{tender_year}"
    # Verify tender exists
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender_row = tender.scalar_one_or_none()
    if not tender_row:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Query amendments from tender_amendments table
    amendments_query = text("""
        SELECT
            amendment_id::text, amendment_date, amendment_type,
            field_changed, old_value, new_value, reason
        FROM tender_amendments
        WHERE tender_id = :tender_id
        ORDER BY amendment_date
    """)

    result = await db.execute(amendments_query, {"tender_id": tender_id})
    rows = result.fetchall()

    amendments = [
        AmendmentResponse(
            amendment_id=str(row.amendment_id),
            amendment_number=idx + 1,  # Generate sequential number from result order
            amendment_date=row.amendment_date,
            field_changed=row.field_changed or row.amendment_type or "unknown",
            old_value=row.old_value,
            new_value=row.new_value,
            reason=row.reason
        )
        for idx, row in enumerate(rows)
    ]

    return AmendmentsListResponse(
        tender_id=tender_id,
        total_amendments=len(amendments),
        amendments=amendments
    )


# ============================================================================
# DOCUMENTS ENDPOINT
# ============================================================================

@router.get("/by-id/{tender_number}/{tender_year}/documents", response_model=DocumentsListResponse)
async def get_tender_documents(
    tender_number: str,
    tender_year: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get documents attached to a tender

    Parameters:
    - tender_number: The tender number part (e.g., "21307")
    - tender_year: The tender year part (e.g., "2025")
    - category: Filter by document category (technical_specs, financial_docs, etc.)

    Returns:
    - List of documents with metadata
    - Documents grouped by category
    """
    tender_id = f"{tender_number}/{tender_year}"
    # Verify tender exists
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender_row = tender.scalar_one_or_none()
    if not tender_row:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Build query with optional category filter
    # Actual columns: doc_id, tender_id, doc_type, file_name, file_path, file_url,
    # content_text, extraction_status, file_size_bytes, page_count, mime_type,
    # uploaded_at, doc_category, doc_version, upload_date, file_hash
    if category:
        docs_query = text("""
            SELECT
                doc_id::text, file_name, doc_type, file_size_bytes,
                doc_category, upload_date, file_url, extraction_status,
                page_count, uploaded_at,
                CASE WHEN extraction_status = 'success' AND content_text IS NOT NULL AND LENGTH(content_text) > 100 THEN true ELSE false END as has_content
            FROM documents
            WHERE tender_id = :tender_id AND doc_category = :category
            ORDER BY upload_date DESC
        """)
        result = await db.execute(docs_query, {"tender_id": tender_id, "category": category})
    else:
        docs_query = text("""
            SELECT
                doc_id::text, file_name, doc_type, file_size_bytes,
                doc_category, upload_date, file_url, extraction_status,
                page_count, uploaded_at,
                CASE WHEN extraction_status = 'success' AND content_text IS NOT NULL AND LENGTH(content_text) > 100 THEN true ELSE false END as has_content
            FROM documents
            WHERE tender_id = :tender_id
            ORDER BY doc_category, upload_date DESC
        """)
        result = await db.execute(docs_query, {"tender_id": tender_id})

    rows = result.fetchall()

    documents = []
    docs_by_category = {}

    for row in rows:
        doc = DocumentResponse(
            doc_id=str(row.doc_id),
            tender_id=tender_id,
            file_name=row.file_name,
            doc_type=row.doc_type,
            file_url=row.file_url,
            file_size_bytes=row.file_size_bytes,
            page_count=row.page_count,
            extraction_status=row.extraction_status or 'pending',
            has_content=bool(row.has_content),
            uploaded_at=row.uploaded_at,
            # Legacy fields for backwards compat
            document_id=str(row.doc_id),
            filename=row.file_name,
            download_url=row.file_url,
            category=row.doc_category,
            description=None,
        )
        documents.append(doc)

        # Group by category
        cat = row.doc_category or 'uncategorized'
        if cat not in docs_by_category:
            docs_by_category[cat] = 0
        docs_by_category[cat] += 1

    return DocumentsListResponse(
        tender_id=tender_id,
        total_documents=len(documents),
        total=len(documents),
        documents=documents,
        documents_by_category=docs_by_category
    )


# ============================================================================
# AI PRODUCTS EXTRACTION ENDPOINT
# ============================================================================

class AIExtractedProduct(BaseModel):
    """Product/service extracted by AI from tender documents"""
    name: str
    quantity: Optional[Any] = None  # Can be string or number from AI
    unit: Optional[str] = None
    unit_price: Optional[Any] = None  # Can be string or number from AI
    total_price: Optional[Any] = None  # Can be string or number from AI
    specifications: Optional[str] = None
    category: Optional[str] = None


class AIProductsResponse(BaseModel):
    """Response for AI-extracted products"""
    tender_id: str
    extraction_status: str  # 'success', 'no_documents', 'extraction_failed'
    products: List[AIExtractedProduct]
    summary: Optional[str] = None
    source_documents: int = 0


@router.get("/by-id/{tender_number}/{tender_year}/ai-products")
async def extract_products_with_ai(
    tender_number: str,
    tender_year: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Get products/services for a tender.

    Strategy:
    1. Return pre-extracted products from product_items table (fast, free)
    2. Only fall back to real-time Gemini if no pre-extracted data exists
    """
    import os
    import json
    import asyncio

    tender_id = f"{tender_number}/{tender_year}"

    # Check price view quota (rate-limited per tier)
    price_quota = await check_price_view_quota(current_user, db, increment=True)
    price_access = price_quota["has_quota"]

    # Verify tender exists
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender_row = tender.scalar_one_or_none()
    if not tender_row:
        raise HTTPException(status_code=404, detail="Tender not found")

    # ── Step 1: Check product_items table for pre-extracted data ──
    items_query = text("""
        SELECT pi.name, pi.quantity, pi.unit, pi.unit_price, pi.total_price,
               pi.specifications, pi.cpv_code, pi.extraction_method
        FROM product_items pi
        WHERE pi.tender_id = :tender_id
          AND pi.name IS NOT NULL
          AND LENGTH(pi.name) >= 3
        ORDER BY pi.item_number
    """)
    items_result = await db.execute(items_query, {"tender_id": tender_id})
    pre_extracted = items_result.fetchall()

    if pre_extracted:
        products = []
        for item in pre_extracted:
            specs = item.specifications
            if isinstance(specs, str):
                try:
                    specs_data = json.loads(specs)
                    specs = specs_data.get('specifications', specs)
                except (json.JSONDecodeError, AttributeError):
                    pass
            elif isinstance(specs, dict):
                specs = specs.get('specifications', json.dumps(specs, ensure_ascii=False))

            products.append(AIExtractedProduct(
                name=item.name,
                quantity=str(item.quantity) if item.quantity else None,
                unit=item.unit,
                unit_price=str(item.unit_price) if item.unit_price else None,
                total_price=str(item.total_price) if item.total_price else None,
                specifications=specs if isinstance(specs, str) else None,
                category=item.cpv_code
            ))

        # Count source documents
        doc_count_q = text("""
            SELECT COUNT(DISTINCT document_id) FROM product_items
            WHERE tender_id = :tender_id
        """)
        doc_count_result = await db.execute(doc_count_q, {"tender_id": tender_id})
        source_docs = doc_count_result.scalar() or 0

        items_with_price = sum(1 for p in products if p.unit_price)
        summary = f"Извлечени {len(products)} производи/услуги ({items_with_price} со цена) од тендерската документација."

        if not price_access:
            for p in products:
                p.unit_price = None
                p.total_price = None

        return {
            "tender_id": tender_id,
            "extraction_status": "success",
            "products": [p.dict() if hasattr(p, 'dict') else p.model_dump() for p in products],
            "summary": summary,
            "source_documents": source_docs,
            "price_gated": not price_access,
            "price_views_remaining": price_quota["remaining"],
            "price_views_limit": price_quota["limit"],
            "price_views_used": price_quota["used"],
        }

    # ── Step 2: Fall back to real-time Gemini extraction ──
    import google.generativeai as genai

    # Get documents with content_text
    docs_query = text("""
        SELECT doc_id, file_name, content_text, specifications_json
        FROM documents
        WHERE tender_id = :tender_id
          AND content_text IS NOT NULL
          AND LENGTH(content_text) > 100
        ORDER BY upload_date DESC
        LIMIT 5
    """)

    result = await db.execute(docs_query, {"tender_id": tender_id})
    docs = result.fetchall()

    if not docs:
        return AIProductsResponse(
            tender_id=tender_id,
            extraction_status="no_documents",
            products=[],
            summary="Нема достапни документи со извлечена содржина за овој тендер.",
            source_documents=0
        )

    # Combine document content (limit to ~15k chars for context)
    combined_content = ""
    for doc in docs:
        content = doc.content_text or ""
        if len(combined_content) + len(content) < 15000:
            combined_content += f"\n\n=== Документ: {doc.file_name} ===\n{content}"
        else:
            remaining = 15000 - len(combined_content)
            if remaining > 500:
                combined_content += f"\n\n=== Документ: {doc.file_name} ===\n{content[:remaining]}..."
            break

    if len(combined_content) < 100:
        return AIProductsResponse(
            tender_id=tender_id,
            extraction_status="no_documents",
            products=[],
            summary="Содржината на документите е премала за извлекување.",
            source_documents=len(docs)
        )

    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        return AIProductsResponse(
            tender_id=tender_id,
            extraction_status="extraction_failed",
            products=[],
            summary="AI сервисот не е конфигуриран.",
            source_documents=len(docs)
        )

    genai.configure(api_key=gemini_api_key)
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    date_context = get_ai_date_context()

    extraction_prompt = f"""{date_context}

Ти си експерт за анализа на тендерска документација. Од следниот текст извлечен од PDF документи, идентификувај ги сите ПРОИЗВОДИ, УСЛУГИ или СТАВКИ што се бараат во тендерот.

За секој производ/услуга извлечи:
- name: Име на производот/услугата
- quantity: Количина (број)
- unit: Мерна единица (парчиња, kg, l, m², часови, итн.)
- unit_price: Единечна цена (ако е наведена)
- total_price: Вкупна цена (ако е наведена)
- specifications: Технички спецификации или барања
- category: Категорија (канцелариски материјали, медицинска опрема, градежни материјали, IT опрема, итн.)

ВАЖНО:
- Извлечи САМО реални производи/услуги, НЕ наслови на документи или административни податоци
- Ако има табела со ставки, извлечи ги сите ставки
- Цените можат да бидат во МКД или EUR
- Ако некој податок не е достапен, остави го празно

Врати JSON во следниот формат:
{{
  "products": [
    {{
      "name": "Име на производ",
      "quantity": "100",
      "unit": "парчиња",
      "unit_price": "500 МКД",
      "total_price": "50000 МКД",
      "specifications": "Технички детали...",
      "category": "Канцелариски материјали"
    }}
  ],
  "summary": "Кратко резиме на набавката (2-3 реченици)"
}}

Ако нема производи/ставки за извлекување, врати:
{{"products": [], "summary": "Не се пронајдени производи или ставки во документацијата."}}

ДОКУМЕНТ СОДРЖИНА:
{combined_content}

ИЗВЛЕЧЕНИ ПОДАТОЦИ (JSON):"""

    try:
        def _sync_generate():
            model_obj = genai.GenerativeModel(model_name)
            response = model_obj.generate_content(
                extraction_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=8192
                )
            )
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    if candidate.finish_reason in [2, 3, 4]:
                        return None
            try:
                resp_text = response.text
                if not resp_text or not resp_text.strip():
                    return None
                return resp_text
            except ValueError:
                return None

        response_text = await asyncio.to_thread(_sync_generate)

        if response_text is None:
            return AIProductsResponse(
                tender_id=tender_id,
                extraction_status="extraction_failed",
                products=[],
                summary="AI анализата не е достапна за овој тендер поради ограничувања на содржината.",
                source_documents=len(docs)
            )

        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        try:
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                extracted_data = json.loads(json_match.group())
            else:
                return AIProductsResponse(
                    tender_id=tender_id,
                    extraction_status="extraction_failed",
                    products=[],
                    summary="AI не успеа да извлече структурирани податоци.",
                    source_documents=len(docs)
                )

        products = []
        for p in extracted_data.get("products", []):
            products.append(AIExtractedProduct(
                name=p.get("name", "Непознат производ"),
                quantity=p.get("quantity"),
                unit=p.get("unit"),
                unit_price=p.get("unit_price") if price_access else None,
                total_price=p.get("total_price") if price_access else None,
                specifications=p.get("specifications"),
                category=p.get("category")
            ))

        return {
            "tender_id": tender_id,
            "extraction_status": "success",
            "products": [p.dict() if hasattr(p, 'dict') else p.model_dump() for p in products],
            "summary": extracted_data.get("summary"),
            "source_documents": len(docs),
            "price_gated": not price_access,
            "price_views_remaining": price_quota["remaining"],
            "price_views_limit": price_quota["limit"],
            "price_views_used": price_quota["used"],
        }

    except Exception as e:
        import traceback
        print(f"AI extraction error: {str(e)}")
        print(traceback.format_exc())
        return AIProductsResponse(
            tender_id=tender_id,
            extraction_status="extraction_failed",
            products=[],
            summary=f"Грешка при AI анализа: {str(e)}",
            source_documents=len(docs)
        )
