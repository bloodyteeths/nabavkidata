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
from models import Tender
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
    document_id: str
    filename: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    category: Optional[str] = None  # technical_specs, financial_docs, award_decision, etc.
    upload_date: Optional[datetime] = None
    download_url: Optional[str] = None
    description: Optional[str] = None


class DocumentsListResponse(BaseModel):
    """List of documents for a tender"""
    tender_id: str
    total_documents: int
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
                doc_category, upload_date, file_url
            FROM documents
            WHERE tender_id = :tender_id AND doc_category = :category
            ORDER BY upload_date DESC
        """)
        result = await db.execute(docs_query, {"tender_id": tender_id, "category": category})
    else:
        docs_query = text("""
            SELECT
                doc_id::text, file_name, doc_type, file_size_bytes,
                doc_category, upload_date, file_url
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
            document_id=str(row.doc_id),
            filename=row.file_name,
            file_type=row.doc_type,
            file_size_bytes=row.file_size_bytes,
            category=row.doc_category,
            upload_date=row.upload_date,
            download_url=row.file_url,
            description=None  # description column doesn't exist
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


@router.get("/by-id/{tender_number}/{tender_year}/ai-products", response_model=AIProductsResponse)
async def extract_products_with_ai(
    tender_number: str,
    tender_year: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Extract products/services from tender documents using AI.

    This endpoint:
    1. Fetches all documents for the tender with content_text
    2. Sends the content to Gemini AI for extraction
    3. Returns structured product data (items, quantities, prices, specifications)

    Parameters:
    - tender_number: The tender number part (e.g., "21307")
    - tender_year: The tender year part (e.g., "2025")

    Returns:
    - List of AI-extracted products with quantities, prices, specifications
    """
    import os
    import json
    import asyncio
    import google.generativeai as genai

    tender_id = f"{tender_number}/{tender_year}"

    # Verify tender exists
    tender = await db.execute(
        select(Tender).where(Tender.tender_id == tender_id)
    )
    tender_row = tender.scalar_one_or_none()
    if not tender_row:
        raise HTTPException(status_code=404, detail="Tender not found")

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
            # Add truncated content
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

    # Configure Gemini
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        raise HTTPException(status_code=503, detail="AI service not configured")

    genai.configure(api_key=gemini_api_key)
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

    # Add date context
    date_context = get_ai_date_context()

    # Build extraction prompt
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
            # No safety settings to avoid blocks
            model_obj = genai.GenerativeModel(model_name)
            response = model_obj.generate_content(
                extraction_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,  # Low temperature for structured extraction
                    max_output_tokens=2000
                )
            )

            # Handle safety blocks (finish_reason=2 means SAFETY)
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    # finish_reason: 1=STOP (normal), 2=SAFETY, 3=RECITATION, 4=OTHER
                    if candidate.finish_reason == 2:
                        return None  # Safety block
                    elif candidate.finish_reason in [3, 4]:
                        return None  # Other block

            # Try to get text, handle empty responses
            try:
                text = response.text
                if not text or not text.strip():
                    return None
                return text
            except ValueError:
                # No valid response parts
                return None

        response_text = await asyncio.to_thread(_sync_generate)

        # Handle blocked or empty responses
        if response_text is None:
            return AIProductsResponse(
                tender_id=tender_id,
                extraction_status="extraction_failed",
                products=[],
                summary="AI анализата не е достапна за овој тендер поради ограничувања на содржината.",
                source_documents=len(docs)
            )

        # Clean up response - extract JSON from markdown if needed
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON response
        try:
            extracted_data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
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

        # Convert to response model
        products = []
        for p in extracted_data.get("products", []):
            products.append(AIExtractedProduct(
                name=p.get("name", "Непознат производ"),
                quantity=p.get("quantity"),
                unit=p.get("unit"),
                unit_price=p.get("unit_price"),
                total_price=p.get("total_price"),
                specifications=p.get("specifications"),
                category=p.get("category")
            ))

        return AIProductsResponse(
            tender_id=tender_id,
            extraction_status="success",
            products=products,
            summary=extracted_data.get("summary"),
            source_documents=len(docs)
        )

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
