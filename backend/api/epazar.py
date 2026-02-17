"""
API endpoints for e-Pazar electronic marketplace data
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
import logging

from database import get_db
from api.auth import get_current_user
from models import User
from utils.transliteration import get_search_variants
from middleware.entitlements import require_module
from config.plans import ModuleName
from schemas import (
    EPazarTenderResponse,
    EPazarTenderListResponse,
    EPazarItemResponse,
    EPazarOfferResponse,
    EPazarAwardedItemResponse,
    EPazarDocumentResponse,
    EPazarSupplierResponse,
    EPazarStatsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/epazar", tags=["e-Pazar"])


# ============================================================================
# TENDER ENDPOINTS
# ============================================================================

@router.get("/tenders", response_model=EPazarTenderListResponse)
async def get_epazar_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: active, awarded, cancelled, closed"),
    category: Optional[str] = Query(None, description="Filter by category"),
    cpv_code: Optional[str] = Query(None, description="Filter by CPV code prefix"),
    contracting_authority: Optional[str] = Query(None, description="Filter by contracting authority"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    min_value: Optional[float] = Query(None, description="Minimum estimated value (MKD)"),
    max_value: Optional[float] = Query(None, description="Maximum estimated value (MKD)"),
    date_from: Optional[date] = Query(None, description="Publication date from"),
    date_to: Optional[date] = Query(None, description="Publication date to"),
    closing_from: Optional[date] = Query(None, description="Closing date from"),
    closing_to: Optional[date] = Query(None, description="Closing date to"),
    sort_by: str = Query("publication_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of e-Pazar tenders with filtering and pagination.
    """
    try:
        # Build base query
        query = text("""
            SELECT
                tender_id, title, description,
                contracting_authority, contracting_authority_id,
                estimated_value_mkd, estimated_value_eur,
                awarded_value_mkd, awarded_value_eur,
                procedure_type, status,
                publication_date, closing_date, award_date, contract_date,
                contract_number, contract_duration,
                cpv_code, category,
                source_url, source_category, language,
                scraped_at, created_at, updated_at
            FROM epazar_tenders
            WHERE 1=1
        """)

        count_query = text("SELECT COUNT(*) FROM epazar_tenders WHERE 1=1")

        # Build WHERE clauses
        conditions = []
        params = {}

        if status:
            conditions.append("status = :status")
            params['status'] = status

        if category:
            conditions.append("category ILIKE :category")
            params['category'] = f"%{category}%"

        if cpv_code:
            conditions.append("cpv_code LIKE :cpv_code")
            params['cpv_code'] = f"{cpv_code}%"

        if contracting_authority:
            conditions.append("contracting_authority ILIKE :contracting_authority")
            params['contracting_authority'] = f"%{contracting_authority}%"

        if search:
            # Get both Latin and Cyrillic variants for bilingual search
            search_variants = get_search_variants(search)
            if len(search_variants) == 1:
                conditions.append("""
                    (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, ''))
                    @@ plainto_tsquery('simple', :search)
                    OR title ILIKE :search_like
                    OR description ILIKE :search_like)
                """)
                params['search'] = search_variants[0]
                params['search_like'] = f"%{search_variants[0]}%"
            else:
                # Search both Latin and Cyrillic variants
                conditions.append("""
                    (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, ''))
                    @@ plainto_tsquery('simple', :search_latin)
                    OR to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, ''))
                    @@ plainto_tsquery('simple', :search_cyrillic)
                    OR title ILIKE :search_latin_like OR title ILIKE :search_cyrillic_like
                    OR description ILIKE :search_latin_like OR description ILIKE :search_cyrillic_like)
                """)
                params['search_latin'] = search_variants[0]
                params['search_cyrillic'] = search_variants[1]
                params['search_latin_like'] = f"%{search_variants[0]}%"
                params['search_cyrillic_like'] = f"%{search_variants[1]}%"

        if min_value is not None:
            conditions.append("estimated_value_mkd >= :min_value")
            params['min_value'] = min_value

        if max_value is not None:
            conditions.append("estimated_value_mkd <= :max_value")
            params['max_value'] = max_value

        if date_from:
            conditions.append("publication_date >= :date_from")
            params['date_from'] = date_from

        if date_to:
            conditions.append("publication_date <= :date_to")
            params['date_to'] = date_to

        if closing_from:
            conditions.append("closing_date >= :closing_from")
            params['closing_from'] = closing_from

        if closing_to:
            conditions.append("closing_date <= :closing_to")
            params['closing_to'] = closing_to

        # Build final query
        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        # Validate sort field
        valid_sort_fields = ['publication_date', 'closing_date', 'estimated_value_mkd', 'title', 'status', 'created_at']
        if sort_by not in valid_sort_fields:
            sort_by = 'publication_date'

        sort_direction = 'DESC' if sort_order.lower() == 'desc' else 'ASC'

        # Get total count
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM epazar_tenders WHERE 1=1 {where_clause}"),
            params
        )
        total = count_result.scalar()

        # Get paginated results
        offset = (page - 1) * page_size
        params['limit'] = page_size
        params['offset'] = offset

        query_str = f"""
            SELECT
                tender_id, title, description,
                contracting_authority, contracting_authority_id,
                estimated_value_mkd, estimated_value_eur,
                awarded_value_mkd, awarded_value_eur,
                procedure_type, status,
                publication_date, closing_date, award_date, contract_date,
                contract_number, contract_duration,
                cpv_code, category,
                source_url, source_category, language,
                scraped_at, created_at, updated_at
            FROM epazar_tenders
            WHERE 1=1 {where_clause}
            ORDER BY {sort_by} {sort_direction} NULLS LAST
            LIMIT :limit OFFSET :offset
        """

        result = await db.execute(text(query_str), params)
        rows = result.fetchall()

        # Convert to response format
        tenders = []
        for row in rows:
            tenders.append({
                'tender_id': row.tender_id,
                'title': row.title,
                'description': row.description,
                'contracting_authority': row.contracting_authority,
                'contracting_authority_id': row.contracting_authority_id,
                'estimated_value_mkd': float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
                'estimated_value_eur': float(row.estimated_value_eur) if row.estimated_value_eur else None,
                'awarded_value_mkd': float(row.awarded_value_mkd) if row.awarded_value_mkd else None,
                'awarded_value_eur': float(row.awarded_value_eur) if row.awarded_value_eur else None,
                'procedure_type': row.procedure_type,
                'status': row.status,
                'publication_date': row.publication_date.isoformat() if row.publication_date else None,
                'closing_date': row.closing_date.isoformat() if row.closing_date else None,
                'award_date': row.award_date.isoformat() if row.award_date else None,
                'contract_date': row.contract_date.isoformat() if row.contract_date else None,
                'contract_number': row.contract_number,
                'contract_duration': row.contract_duration,
                'cpv_code': row.cpv_code,
                'category': row.category,
                'source_url': row.source_url,
                'source_category': row.source_category,
                'language': row.language,
                'scraped_at': row.scraped_at.isoformat() if row.scraped_at else None,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'updated_at': row.updated_at.isoformat() if row.updated_at else None,
            })

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': tenders
        }

    except Exception as e:
        logger.error(f"Error fetching e-Pazar tenders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenders/{tender_id}", response_model=EPazarTenderResponse)
async def get_epazar_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get single e-Pazar tender with full details.
    """
    try:
        # Get tender
        result = await db.execute(
            text("SELECT * FROM epazar_tenders WHERE tender_id = :tender_id"),
            {'tender_id': tender_id}
        )
        tender = result.fetchone()

        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")

        # Get items
        items_result = await db.execute(
            text("""
                SELECT * FROM epazar_items
                WHERE tender_id = :tender_id
                ORDER BY line_number
            """),
            {'tender_id': tender_id}
        )
        items = items_result.fetchall()

        # Get offers
        offers_result = await db.execute(
            text("""
                SELECT * FROM epazar_offers
                WHERE tender_id = :tender_id
                ORDER BY ranking NULLS LAST, total_bid_mkd ASC
            """),
            {'tender_id': tender_id}
        )
        offers = offers_result.fetchall()

        # Get awarded items
        awarded_result = await db.execute(
            text("""
                SELECT * FROM epazar_awarded_items
                WHERE tender_id = :tender_id
            """),
            {'tender_id': tender_id}
        )
        awarded_items = awarded_result.fetchall()

        # Get documents
        docs_result = await db.execute(
            text("""
                SELECT * FROM epazar_documents
                WHERE tender_id = :tender_id
            """),
            {'tender_id': tender_id}
        )
        documents = docs_result.fetchall()

        return {
            'tender_id': tender.tender_id,
            'title': tender.title,
            'description': tender.description,
            'contracting_authority': tender.contracting_authority,
            'contracting_authority_id': tender.contracting_authority_id,
            'estimated_value_mkd': float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
            'estimated_value_eur': float(tender.estimated_value_eur) if tender.estimated_value_eur else None,
            'awarded_value_mkd': float(tender.awarded_value_mkd) if tender.awarded_value_mkd else None,
            'awarded_value_eur': float(tender.awarded_value_eur) if tender.awarded_value_eur else None,
            'procedure_type': tender.procedure_type,
            'status': tender.status,
            'publication_date': tender.publication_date.isoformat() if tender.publication_date else None,
            'closing_date': tender.closing_date.isoformat() if tender.closing_date else None,
            'award_date': tender.award_date.isoformat() if tender.award_date else None,
            'contract_date': tender.contract_date.isoformat() if tender.contract_date else None,
            'contract_number': tender.contract_number,
            'contract_duration': tender.contract_duration,
            'cpv_code': tender.cpv_code,
            'category': tender.category,
            'source_url': tender.source_url,
            'items': [dict(row._mapping) for row in items],
            'offers': [dict(row._mapping) for row in offers],
            'awarded_items': [dict(row._mapping) for row in awarded_items],
            'documents': [dict(row._mapping) for row in documents],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching e-Pazar tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_tenders(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get active tenders sorted by closing deadline (soonest first).

    Returns active tenders that are still open for bidding, ordered by
    closing date to highlight the most urgent opportunities.
    """
    try:
        query = text("""
            SELECT
                tender_id, title, contracting_authority,
                estimated_value_mkd, closing_date, status,
                procedure_type, cpv_code, publication_date
            FROM epazar_tenders
            WHERE status = 'active'
              AND closing_date >= CURRENT_DATE
            ORDER BY closing_date ASC
            LIMIT :limit
        """)

        result = await db.execute(query, {'limit': limit})
        rows = result.fetchall()

        tenders = []
        for row in rows:
            tenders.append({
                'tender_id': row.tender_id,
                'title': row.title,
                'contracting_authority': row.contracting_authority,
                'estimated_value_mkd': float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
                'closing_date': row.closing_date.isoformat() if row.closing_date else None,
                'status': row.status,
                'procedure_type': row.procedure_type,
                'cpv_code': row.cpv_code,
                'publication_date': row.publication_date.isoformat() if row.publication_date else None,
            })

        return {
            "tenders": tenders,
            "total": len(tenders)
        }

    except Exception as e:
        logger.error(f"Error fetching active tenders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-awarded")
async def get_recent_awarded(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recently awarded tenders with winner information.

    Returns tenders that have been awarded or signed, showing winning
    supplier and bid amount for market intelligence.
    """
    try:
        query = text("""
            SELECT
                t.tender_id, t.title, t.contracting_authority,
                t.estimated_value_mkd, t.awarded_value_mkd,
                t.award_date, t.status,
                o.supplier_name as winner_name,
                o.total_bid_mkd as winning_bid
            FROM epazar_tenders t
            LEFT JOIN epazar_offers o ON t.tender_id = o.tender_id AND o.is_winner = true
            WHERE t.status IN ('awarded', 'signed')
            ORDER BY COALESCE(t.award_date, t.updated_at) DESC
            LIMIT :limit
        """)

        result = await db.execute(query, {'limit': limit})
        rows = result.fetchall()

        tenders = []
        for row in rows:
            tenders.append({
                'tender_id': row.tender_id,
                'title': row.title,
                'contracting_authority': row.contracting_authority,
                'estimated_value_mkd': float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
                'awarded_value_mkd': float(row.awarded_value_mkd) if row.awarded_value_mkd else None,
                'award_date': row.award_date.isoformat() if row.award_date else None,
                'status': row.status,
                'winner_name': row.winner_name,
                'winning_bid': float(row.winning_bid) if row.winning_bid else None,
            })

        return {
            "tenders": tenders,
            "total": len(tenders)
        }

    except Exception as e:
        logger.error(f"Error fetching recently awarded tenders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ITEMS ENDPOINTS
# ============================================================================

@router.get("/items", response_model=dict)
async def search_epazar_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search in item name and description"),
    cpv_code: Optional[str] = Query(None, description="Filter by CPV code prefix"),
    min_price: Optional[float] = Query(None, description="Minimum unit price (MKD)"),
    max_price: Optional[float] = Query(None, description="Maximum unit price (MKD)"),
    unit: Optional[str] = Query(None, description="Filter by unit (e.g., 'kg', 'piece')"),
    sort_by: str = Query("item_name", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search and browse all e-Pazar items across all tenders with filtering and pagination.
    """
    try:
        conditions = []
        params = {}

        if search:
            # Get both Latin and Cyrillic variants for bilingual search
            search_variants = get_search_variants(search)
            if len(search_variants) == 1:
                conditions.append("""
                    (i.item_name ILIKE :search
                    OR i.item_description ILIKE :search
                    OR i.cpv_code ILIKE :search)
                """)
                params['search'] = f"%{search_variants[0]}%"
            else:
                # Search both Latin and Cyrillic variants
                conditions.append("""
                    (i.item_name ILIKE :search_latin OR i.item_name ILIKE :search_cyrillic
                    OR i.item_description ILIKE :search_latin OR i.item_description ILIKE :search_cyrillic
                    OR i.cpv_code ILIKE :search_latin)
                """)
                params['search_latin'] = f"%{search_variants[0]}%"
                params['search_cyrillic'] = f"%{search_variants[1]}%"

        if cpv_code:
            conditions.append("i.cpv_code LIKE :cpv_code")
            params['cpv_code'] = f"{cpv_code}%"

        if min_price is not None:
            conditions.append("i.estimated_unit_price_mkd >= :min_price")
            params['min_price'] = min_price

        if max_price is not None:
            conditions.append("i.estimated_unit_price_mkd <= :max_price")
            params['max_price'] = max_price

        if unit:
            conditions.append("i.unit ILIKE :unit")
            params['unit'] = f"%{unit}%"

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        # Validate sort field (prefix with i. for table alias)
        valid_sort_fields = ['item_name', 'estimated_unit_price_mkd', 'quantity', 'estimated_total_price_mkd', 'cpv_code']
        if sort_by not in valid_sort_fields:
            sort_by = 'item_name'
        sort_field = f"i.{sort_by}"

        sort_direction = 'DESC' if sort_order.lower() == 'desc' else 'ASC'

        # Get total count
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM epazar_items i WHERE 1=1 {where_clause}"),
            params
        )
        total = count_result.scalar()

        # Get paginated results with tender info
        offset = (page - 1) * page_size
        params['limit'] = page_size
        params['offset'] = offset

        result = await db.execute(
            text(f"""
                SELECT i.*,
                       t.title as tender_title,
                       t.contracting_authority,
                       t.status as tender_status,
                       t.closing_date as tender_closing_date
                FROM epazar_items i
                LEFT JOIN epazar_tenders t ON i.tender_id = t.tender_id
                WHERE 1=1 {where_clause}
                ORDER BY {sort_field} {sort_direction} NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            params
        )
        items = result.fetchall()

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': [dict(row._mapping) for row in items]
        }

    except Exception as e:
        logger.error(f"Error searching e-Pazar items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/aggregations", response_model=dict)
async def get_epazar_items_aggregations(
    search: Optional[str] = Query(None, description="Search term to aggregate"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get price aggregations for e-Pazar items (min, max, avg prices by item name).
    """
    try:
        conditions = []
        params = {}

        if search:
            conditions.append("item_name ILIKE :search")
            params['search'] = f"%{search}%"

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        result = await db.execute(
            text(f"""
                SELECT
                    item_name,
                    unit,
                    COUNT(*) as occurrence_count,
                    MIN(estimated_unit_price_mkd) as min_unit_price,
                    MAX(estimated_unit_price_mkd) as max_unit_price,
                    AVG(estimated_unit_price_mkd) as avg_unit_price,
                    SUM(quantity) as total_quantity,
                    COUNT(DISTINCT tender_id) as tender_count
                FROM epazar_items
                WHERE estimated_unit_price_mkd IS NOT NULL AND estimated_unit_price_mkd > 0 {where_clause}
                GROUP BY item_name, unit
                ORDER BY occurrence_count DESC
                LIMIT 50
            """),
            params
        )
        aggregations = result.fetchall()

        return {
            'aggregations': [dict(row._mapping) for row in aggregations]
        }

    except Exception as e:
        logger.error(f"Error getting e-Pazar items aggregations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenders/{tender_id}/items", response_model=List[EPazarItemResponse])
async def get_epazar_items(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get BOQ items for a tender.
    """
    try:
        result = await db.execute(
            text("""
                SELECT * FROM epazar_items
                WHERE tender_id = :tender_id
                ORDER BY line_number
            """),
            {'tender_id': tender_id}
        )
        items = result.fetchall()

        return [dict(row._mapping) for row in items]

    except Exception as e:
        logger.error(f"Error fetching items for tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OFFERS ENDPOINTS
# ============================================================================

@router.get("/tenders/{tender_id}/offers", response_model=List[EPazarOfferResponse])
async def get_epazar_offers(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all offers/bids for a tender.
    """
    try:
        result = await db.execute(
            text("""
                SELECT o.*,
                    (SELECT COUNT(*) FROM epazar_offer_items WHERE offer_id = o.offer_id) as items_count
                FROM epazar_offers o
                WHERE o.tender_id = :tender_id
                ORDER BY o.ranking NULLS LAST, o.total_bid_mkd ASC
            """),
            {'tender_id': tender_id}
        )
        offers = result.fetchall()

        return [dict(row._mapping) for row in offers]

    except Exception as e:
        logger.error(f"Error fetching offers for tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/offers/{offer_id}/items")
async def get_offer_items(
    offer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get item-level pricing for an offer.
    """
    try:
        result = await db.execute(
            text("""
                SELECT oi.*, i.item_name, i.item_description, i.unit
                FROM epazar_offer_items oi
                JOIN epazar_items i ON oi.item_id = i.item_id
                WHERE oi.offer_id = :offer_id
            """),
            {'offer_id': offer_id}
        )
        items = result.fetchall()

        return [dict(row._mapping) for row in items]

    except Exception as e:
        logger.error(f"Error fetching offer items for offer {offer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AWARDED ITEMS ENDPOINTS
# ============================================================================

@router.get("/tenders/{tender_id}/awarded-items", response_model=List[EPazarAwardedItemResponse])
async def get_epazar_awarded_items(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get awarded contract items for a tender.
    """
    try:
        result = await db.execute(
            text("""
                SELECT ai.*, i.item_name, i.item_description
                FROM epazar_awarded_items ai
                LEFT JOIN epazar_items i ON ai.item_id = i.item_id
                WHERE ai.tender_id = :tender_id
            """),
            {'tender_id': tender_id}
        )
        items = result.fetchall()

        return [dict(row._mapping) for row in items]

    except Exception as e:
        logger.error(f"Error fetching awarded items for tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DOCUMENTS ENDPOINTS
# ============================================================================

@router.get("/tenders/{tender_id}/documents", response_model=List[EPazarDocumentResponse])
async def get_epazar_documents(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get documents for a tender.
    """
    try:
        result = await db.execute(
            text("""
                SELECT * FROM epazar_documents
                WHERE tender_id = :tender_id
                ORDER BY doc_type, upload_date DESC NULLS LAST
            """),
            {'tender_id': tender_id}
        )
        documents = result.fetchall()

        return [dict(row._mapping) for row in documents]

    except Exception as e:
        logger.error(f"Error fetching documents for tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EVALUATION DATA ENDPOINTS (GOLD data from PDF evaluation reports)
# ============================================================================

@router.get("/tenders/{tender_id}/evaluation", dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
async def get_epazar_evaluation(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get evaluation data for a tender - winning items with brands and actual prices.
    This is the GOLD data extracted from PDF evaluation reports.
    """
    try:
        # Get evaluation report info
        report_result = await db.execute(
            text("""
                SELECT report_id, tender_number, contracting_authority,
                       tender_subject, tender_type, bidders_list,
                       extraction_status, extraction_confidence
                FROM epazar_evaluation_reports
                WHERE tender_id = :tender_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {'tender_id': tender_id}
        )
        report = report_result.fetchone()

        # Get evaluation items (winning items with brands and actual prices)
        items_result = await db.execute(
            text("""
                SELECT
                    line_number, item_subject, required_brands_raw,
                    offered_brand, unit, quantity,
                    unit_price_without_vat, total_without_vat,
                    winner_name
                FROM epazar_item_evaluations
                WHERE tender_id = :tender_id
                ORDER BY line_number
            """),
            {'tender_id': tender_id}
        )
        items = items_result.fetchall()

        # Get bidders from evaluation
        bidders_result = await db.execute(
            text("""
                SELECT bidder_name, is_winner, is_rejected
                FROM epazar_bidders
                WHERE tender_id = :tender_id
                ORDER BY is_winner DESC, bidder_name
            """),
            {'tender_id': tender_id}
        )
        bidders = bidders_result.fetchall()

        # Format items with market price comparison
        formatted_items = []
        for item in items:
            item_dict = dict(item._mapping)

            # Get market prices for this item
            if item.item_subject:
                market_result = await db.execute(
                    text("""
                        SELECT
                            MIN(unit_price_without_vat) FILTER (WHERE unit_price_without_vat > 0) as market_min,
                            AVG(unit_price_without_vat) FILTER (WHERE unit_price_without_vat > 0) as market_avg,
                            MAX(unit_price_without_vat) FILTER (WHERE unit_price_without_vat > 0) as market_max,
                            COUNT(*) FILTER (WHERE unit_price_without_vat > 0) as market_count
                        FROM epazar_item_evaluations
                        WHERE item_subject ILIKE :search
                          AND tender_id != :tender_id
                    """),
                    {'search': f"%{item.item_subject[:30]}%", 'tender_id': tender_id}
                )
                market = market_result.fetchone()
                if market and market.market_count and market.market_count > 0:
                    item_dict['market_min'] = float(market.market_min) if market.market_min else None
                    item_dict['market_avg'] = float(market.market_avg) if market.market_avg else None
                    item_dict['market_max'] = float(market.market_max) if market.market_max else None
                    item_dict['market_count'] = market.market_count

            # Convert Decimal to float
            if item_dict.get('unit_price_without_vat'):
                item_dict['unit_price_without_vat'] = float(item_dict['unit_price_without_vat'])
            if item_dict.get('total_without_vat'):
                item_dict['total_without_vat'] = float(item_dict['total_without_vat'])
            if item_dict.get('quantity'):
                item_dict['quantity'] = float(item_dict['quantity'])

            formatted_items.append(item_dict)

        return {
            'tender_id': tender_id,
            'has_evaluation': report is not None and len(items) > 0,
            'extraction_status': report.extraction_status if report else None,
            'extraction_confidence': float(report.extraction_confidence) if report and report.extraction_confidence else None,
            'tender_number': report.tender_number if report else None,
            'contracting_authority': report.contracting_authority if report else None,
            'tender_subject': report.tender_subject if report else None,
            'bidders': [
                {
                    'name': b.bidder_name,
                    'is_winner': b.is_winner,
                    'is_rejected': b.is_rejected
                }
                for b in bidders
            ],
            'items': formatted_items,
            'items_count': len(formatted_items),
            'total_value': sum(
                item.get('total_without_vat', 0) or 0
                for item in formatted_items
            )
        }

    except Exception as e:
        logger.error(f"Error fetching evaluation for tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenders/{tender_id}/price-hints", dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
async def get_price_hints_for_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get price hints for items in a tender based on historical sales.
    Uses AI-matched similar items from past evaluation reports.
    """
    try:
        # Get items from this tender
        items_result = await db.execute(
            text("""
                SELECT item_id, line_number, item_name, quantity, unit,
                       estimated_unit_price_mkd
                FROM epazar_items
                WHERE tender_id = :tender_id
                ORDER BY line_number
                LIMIT 20
            """),
            {'tender_id': tender_id}
        )
        items = items_result.fetchall()

        hints = []
        for item in items:
            item_name = item.item_name
            if not item_name or len(item_name) < 3:
                continue

            # Find similar items from evaluation data (past sales)
            # Use first few words for matching
            search_terms = item_name[:40].replace('%', '').strip()

            similar_result = await db.execute(
                text("""
                    SELECT
                        e.item_subject,
                        e.offered_brand,
                        e.unit_price_without_vat,
                        e.quantity,
                        e.winner_name,
                        t.title as tender_title,
                        t.publication_date,
                        t.tender_id as source_tender_id
                    FROM epazar_item_evaluations e
                    JOIN epazar_tenders t ON e.tender_id = t.tender_id
                    WHERE e.item_subject ILIKE :search
                      AND e.unit_price_without_vat > 0
                      AND e.tender_id != :tender_id
                    ORDER BY t.publication_date DESC
                    LIMIT 5
                """),
                {'search': f"%{search_terms}%", 'tender_id': tender_id}
            )
            similar_items = similar_result.fetchall()

            if similar_items:
                # Calculate price stats
                prices = [float(s.unit_price_without_vat) for s in similar_items if s.unit_price_without_vat]
                brands = [s.offered_brand for s in similar_items if s.offered_brand]

                hints.append({
                    'line_number': item.line_number,
                    'item_name': item_name,
                    'estimated_price': float(item.estimated_unit_price_mkd) if item.estimated_unit_price_mkd else None,
                    'historical': {
                        'min_price': min(prices) if prices else None,
                        'max_price': max(prices) if prices else None,
                        'avg_price': sum(prices) / len(prices) if prices else None,
                        'sample_count': len(similar_items),
                        'brands': list(set(brands))[:3],
                        'examples': [
                            {
                                'price': float(s.unit_price_without_vat),
                                'brand': s.offered_brand,
                                'winner': s.winner_name,
                                'tender_title': s.tender_title,
                                'tender_id': s.source_tender_id,
                                'date': s.publication_date.isoformat() if s.publication_date else None
                            }
                            for s in similar_items[:3]
                        ]
                    }
                })

        return {
            'tender_id': tender_id,
            'hints': hints,
            'hints_count': len(hints)
        }

    except Exception as e:
        logger.error(f"Error fetching price hints for tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUPPLIERS ENDPOINTS
# ============================================================================

@router.get("/suppliers", response_model=dict)
async def get_epazar_suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search supplier name"),
    city: Optional[str] = Query(None, description="Filter by city"),
    min_wins: Optional[int] = Query(None, description="Minimum wins"),
    sort_by: str = Query("total_contract_value_mkd", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of e-Pazar suppliers with statistics.
    """
    try:
        conditions = []
        params = {}

        if search:
            conditions.append("company_name ILIKE :search")
            params['search'] = f"%{search}%"

        if city:
            conditions.append("city ILIKE :city")
            params['city'] = f"%{city}%"

        if min_wins is not None:
            conditions.append("total_wins >= :min_wins")
            params['min_wins'] = min_wins

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        # Validate sort field
        valid_sort_fields = ['company_name', 'total_wins', 'total_offers', 'total_contract_value_mkd', 'win_rate']
        if sort_by not in valid_sort_fields:
            sort_by = 'total_contract_value_mkd'

        sort_direction = 'DESC' if sort_order.lower() == 'desc' else 'ASC'

        # Get total count
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM epazar_suppliers WHERE 1=1 {where_clause}"),
            params
        )
        total = count_result.scalar()

        # Get paginated results
        offset = (page - 1) * page_size
        params['limit'] = page_size
        params['offset'] = offset

        result = await db.execute(
            text(f"""
                SELECT * FROM epazar_suppliers
                WHERE 1=1 {where_clause}
                ORDER BY {sort_by} {sort_direction} NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            params
        )
        suppliers = result.fetchall()

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': [dict(row._mapping) for row in suppliers]
        }

    except Exception as e:
        logger.error(f"Error fetching e-Pazar suppliers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suppliers/{supplier_id}", response_model=EPazarSupplierResponse)
async def get_epazar_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get single supplier with full details and recent contracts.
    """
    try:
        # Get supplier
        result = await db.execute(
            text("SELECT * FROM epazar_suppliers WHERE supplier_id = :supplier_id"),
            {'supplier_id': supplier_id}
        )
        supplier = result.fetchone()

        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

        # Get recent offers
        offers_result = await db.execute(
            text("""
                SELECT o.*, t.title as tender_title, t.closing_date
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE o.supplier_name = :supplier_name
                ORDER BY o.offer_date DESC NULLS LAST
                LIMIT 20
            """),
            {'supplier_name': supplier.company_name}
        )
        recent_offers = offers_result.fetchall()

        # Get recent wins
        wins_result = await db.execute(
            text("""
                SELECT o.*, t.title as tender_title, t.closing_date, t.awarded_value_mkd
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE o.supplier_name = :supplier_name AND o.is_winner = TRUE
                ORDER BY o.offer_date DESC NULLS LAST
                LIMIT 10
            """),
            {'supplier_name': supplier.company_name}
        )
        recent_wins = wins_result.fetchall()

        return {
            **dict(supplier._mapping),
            'recent_offers': [dict(row._mapping) for row in recent_offers],
            'recent_wins': [dict(row._mapping) for row in recent_wins],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching e-Pazar supplier {supplier_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@router.get("/stats/overview", response_model=EPazarStatsResponse)
async def get_epazar_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get overview statistics for e-Pazar data.
    """
    try:
        # Total tenders by status
        status_result = await db.execute(
            text("""
                SELECT status, COUNT(*) as count,
                       COALESCE(SUM(estimated_value_mkd), 0) as total_value
                FROM epazar_tenders
                GROUP BY status
            """)
        )
        status_stats = {row.status: {'count': row.count, 'total_value': float(row.total_value)}
                       for row in status_result.fetchall()}

        # Total counts
        totals_result = await db.execute(
            text("""
                SELECT
                    (SELECT COUNT(*) FROM epazar_tenders) as total_tenders,
                    (SELECT COUNT(*) FROM epazar_items) as total_items,
                    (SELECT COUNT(*) FROM epazar_offers) as total_offers,
                    (SELECT COUNT(*) FROM epazar_suppliers) as total_suppliers,
                    (SELECT COUNT(*) FROM epazar_documents) as total_documents,
                    (SELECT COALESCE(SUM(awarded_value_mkd), 0) FROM epazar_tenders WHERE awarded_value_mkd > 0) as total_value_mkd,
                    (SELECT COALESCE(SUM(awarded_value_mkd), 0) FROM epazar_tenders WHERE status = 'awarded') as awarded_value_mkd
            """)
        )
        totals = totals_result.fetchone()

        # Recent activity
        recent_result = await db.execute(
            text("""
                SELECT tender_id, title, status, publication_date, estimated_value_mkd
                FROM epazar_tenders
                ORDER BY created_at DESC
                LIMIT 5
            """)
        )
        recent_tenders = recent_result.fetchall()

        # Top suppliers
        suppliers_result = await db.execute(
            text("""
                SELECT company_name, total_wins, total_contract_value_mkd, win_rate
                FROM epazar_suppliers
                ORDER BY total_contract_value_mkd DESC NULLS LAST
                LIMIT 5
            """)
        )
        top_suppliers = suppliers_result.fetchall()

        return {
            'total_tenders': totals.total_tenders,
            'total_items': totals.total_items,
            'total_offers': totals.total_offers,
            'total_suppliers': totals.total_suppliers,
            'total_documents': totals.total_documents,
            'total_value_mkd': float(totals.total_value_mkd),
            'awarded_value_mkd': float(totals.awarded_value_mkd),
            'status_breakdown': status_stats,
            'recent_tenders': [dict(row._mapping) for row in recent_tenders],
            'top_suppliers': [dict(row._mapping) for row in top_suppliers],
        }

    except Exception as e:
        logger.error(f"Error fetching e-Pazar stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI SUMMARIZATION ENDPOINTS
# ============================================================================

@router.post("/tenders/{tender_id}/summarize", dependencies=[Depends(require_module(ModuleName.RAG_SEARCH))])
async def summarize_tender(
    tender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI summary of tender items and contract details.
    Requires authentication.
    """
    try:
        # Get tender with all related data
        tender_result = await db.execute(
            text("SELECT * FROM epazar_tenders WHERE tender_id = :tender_id"),
            {'tender_id': tender_id}
        )
        tender = tender_result.fetchone()

        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")

        # Get items
        items_result = await db.execute(
            text("SELECT * FROM epazar_items WHERE tender_id = :tender_id ORDER BY line_number"),
            {'tender_id': tender_id}
        )
        items = items_result.fetchall()

        # Get offers
        offers_result = await db.execute(
            text("SELECT * FROM epazar_offers WHERE tender_id = :tender_id ORDER BY ranking"),
            {'tender_id': tender_id}
        )
        offers = offers_result.fetchall()

        # Get documents with extracted content
        docs_result = await db.execute(
            text("""
                SELECT file_name, doc_type, content_text
                FROM epazar_documents
                WHERE tender_id = :tender_id
                  AND extraction_status = 'success'
                  AND content_text IS NOT NULL
                  AND content_text != ''
            """),
            {'tender_id': tender_id}
        )
        documents = docs_result.fetchall()

        # Build context for AI
        context = {
            'tender_title': tender.title,
            'tender_description': tender.description,
            'contracting_authority': tender.contracting_authority,
            'estimated_value': float(tender.estimated_value_mkd) if tender.estimated_value_mkd else None,
            'status': tender.status,
            'items': [
                {
                    'name': item.item_name,
                    'quantity': float(item.quantity) if item.quantity else None,
                    'unit': item.unit,
                    'estimated_price': float(item.estimated_total_price_mkd) if item.estimated_total_price_mkd else None,
                }
                for item in items
            ],
            'offers': [
                {
                    'supplier': offer.supplier_name,
                    'amount': float(offer.total_bid_mkd) if offer.total_bid_mkd else None,
                    'is_winner': offer.is_winner,
                    'ranking': offer.ranking,
                }
                for offer in offers
            ],
            'documents': [
                {
                    'file_name': doc.file_name,
                    'doc_type': doc.doc_type,
                    'content': doc.content_text[:5000] if doc.content_text else None,  # Limit to 5k chars per doc
                }
                for doc in documents
            ],
        }

        # Call AI service (using existing RAG infrastructure)
        from ai.rag_query import generate_tender_summary

        summary = await generate_tender_summary(context)

        return {
            'tender_id': tender_id,
            'summary': summary,
            'items_count': len(items),
            'offers_count': len(offers),
            'documents_used': len(documents),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suppliers/{supplier_id}/analyze", dependencies=[Depends(require_module(ModuleName.COMPETITOR_TRACKING))])
async def analyze_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI analysis of supplier performance.
    Requires authentication.
    """
    try:
        # Get supplier
        result = await db.execute(
            text("SELECT * FROM epazar_suppliers WHERE supplier_id = :supplier_id"),
            {'supplier_id': supplier_id}
        )
        supplier = result.fetchone()

        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

        # Get all offers
        offers_result = await db.execute(
            text("""
                SELECT o.*, t.title, t.category, t.cpv_code, t.estimated_value_mkd
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE o.supplier_name = :supplier_name
                ORDER BY o.offer_date DESC
            """),
            {'supplier_name': supplier.company_name}
        )
        offers = offers_result.fetchall()

        # Build analysis context
        context = {
            'company_name': supplier.company_name,
            'total_offers': supplier.total_offers,
            'total_wins': supplier.total_wins,
            'win_rate': float(supplier.win_rate) if supplier.win_rate else 0,
            'total_contract_value': float(supplier.total_contract_value_mkd) if supplier.total_contract_value_mkd else 0,
            'industries': supplier.industries,
            'offers_history': [
                {
                    'tender_title': offer.title,
                    'category': offer.category,
                    'bid_amount': float(offer.total_bid_mkd) if offer.total_bid_mkd else None,
                    'is_winner': offer.is_winner,
                    'ranking': offer.ranking,
                }
                for offer in offers[:50]  # Limit to recent 50
            ],
        }

        # Call AI service
        from ai.rag_query import generate_supplier_analysis

        analysis = await generate_supplier_analysis(context)

        return {
            'supplier_id': supplier_id,
            'company_name': supplier.company_name,
            'analysis': analysis,
            'total_offers_analyzed': len(offers),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing supplier {supplier_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BUYER/INSTITUTION PROFILES
# ============================================================================

@router.get("/buyers", response_model=dict)
async def get_epazar_buyers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search buyer name"),
    min_tenders: Optional[int] = Query(None, description="Minimum tender count"),
    sort_by: str = Query("total_value_mkd", description="Sort field: total_value_mkd, total_tenders, avg_tender_value"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of e-Pazar buyers/institutions with statistics.

    Returns aggregated buyer profiles showing total tenders, spending, and preferred suppliers.
    """
    try:
        conditions = []
        params = {}

        if search:
            conditions.append("contracting_authority ILIKE :search")
            params['search'] = f"%{search}%"

        if min_tenders is not None:
            conditions.append("tender_count >= :min_tenders")
            params['min_tenders'] = min_tenders

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        # Validate sort field
        valid_sort_fields = ['total_value_mkd', 'total_tenders', 'avg_tender_value']
        if sort_by not in valid_sort_fields:
            sort_by = 'total_value_mkd'

        sort_direction = 'DESC' if sort_order.lower() == 'desc' else 'ASC'

        # Build aggregated query for buyers
        base_query = f"""
            WITH buyer_stats AS (
                SELECT
                    contracting_authority,
                    COUNT(*) as tender_count,
                    COALESCE(SUM(awarded_value_mkd), 0) as total_value,
                    COALESCE(AVG(awarded_value_mkd), 0) as avg_value
                FROM epazar_tenders
                WHERE contracting_authority IS NOT NULL
                  AND contracting_authority != ''
                GROUP BY contracting_authority
                HAVING COUNT(*) > 0 {where_clause}
            )
            SELECT
                contracting_authority,
                tender_count as total_tenders,
                total_value as total_value_mkd,
                avg_value as avg_tender_value_mkd
            FROM buyer_stats
        """

        # Map sort fields
        sort_field_map = {
            'total_value_mkd': 'total_value',
            'total_tenders': 'tender_count',
            'avg_tender_value': 'avg_value'
        }
        actual_sort_field = sort_field_map.get(sort_by, 'total_value')

        # Get total count
        count_query = f"""
            WITH buyer_stats AS (
                SELECT
                    contracting_authority,
                    COUNT(*) as tender_count
                FROM epazar_tenders
                WHERE contracting_authority IS NOT NULL
                  AND contracting_authority != ''
                GROUP BY contracting_authority
                HAVING COUNT(*) > 0 {where_clause}
            )
            SELECT COUNT(*) FROM buyer_stats
        """

        count_result = await db.execute(text(count_query), params)
        total = count_result.scalar()

        # Get paginated results
        offset = (page - 1) * page_size
        params['limit'] = page_size
        params['offset'] = offset

        query_str = f"""
            {base_query}
            ORDER BY {actual_sort_field} {sort_direction} NULLS LAST
            LIMIT :limit OFFSET :offset
        """

        result = await db.execute(text(query_str), params)
        buyer_rows = result.fetchall()

        # For each buyer, get preferred suppliers and main categories
        buyers = []
        for row in buyer_rows:
            buyer_name = row.contracting_authority

            # Get top 2 preferred suppliers (by contract count)
            suppliers_result = await db.execute(
                text("""
                    SELECT o.supplier_name, COUNT(*) as contract_count
                    FROM epazar_offers o
                    JOIN epazar_tenders t ON o.tender_id = t.tender_id
                    WHERE t.contracting_authority = :buyer_name
                      AND o.is_winner = TRUE
                      AND o.supplier_name IS NOT NULL
                    GROUP BY o.supplier_name
                    ORDER BY contract_count DESC
                    LIMIT 2
                """),
                {'buyer_name': buyer_name}
            )
            preferred_suppliers = [s.supplier_name for s in suppliers_result.fetchall()]

            # Get main categories (top 3)
            categories_result = await db.execute(
                text("""
                    SELECT category, COUNT(*) as count
                    FROM epazar_tenders
                    WHERE contracting_authority = :buyer_name
                      AND category IS NOT NULL
                    GROUP BY category
                    ORDER BY count DESC
                    LIMIT 3
                """),
                {'buyer_name': buyer_name}
            )
            main_categories = [c.category for c in categories_result.fetchall()]

            buyers.append({
                'name': buyer_name,
                'total_tenders': row.total_tenders,
                'total_value_mkd': float(row.total_value_mkd),
                'avg_tender_value_mkd': round(float(row.avg_tender_value_mkd), 2),
                'preferred_suppliers': preferred_suppliers,
                'main_categories': main_categories
            })

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'buyers': buyers
        }

    except Exception as e:
        logger.error(f"Error fetching e-Pazar buyers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buyers/{buyer_name}", response_model=dict)
async def get_epazar_buyer_profile(
    buyer_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed profile for a specific e-Pazar buyer/institution.

    Returns comprehensive statistics including spending patterns, supplier relationships,
    category breakdown, and recent activity.
    """
    try:
        # Get basic stats
        stats_result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total_tenders,
                    COALESCE(SUM(awarded_value_mkd), 0) as total_value,
                    COALESCE(AVG(awarded_value_mkd), 0) as avg_tender_value,
                    MIN(publication_date) as first_tender_date,
                    MAX(publication_date) as last_tender_date
                FROM epazar_tenders
                WHERE contracting_authority = :buyer_name
            """),
            {'buyer_name': buyer_name}
        )
        stats = stats_result.fetchone()

        if not stats or stats.total_tenders == 0:
            raise HTTPException(status_code=404, detail="Buyer not found")

        # Get average offers per tender
        offers_stats_result = await db.execute(
            text("""
                SELECT AVG(offer_count) as avg_offers
                FROM (
                    SELECT t.tender_id, COUNT(o.offer_id) as offer_count
                    FROM epazar_tenders t
                    LEFT JOIN epazar_offers o ON t.tender_id = o.tender_id
                    WHERE t.contracting_authority = :buyer_name
                    GROUP BY t.tender_id
                ) offer_counts
            """),
            {'buyer_name': buyer_name}
        )
        avg_offers = offers_stats_result.scalar() or 0

        # Calculate average discount (estimated vs awarded)
        discount_result = await db.execute(
            text("""
                SELECT AVG(
                    CASE
                        WHEN estimated_value_mkd > 0 AND awarded_value_mkd IS NOT NULL
                        THEN (estimated_value_mkd - awarded_value_mkd) / estimated_value_mkd * 100
                        ELSE 0
                    END
                ) as avg_discount
                FROM epazar_tenders
                WHERE contracting_authority = :buyer_name
                  AND estimated_value_mkd > 0
                  AND awarded_value_mkd IS NOT NULL
            """),
            {'buyer_name': buyer_name}
        )
        avg_discount = discount_result.scalar() or 0

        # Get top suppliers (by contract count and value)
        suppliers_result = await db.execute(
            text("""
                SELECT
                    o.supplier_name,
                    COUNT(*) as contract_count,
                    COALESCE(SUM(t.awarded_value_mkd), 0) as total_value,
                    COALESCE(AVG(t.awarded_value_mkd), 0) as avg_value
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE t.contracting_authority = :buyer_name
                  AND o.is_winner = TRUE
                  AND o.supplier_name IS NOT NULL
                GROUP BY o.supplier_name
                ORDER BY contract_count DESC, total_value DESC
                LIMIT 10
            """),
            {'buyer_name': buyer_name}
        )
        top_suppliers = [
            {
                'supplier_name': row.supplier_name,
                'contract_count': row.contract_count,
                'total_value_mkd': float(row.total_value),
                'avg_value_mkd': round(float(row.avg_value), 2)
            }
            for row in suppliers_result.fetchall()
        ]

        # Get recent tenders (last 10)
        recent_result = await db.execute(
            text("""
                SELECT
                    tender_id,
                    title,
                    status,
                    publication_date,
                    closing_date,
                    estimated_value_mkd,
                    awarded_value_mkd,
                    category
                FROM epazar_tenders
                WHERE contracting_authority = :buyer_name
                ORDER BY publication_date DESC NULLS LAST
                LIMIT 10
            """),
            {'buyer_name': buyer_name}
        )
        recent_tenders = [
            {
                'tender_id': row.tender_id,
                'title': row.title,
                'status': row.status,
                'publication_date': row.publication_date.isoformat() if row.publication_date else None,
                'closing_date': row.closing_date.isoformat() if row.closing_date else None,
                'estimated_value_mkd': float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
                'awarded_value_mkd': float(row.awarded_value_mkd) if row.awarded_value_mkd else None,
                'category': row.category
            }
            for row in recent_result.fetchall()
        ]

        # Get category breakdown
        categories_result = await db.execute(
            text("""
                SELECT
                    category,
                    COUNT(*) as tender_count,
                    COALESCE(SUM(awarded_value_mkd), 0) as total_value
                FROM epazar_tenders
                WHERE contracting_authority = :buyer_name
                  AND category IS NOT NULL
                GROUP BY category
                ORDER BY tender_count DESC
                LIMIT 10
            """),
            {'buyer_name': buyer_name}
        )
        category_breakdown = [
            {
                'category': row.category,
                'tender_count': row.tender_count,
                'total_value_mkd': float(row.total_value)
            }
            for row in categories_result.fetchall()
        ]

        # Get monthly spending (last 12 months)
        monthly_result = await db.execute(
            text("""
                SELECT
                    date_trunc('month', publication_date) as month,
                    COUNT(*) as tender_count,
                    COALESCE(SUM(awarded_value_mkd), 0) as total_spending
                FROM epazar_tenders
                WHERE contracting_authority = :buyer_name
                  AND publication_date >= NOW() - INTERVAL '12 months'
                GROUP BY date_trunc('month', publication_date)
                ORDER BY month DESC
            """),
            {'buyer_name': buyer_name}
        )
        monthly_spending = [
            {
                'month': row.month.strftime('%Y-%m') if row.month else None,
                'tender_count': row.tender_count,
                'total_spending_mkd': float(row.total_spending)
            }
            for row in monthly_result.fetchall()
        ]

        return {
            'name': buyer_name,
            'stats': {
                'total_tenders': stats.total_tenders,
                'total_value_mkd': float(stats.total_value),
                'avg_tender_value': round(float(stats.avg_tender_value), 2),
                'avg_offers_per_tender': round(float(avg_offers), 2),
                'avg_discount_awarded': round(float(avg_discount), 2),
                'first_tender_date': stats.first_tender_date.isoformat() if stats.first_tender_date else None,
                'last_tender_date': stats.last_tender_date.isoformat() if stats.last_tender_date else None
            },
            'top_suppliers': top_suppliers,
            'recent_tenders': recent_tenders,
            'category_breakdown': category_breakdown,
            'monthly_spending': monthly_spending
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching buyer profile for {buyer_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ITEM PRICE HISTORY
# ============================================================================

@router.get("/items/{item_id}/price-history")
async def get_epazar_item_price_history(
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get price history for a specific e-Pazar item across all tenders.

    Returns historical prices, statistics, and price trend analysis.
    """
    try:
        # First get the item to find its name
        item_query = text("""
            SELECT item_id, item_name, item_description, unit, cpv_code
            FROM epazar_items
            WHERE item_id = :item_id
        """)
        item_result = await db.execute(item_query, {'item_id': item_id})
        item = item_result.fetchone()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Get price history for this item and similar items
        history_query = text("""
            SELECT
                i.tender_id,
                t.closing_date,
                t.contracting_authority,
                t.status as tender_status,
                i.estimated_unit_price_mkd as unit_price,
                i.quantity,
                i.estimated_total_price_mkd as total_price,
                o.supplier_name,
                o.is_winner,
                oi.unit_price_mkd as winning_unit_price
            FROM epazar_items i
            JOIN epazar_tenders t ON i.tender_id = t.tender_id
            LEFT JOIN epazar_offers o ON i.tender_id = o.tender_id AND o.is_winner = TRUE
            LEFT JOIN epazar_offer_items oi ON o.offer_id = oi.offer_id AND oi.item_id = i.item_id
            WHERE i.item_id = :item_id
               OR (i.item_name ILIKE :item_name AND i.item_id != :item_id)
            ORDER BY t.closing_date DESC NULLS LAST
            LIMIT 100
        """)

        history_result = await db.execute(history_query, {
            'item_id': item_id,
            'item_name': f"%{item.item_name}%"
        })
        history_rows = history_result.fetchall()

        # Build price history
        price_history = []
        prices = []
        for row in history_rows:
            price = float(row.unit_price) if row.unit_price else None
            winning_price = float(row.winning_unit_price) if row.winning_unit_price else None

            if price:
                prices.append(price)

            price_history.append({
                "tender_id": row.tender_id,
                "date": row.closing_date.isoformat() if row.closing_date else None,
                "contracting_authority": row.contracting_authority,
                "unit_price_mkd": price,
                "winning_unit_price_mkd": winning_price,
                "quantity": float(row.quantity) if row.quantity else None,
                "total_price_mkd": float(row.total_price) if row.total_price else None,
                "supplier": row.supplier_name,
                "is_winning_price": row.is_winner or False
            })

        # Calculate statistics
        statistics = {
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "avg_price": sum(prices) / len(prices) if prices else None,
            "occurrence_count": len(price_history),
            "price_trend": "stable"
        }

        # Determine price trend
        if len(prices) >= 3:
            recent_avg = sum(prices[:len(prices)//3]) / (len(prices)//3)
            older_avg = sum(prices[2*len(prices)//3:]) / (len(prices) - 2*len(prices)//3)
            if recent_avg > older_avg * 1.1:
                statistics["price_trend"] = "rising"
            elif recent_avg < older_avg * 0.9:
                statistics["price_trend"] = "falling"

        return {
            "item_id": item_id,
            "item_name": item.item_name,
            "item_description": item.item_description,
            "unit": item.unit,
            "cpv_code": item.cpv_code,
            "price_history": price_history,
            "statistics": statistics
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price history for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUPPLIER DETAILED STATS
# ============================================================================

@router.get("/tenders/{tender_id}/similar")
async def get_similar_epazar_tenders(
    tender_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of similar tenders to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get similar past e-Pazar tenders based on:
    1. Same contracting_authority
    2. Similar item names (text similarity)
    3. Same category

    Returns similar tenders with insights for competitive bidding strategy.
    """
    try:
        # Get current tender with items
        current_tender_query = text("""
            SELECT t.*,
                   ARRAY_AGG(DISTINCT i.item_name) FILTER (WHERE i.item_name IS NOT NULL) as item_names
            FROM epazar_tenders t
            LEFT JOIN epazar_items i ON t.tender_id = i.tender_id
            WHERE t.tender_id = :tender_id
            GROUP BY t.tender_id
        """)
        current_result = await db.execute(current_tender_query, {'tender_id': tender_id})
        current_tender = current_result.fetchone()

        if not current_tender:
            raise HTTPException(status_code=404, detail="Tender not found")

        # Build similarity query
        # Priority: 1) Same authority + similar items, 2) Same authority + same category, 3) Similar items
        similar_query = text("""
            WITH current_tender_items AS (
                SELECT item_name
                FROM epazar_items
                WHERE tender_id = :tender_id
            ),
            similar_tenders AS (
                SELECT DISTINCT ON (t.tender_id)
                    t.tender_id,
                    t.title,
                    t.contracting_authority,
                    t.category,
                    t.estimated_value_mkd,
                    t.awarded_value_mkd,
                    t.closing_date,
                    t.award_date,
                    t.status,
                    -- Similarity scoring
                    CASE
                        WHEN t.contracting_authority = :authority THEN 100
                        ELSE 0
                    END +
                    CASE
                        WHEN t.category = :category THEN 50
                        ELSE 0
                    END +
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM epazar_items i2
                            WHERE i2.tender_id = t.tender_id
                            AND EXISTS (
                                SELECT 1 FROM current_tender_items cti
                                WHERE similarity(i2.item_name, cti.item_name) > 0.3
                            )
                        ) THEN 30
                        ELSE 0
                    END as similarity_score,
                    -- Get winning offer details
                    (SELECT supplier_name FROM epazar_offers WHERE tender_id = t.tender_id AND is_winner = TRUE LIMIT 1) as winner,
                    (SELECT COUNT(*) FROM epazar_offers WHERE tender_id = t.tender_id) as num_offers,
                    -- Calculate discount
                    CASE
                        WHEN t.estimated_value_mkd > 0 AND t.awarded_value_mkd IS NOT NULL
                        THEN ROUND(((t.estimated_value_mkd - t.awarded_value_mkd) / t.estimated_value_mkd * 100)::numeric, 2)
                        ELSE NULL
                    END as discount_percent
                FROM epazar_tenders t
                WHERE t.tender_id != :tender_id
                    AND t.status IN ('awarded', 'closed')
                    AND t.awarded_value_mkd IS NOT NULL
                    AND (
                        t.contracting_authority = :authority
                        OR t.category = :category
                        OR EXISTS (
                            SELECT 1 FROM epazar_items i
                            WHERE i.tender_id = t.tender_id
                            AND EXISTS (
                                SELECT 1 FROM current_tender_items cti
                                WHERE i.item_name ILIKE '%' || cti.item_name || '%'
                                   OR cti.item_name ILIKE '%' || i.item_name || '%'
                                   OR similarity(i.item_name, cti.item_name) > 0.3
                            )
                        )
                    )
                ORDER BY t.tender_id, similarity_score DESC
            )
            SELECT * FROM similar_tenders
            WHERE similarity_score > 0
            ORDER BY similarity_score DESC, closing_date DESC NULLS LAST
            LIMIT :limit
        """)

        similar_result = await db.execute(similar_query, {
            'tender_id': tender_id,
            'authority': current_tender.contracting_authority,
            'category': current_tender.category,
            'limit': limit
        })
        similar_rows = similar_result.fetchall()

        # Build similar tenders list with similarity reasons
        similar_tenders = []
        for row in similar_rows:
            similarity_reasons = []
            if row.contracting_authority == current_tender.contracting_authority:
                similarity_reasons.append("Same buyer")
            if row.category == current_tender.category:
                similarity_reasons.append("Same category")
            if row.similarity_score >= 30:  # Has item similarity
                similarity_reasons.append("Similar items")

            similar_tenders.append({
                "tender_id": row.tender_id,
                "title": row.title,
                "contracting_authority": row.contracting_authority,
                "category": row.category,
                "estimated_value_mkd": float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
                "awarded_value_mkd": float(row.awarded_value_mkd) if row.awarded_value_mkd else None,
                "winner": row.winner,
                "discount_percent": float(row.discount_percent) if row.discount_percent else None,
                "num_offers": row.num_offers or 0,
                "closing_date": row.closing_date.isoformat() if row.closing_date else None,
                "award_date": row.award_date.isoformat() if row.award_date else None,
                "similarity_score": row.similarity_score,
                "similarity_reason": ", ".join(similarity_reasons),
                "match_reason": ", ".join(similarity_reasons)  # Alias for frontend compatibility
            })

        # Calculate insights from similar tenders
        discounts = [t["discount_percent"] for t in similar_tenders if t["discount_percent"] is not None]
        num_bidders = [t["num_offers"] for t in similar_tenders if t["num_offers"] > 0]
        awarded_values = [t["awarded_value_mkd"] for t in similar_tenders if t["awarded_value_mkd"] is not None]

        avg_discount = sum(discounts) / len(discounts) if discounts else 0
        avg_bidders = sum(num_bidders) / len(num_bidders) if num_bidders else 0

        # Estimate bid range based on current tender value and average discount
        estimated_value = float(current_tender.estimated_value_mkd) if current_tender.estimated_value_mkd else None
        recommended_min = None
        recommended_max = None

        if estimated_value and avg_discount:
            # Apply average discount range
            recommended_max = estimated_value * (1 - (avg_discount - 5) / 100)
            recommended_min = estimated_value * (1 - (avg_discount + 5) / 100)
        elif awarded_values:
            # Use historical values if available
            recommended_min = min(awarded_values)
            recommended_max = max(awarded_values)

        # Determine win probability based on market competition
        win_probability = "low"
        if avg_bidders < 3:
            win_probability = "high"
        elif avg_bidders < 5:
            win_probability = "medium"

        insights = {
            "avg_winning_discount": round(avg_discount, 2) if discounts else None,
            "avg_num_bidders": round(avg_bidders, 1) if num_bidders else None,
            "recommended_bid_range": [
                round(recommended_min, 2) if recommended_min else None,
                round(recommended_max, 2) if recommended_max else None
            ] if recommended_min and recommended_max else None,
            "win_probability_estimate": win_probability,
            "similar_tenders_count": len(similar_tenders),
            "same_buyer_count": sum(1 for t in similar_tenders if "Same buyer" in t["similarity_reason"])
        }

        return {
            "current_tender": {
                "tender_id": current_tender.tender_id,
                "title": current_tender.title,
                "contracting_authority": current_tender.contracting_authority,
                "category": current_tender.category,
                "estimated_value_mkd": float(current_tender.estimated_value_mkd) if current_tender.estimated_value_mkd else None,
                "closing_date": current_tender.closing_date.isoformat() if current_tender.closing_date else None,
                "status": current_tender.status
            },
            "similar_tenders": similar_tenders,
            "insights": insights
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar tenders for {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suppliers/{supplier_id}/stats")
async def get_epazar_supplier_stats(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed statistics for an e-Pazar supplier.

    Returns comprehensive performance metrics, trends, and category breakdown.
    """
    try:
        # Get supplier basic info
        supplier_query = text("""
            SELECT * FROM epazar_suppliers WHERE supplier_id = :supplier_id
        """)
        supplier_result = await db.execute(supplier_query, {'supplier_id': supplier_id})
        supplier = supplier_result.fetchone()

        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

        # Get detailed statistics
        stats_query = text("""
            SELECT
                COUNT(*) as total_offers,
                COUNT(*) FILTER (WHERE is_winner) as total_wins,
                AVG(total_bid_mkd) as avg_bid_amount,
                MIN(total_bid_mkd) as min_bid,
                MAX(total_bid_mkd) as max_bid,
                SUM(total_bid_mkd) FILTER (WHERE is_winner) as total_won_value,
                COUNT(DISTINCT tender_id) as unique_tenders,
                MIN(offer_date) as first_offer_date,
                MAX(offer_date) as last_offer_date
            FROM epazar_offers
            WHERE supplier_name = :supplier_name
        """)
        stats_result = await db.execute(stats_query, {'supplier_name': supplier.company_name})
        stats = stats_result.fetchone()

        # Calculate average discount vs estimated value
        discount_query = text("""
            SELECT AVG(
                CASE
                    WHEN t.estimated_value_mkd > 0
                    THEN (t.estimated_value_mkd - o.total_bid_mkd) / t.estimated_value_mkd * 100
                    ELSE 0
                END
            ) as avg_discount_percent
            FROM epazar_offers o
            JOIN epazar_tenders t ON o.tender_id = t.tender_id
            WHERE o.supplier_name = :supplier_name
              AND o.is_winner = TRUE
              AND t.estimated_value_mkd > 0
        """)
        discount_result = await db.execute(discount_query, {'supplier_name': supplier.company_name})
        avg_discount = discount_result.scalar() or 0

        # Category breakdown
        categories_query = text("""
            SELECT
                t.category,
                COUNT(*) as offers,
                COUNT(*) FILTER (WHERE o.is_winner) as wins
            FROM epazar_offers o
            JOIN epazar_tenders t ON o.tender_id = t.tender_id
            WHERE o.supplier_name = :supplier_name
              AND t.category IS NOT NULL
            GROUP BY t.category
            ORDER BY wins DESC, offers DESC
            LIMIT 10
        """)
        categories_result = await db.execute(categories_query, {'supplier_name': supplier.company_name})
        categories = [
            {"category": row.category, "offers": row.offers, "wins": row.wins}
            for row in categories_result.fetchall()
        ]

        # Monthly activity trend (last 12 months)
        trend_query = text("""
            SELECT
                date_trunc('month', o.offer_date) as month,
                COUNT(*) as offers,
                COUNT(*) FILTER (WHERE o.is_winner) as wins,
                SUM(o.total_bid_mkd) as total_bid_value
            FROM epazar_offers o
            WHERE o.supplier_name = :supplier_name
              AND o.offer_date >= NOW() - INTERVAL '12 months'
            GROUP BY date_trunc('month', o.offer_date)
            ORDER BY month
        """)
        trend_result = await db.execute(trend_query, {'supplier_name': supplier.company_name})
        monthly_trend = [
            {
                "month": row.month.strftime("%Y-%m") if row.month else None,
                "offers": row.offers,
                "wins": row.wins,
                "total_bid_value": float(row.total_bid_value) if row.total_bid_value else None
            }
            for row in trend_result.fetchall()
        ]

        # Calculate win rate trends
        win_rate_6m_query = text("""
            SELECT
                COUNT(*) FILTER (WHERE is_winner)::float / NULLIF(COUNT(*), 0) * 100 as win_rate
            FROM epazar_offers
            WHERE supplier_name = :supplier_name
              AND offer_date >= NOW() - INTERVAL '6 months'
        """)
        win_rate_6m_result = await db.execute(win_rate_6m_query, {'supplier_name': supplier.company_name})
        win_rate_6m = win_rate_6m_result.scalar() or 0

        win_rate_12m_query = text("""
            SELECT
                COUNT(*) FILTER (WHERE is_winner)::float / NULLIF(COUNT(*), 0) * 100 as win_rate
            FROM epazar_offers
            WHERE supplier_name = :supplier_name
              AND offer_date >= NOW() - INTERVAL '12 months'
        """)
        win_rate_12m_result = await db.execute(win_rate_12m_query, {'supplier_name': supplier.company_name})
        win_rate_12m = win_rate_12m_result.scalar() or 0

        # Repeat customer analysis
        repeat_query = text("""
            SELECT COUNT(DISTINCT t.contracting_authority) as unique_customers,
                   COUNT(*) FILTER (WHERE o.is_winner) as total_wins
            FROM epazar_offers o
            JOIN epazar_tenders t ON o.tender_id = t.tender_id
            WHERE o.supplier_name = :supplier_name AND o.is_winner = TRUE
        """)
        repeat_result = await db.execute(repeat_query, {'supplier_name': supplier.company_name})
        repeat_row = repeat_result.fetchone()

        total_wins = stats.total_wins or 0
        unique_customers = repeat_row.unique_customers or 0
        repeat_rate = ((total_wins - unique_customers) / total_wins * 100) if total_wins > unique_customers else 0

        return {
            "supplier_id": supplier_id,
            "company_name": supplier.company_name,
            "statistics": {
                "total_offers": stats.total_offers or 0,
                "total_wins": stats.total_wins or 0,
                "win_rate": float(supplier.win_rate) if supplier.win_rate else 0,
                "total_contract_value_mkd": float(stats.total_won_value) if stats.total_won_value else 0,
                "avg_bid_amount": float(stats.avg_bid_amount) if stats.avg_bid_amount else None,
                "min_bid": float(stats.min_bid) if stats.min_bid else None,
                "max_bid": float(stats.max_bid) if stats.max_bid else None,
                "avg_discount_percent": round(float(avg_discount), 2),
                "unique_tenders": stats.unique_tenders or 0,
                "active_since": stats.first_offer_date.isoformat() if stats.first_offer_date else None,
                "last_activity": stats.last_offer_date.isoformat() if stats.last_offer_date else None
            },
            "performance": {
                "repeat_customer_rate": round(repeat_rate, 2),
                "unique_customers": unique_customers
            },
            "trends": {
                "win_rate_6m": round(float(win_rate_6m), 2),
                "win_rate_12m": round(float(win_rate_12m), 2),
                "activity_trend": "stable"  # Could calculate more precisely
            },
            "categories": categories,
            "monthly_trend": monthly_trend
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stats for supplier {supplier_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PRICE SEARCH - Returns matching products for autocomplete
# ============================================================================

@router.get("/price-search", dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
async def search_products_for_price(
    q: str = Query(..., min_length=2, description="Search query"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for distinct products matching query - for autocomplete/suggestions.
    Returns list of product names with their price ranges.
    """
    try:
        search_variants = get_search_variants(q)

        if len(search_variants) == 1:
            search_condition = "item_subject ILIKE :search"
            params = {'search': f"%{search_variants[0]}%"}
        else:
            search_condition = "(item_subject ILIKE :search_latin OR item_subject ILIKE :search_cyrillic)"
            params = {
                'search_latin': f"%{search_variants[0]}%",
                'search_cyrillic': f"%{search_variants[1]}%"
            }

        # Get distinct products with price stats from evaluation data
        query = text(f"""
            SELECT
                TRIM(item_subject) as product_name,
                COUNT(*) as count,
                MIN(unit_price_without_vat) FILTER (WHERE unit_price_without_vat > 0) as min_price,
                MAX(unit_price_without_vat) FILTER (WHERE unit_price_without_vat > 0) as max_price,
                AVG(unit_price_without_vat) FILTER (WHERE unit_price_without_vat > 0) as avg_price
            FROM epazar_item_evaluations
            WHERE {search_condition}
              AND item_subject IS NOT NULL
              AND LENGTH(TRIM(item_subject)) >= 3
            GROUP BY TRIM(item_subject)
            HAVING COUNT(*) >= 1
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)

        result = await db.execute(query, params)
        products = []
        for row in result.fetchall():
            if row.product_name and len(row.product_name.strip()) >= 3:
                products.append({
                    "name": row.product_name,
                    "count": row.count,
                    "min_price": round(float(row.min_price), 2) if row.min_price else None,
                    "max_price": round(float(row.max_price), 2) if row.max_price else None,
                    "avg_price": round(float(row.avg_price), 2) if row.avg_price else None,
                })

        return {"query": q, "products": products, "total": len(products)}

    except Exception as e:
        logger.error(f"Error in price search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PRICE INTELLIGENCE ENDPOINT
# ============================================================================

@router.get("/price-intelligence", dependencies=[Depends(require_module(ModuleName.ANALYTICS))])
async def get_price_intelligence(
    search: str = Query(..., description="Item name to search"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive price intelligence for e-Pazar items.

    Returns:
    - Price statistics from estimated unit prices
    - Competition metrics from offers on tenders containing the item
    - Recommended bid range (5-10% below average winning bid)
    - Trend and discount data where available

    Supports bilingual search (Latin and Cyrillic).

    Example usage:
    GET /api/epazar/price-intelligence?search=toner
    GET /api/epazar/price-intelligence?search=хартија
    """
    try:
        # Get bilingual search variants
        search_variants = get_search_variants(search)

        # Build search condition for bilingual support
        if len(search_variants) == 1:
            search_condition = "i.item_name ILIKE :search"
            params = {'search': f"%{search_variants[0]}%"}
        else:
            search_condition = "(i.item_name ILIKE :search_latin OR i.item_name ILIKE :search_cyrillic)"
            params = {
                'search_latin': f"%{search_variants[0]}%",
                'search_cyrillic': f"%{search_variants[1]}%"
            }

        category_filter = ""
        if category:
            category_filter = " AND t.category ILIKE :category"
            params['category'] = f"%{category}%"

        # Get item-level price stats from estimated prices
        item_stats_query = text(f"""
            SELECT
                COUNT(DISTINCT i.item_id) as total_items,
                COUNT(DISTINCT t.tender_id) as total_tenders,
                SUM(i.quantity) as total_quantity,
                MIN(i.estimated_unit_price_mkd) FILTER (WHERE i.estimated_unit_price_mkd > 0) as min_estimated,
                MAX(i.estimated_unit_price_mkd) FILTER (WHERE i.estimated_unit_price_mkd > 0) as max_estimated,
                AVG(i.estimated_unit_price_mkd) FILTER (WHERE i.estimated_unit_price_mkd > 0) as avg_estimated,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY i.estimated_unit_price_mkd)
                    FILTER (WHERE i.estimated_unit_price_mkd > 0) as median_estimated,
                MIN(i.unit) as common_unit
            FROM epazar_items i
            JOIN epazar_tenders t ON i.tender_id = t.tender_id
            WHERE {search_condition}
              {category_filter}
        """)

        result = await db.execute(item_stats_query, params)
        item_stats = result.fetchone()

        if not item_stats or item_stats.total_items == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No items found for '{search}'. Try searching in Cyrillic (e.g., 'тонер' instead of 'toner')."
            )

        # Get competition data from offers on tenders that contain these items
        competition_query = text(f"""
            WITH tender_items AS (
                SELECT DISTINCT t.tender_id
                FROM epazar_items i
                JOIN epazar_tenders t ON i.tender_id = t.tender_id
                WHERE {search_condition}
                  {category_filter}
            ),
            tender_offers AS (
                SELECT
                    o.tender_id,
                    COUNT(*) as offer_count,
                    MIN(o.total_bid_mkd) as min_bid,
                    MAX(o.total_bid_mkd) as max_bid,
                    AVG(o.total_bid_mkd) as avg_bid,
                    MIN(o.total_bid_mkd) FILTER (WHERE o.is_winner = TRUE) as winning_bid
                FROM epazar_offers o
                INNER JOIN tender_items ti ON o.tender_id = ti.tender_id
                WHERE o.total_bid_mkd > 0
                GROUP BY o.tender_id
            )
            SELECT
                COUNT(*) as tenders_with_offers,
                SUM(offer_count) as total_offers,
                AVG(offer_count) as avg_offers_per_tender,
                AVG(winning_bid / NULLIF(avg_bid, 0)) as avg_discount_ratio,
                COUNT(*) FILTER (WHERE winning_bid IS NOT NULL) as tenders_with_winner
            FROM tender_offers
        """)

        comp_result = await db.execute(competition_query, params)
        comp_stats = comp_result.fetchone()

        # Determine competition level
        avg_offers = float(comp_stats.avg_offers_per_tender) if comp_stats.avg_offers_per_tender else 1
        if avg_offers >= 4:
            competition_level = "high"
        elif avg_offers >= 2:
            competition_level = "medium"
        else:
            competition_level = "low"

        # Calculate typical discount (how much winners bid below average)
        typical_discount_percent = 0.0
        if comp_stats.avg_discount_ratio:
            typical_discount_percent = round((1 - float(comp_stats.avg_discount_ratio)) * 100, 1)

        # Query ACTUAL winning prices from evaluation reports (GOLD data)
        # This is the real price data extracted from PDF evaluation reports
        if len(search_variants) == 1:
            eval_search_condition = "e.item_subject ILIKE :search"
        else:
            eval_search_condition = "(e.item_subject ILIKE :search_latin OR e.item_subject ILIKE :search_cyrillic)"

        actual_prices_query = text(f"""
            SELECT
                COUNT(*) as evaluation_count,
                MIN(e.unit_price_without_vat) FILTER (WHERE e.unit_price_without_vat > 0) as actual_min,
                MAX(e.unit_price_without_vat) FILTER (WHERE e.unit_price_without_vat > 0) as actual_max,
                AVG(e.unit_price_without_vat) FILTER (WHERE e.unit_price_without_vat > 0) as actual_avg,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY e.unit_price_without_vat)
                    FILTER (WHERE e.unit_price_without_vat > 0) as actual_p25,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY e.unit_price_without_vat)
                    FILTER (WHERE e.unit_price_without_vat > 0) as actual_p75
            FROM epazar_item_evaluations e
            WHERE {eval_search_condition}
        """)

        eval_result = await db.execute(actual_prices_query, params)
        eval_stats = eval_result.fetchone()

        # Get winning brands from evaluation data (filter out garbage from bad PDF parsing)
        brands_query = text(f"""
            SELECT
                e.offered_brand,
                COUNT(*) as win_count,
                AVG(e.unit_price_without_vat) as avg_price
            FROM epazar_item_evaluations e
            WHERE e.offered_brand IS NOT NULL
              AND e.offered_brand != ''
              AND LENGTH(e.offered_brand) >= 2
              AND LENGTH(e.offered_brand) <= 50
              AND e.offered_brand !~ '[:\)\(\[\]0-9]'
              AND e.offered_brand NOT ILIKE '%производот нема%'
              AND e.unit_price_without_vat > 0
              AND {eval_search_condition}
            GROUP BY e.offered_brand
            ORDER BY win_count DESC
            LIMIT 5
        """)

        brands_result = await db.execute(brands_query, params)
        winning_brands = [
            {"brand": row.offered_brand, "wins": row.win_count, "avg_price": float(row.avg_price) if row.avg_price else None}
            for row in brands_result.fetchall()
            if row.offered_brand and len(row.offered_brand.strip()) >= 2
        ]

        # Use ACTUAL prices from evaluations if available, otherwise fall back to estimated
        has_actual_prices = eval_stats and eval_stats.evaluation_count and eval_stats.evaluation_count > 0
        if has_actual_prices:
            min_price = float(eval_stats.actual_min) if eval_stats.actual_min else 0
            max_price = float(eval_stats.actual_max) if eval_stats.actual_max else 0
            avg_price = float(eval_stats.actual_avg) if eval_stats.actual_avg else 0
            median_price = avg_price  # Use avg as median approximation
            p25_price = float(eval_stats.actual_p25) if eval_stats.actual_p25 else min_price
            p75_price = float(eval_stats.actual_p75) if eval_stats.actual_p75 else max_price
        else:
            # Fall back to estimated prices
            min_price = float(item_stats.min_estimated) if item_stats.min_estimated else 0
            max_price = float(item_stats.max_estimated) if item_stats.max_estimated else 0
            avg_price = float(item_stats.avg_estimated) if item_stats.avg_estimated else 0
            median_price = float(item_stats.median_estimated) if item_stats.median_estimated else avg_price
            p25_price = min_price
            p75_price = max_price

        # Calculate recommended bid (apply typical discount to estimated price)
        discount_factor = 1 - (typical_discount_percent / 100) if typical_discount_percent > 0 else 0.92
        recommended_bid_low = round(avg_price * (discount_factor - 0.05), 2)
        recommended_bid_high = round(avg_price * discount_factor, 2)

        # Get sample item name from actual data (use condition without table alias)
        if len(search_variants) == 1:
            sample_condition = "item_name ILIKE :search"
        else:
            sample_condition = "(item_name ILIKE :search_latin OR item_name ILIKE :search_cyrillic)"
        sample_query = text(f"""
            SELECT item_name
            FROM epazar_items
            WHERE {sample_condition}
            LIMIT 1
        """)
        sample_result = await db.execute(sample_query, params)
        sample_row = sample_result.fetchone()
        item_name = sample_row.item_name if sample_row else search

        # Return flat structure that matches frontend PriceIntelligence interface
        return {
            # Frontend expected fields (flat structure)
            "product_name": item_name,
            "recommended_bid_min_mkd": round(p25_price, 2) if has_actual_prices else recommended_bid_low,
            "recommended_bid_max_mkd": round(p75_price, 2) if has_actual_prices else recommended_bid_high,
            "market_min_mkd": round(min_price, 2),
            "market_max_mkd": round(max_price, 2),
            "market_avg_mkd": round(avg_price, 2),
            "trend": "stable",  # TODO: add trend analysis when more historical data available
            "trend_percentage": typical_discount_percent if typical_discount_percent else None,
            "competition_level": competition_level,
            "sample_size": item_stats.total_items,
            # Additional fields for API consumers
            "unit": item_stats.common_unit,
            "median_price": round(median_price, 2),
            "typical_discount_percent": typical_discount_percent,
            "total_tenders": item_stats.total_tenders,
            "total_quantity": float(item_stats.total_quantity) if item_stats.total_quantity else 0,
            # NEW: Actual prices from evaluation reports (GOLD data)
            "actual_prices": {
                "has_data": has_actual_prices,
                "sample_size": eval_stats.evaluation_count if eval_stats else 0,
                "min": round(float(eval_stats.actual_min), 2) if eval_stats and eval_stats.actual_min else None,
                "avg": round(float(eval_stats.actual_avg), 2) if eval_stats and eval_stats.actual_avg else None,
                "max": round(float(eval_stats.actual_max), 2) if eval_stats and eval_stats.actual_max else None,
                "p25": round(float(eval_stats.actual_p25), 2) if eval_stats and eval_stats.actual_p25 else None,
                "p75": round(float(eval_stats.actual_p75), 2) if eval_stats and eval_stats.actual_p75 else None,
            },
            # NEW: Winning brands from evaluation data
            "winning_brands": winning_brands,
            # NEW: AI recommendation message
            "ai_recommendation": f"Препорачана цена: {round(p25_price, 0):.0f}-{round(p75_price, 0):.0f} МКД. " +
                (f"Најчест победнички бренд: {winning_brands[0]['brand']}. " if winning_brands else "") +
                f"Базирано на {eval_stats.evaluation_count if eval_stats else 0} победнички понуди." if has_actual_prices else
                f"Препорачана цена: {recommended_bid_low:.0f}-{recommended_bid_high:.0f} МКД (базирано на проценки).",
            "data_points": {
                "items_analyzed": item_stats.total_items,
                "tenders_with_offers": comp_stats.tenders_with_offers or 0,
                "total_offers": comp_stats.total_offers or 0,
                "avg_offers_per_tender": round(avg_offers, 1),
                "tenders_with_winner": comp_stats.tenders_with_winner or 0,
                "evaluation_records": eval_stats.evaluation_count if eval_stats else 0
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price intelligence for '{search}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUPPLIER RANKINGS ENDPOINT
# ============================================================================

@router.get("/supplier-rankings", dependencies=[Depends(require_module(ModuleName.COMPETITOR_TRACKING))])
async def get_supplier_rankings(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Number of results (default 20)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get supplier rankings for e-Pazar marketplace.

    Returns top suppliers ranked by total wins, with performance metrics including:
    - Total wins and offers
    - Win rate percentage
    - Total contract value
    - Average discount vs estimated value
    - Main categories they operate in
    - Top buyers they work with
    """
    try:
        # Build WHERE clause for category filter
        category_filter = ""
        params = {'limit': limit}

        if category:
            category_filter = "AND t.category ILIKE :category"
            params['category'] = f"%{category}%"

        # Main query to get supplier rankings
        rankings_query = text(f"""
            WITH supplier_wins AS (
                SELECT
                    o.supplier_name,
                    COUNT(*) as total_offers,
                    COUNT(*) FILTER (WHERE o.is_winner = TRUE) as total_wins,
                    CASE
                        WHEN COUNT(*) > 0
                        THEN (COUNT(*) FILTER (WHERE o.is_winner = TRUE)::NUMERIC / COUNT(*)::NUMERIC * 100)
                        ELSE 0
                    END as win_rate,
                    COALESCE(SUM(o.total_bid_mkd) FILTER (WHERE o.is_winner = TRUE), 0) as total_contract_value_mkd,
                    -- Calculate average discount (estimated - winning bid) / estimated * 100
                    AVG(
                        CASE
                            WHEN o.is_winner = TRUE AND t.estimated_value_mkd > 0
                            THEN ((t.estimated_value_mkd - o.total_bid_mkd) / t.estimated_value_mkd * 100)
                            ELSE NULL
                        END
                    ) as avg_discount_percent
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE 1=1 {category_filter}
                GROUP BY o.supplier_name
                HAVING COUNT(*) FILTER (WHERE o.is_winner = TRUE) > 0
            ),
            supplier_categories AS (
                SELECT
                    o.supplier_name,
                    array_agg(DISTINCT t.category ORDER BY t.category)
                        FILTER (WHERE t.category IS NOT NULL) as categories,
                    -- Get top categories by win count
                    (
                        SELECT json_agg(cat_stats ORDER BY wins DESC)
                        FROM (
                            SELECT
                                t2.category,
                                COUNT(*) FILTER (WHERE o2.is_winner = TRUE) as wins
                            FROM epazar_offers o2
                            JOIN epazar_tenders t2 ON o2.tender_id = t2.tender_id
                            WHERE o2.supplier_name = o.supplier_name
                                AND o2.is_winner = TRUE
                                AND t2.category IS NOT NULL
                            GROUP BY t2.category
                            ORDER BY wins DESC
                            LIMIT 3
                        ) cat_stats
                    ) as top_categories_json
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE 1=1 {category_filter}
                GROUP BY o.supplier_name
            ),
            supplier_buyers AS (
                SELECT
                    o.supplier_name,
                    -- Get top buyers by contract count
                    (
                        SELECT json_agg(buyer_stats ORDER BY contracts DESC)
                        FROM (
                            SELECT
                                t2.contracting_authority as buyer,
                                COUNT(*) as contracts,
                                COALESCE(SUM(o2.total_bid_mkd), 0) as total_value
                            FROM epazar_offers o2
                            JOIN epazar_tenders t2 ON o2.tender_id = t2.tender_id
                            WHERE o2.supplier_name = o.supplier_name
                                AND o2.is_winner = TRUE
                                AND t2.contracting_authority IS NOT NULL
                            GROUP BY t2.contracting_authority
                            ORDER BY contracts DESC
                            LIMIT 5
                        ) buyer_stats
                    ) as top_buyers_json
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE 1=1 {category_filter}
                GROUP BY o.supplier_name
            )
            SELECT
                ROW_NUMBER() OVER (ORDER BY sw.total_wins DESC, sw.total_contract_value_mkd DESC) as rank,
                sw.supplier_name,
                sw.total_wins,
                sw.total_offers,
                sw.win_rate,
                sw.total_contract_value_mkd,
                sw.avg_discount_percent,
                COALESCE(sc.categories, ARRAY[]::text[]) as main_categories,
                COALESCE(sb.top_buyers_json, '[]'::json) as top_buyers_json
            FROM supplier_wins sw
            LEFT JOIN supplier_categories sc ON sw.supplier_name = sc.supplier_name
            LEFT JOIN supplier_buyers sb ON sw.supplier_name = sb.supplier_name
            ORDER BY sw.total_wins DESC, sw.total_contract_value_mkd DESC
            LIMIT :limit
        """)

        result = await db.execute(rankings_query, params)
        rankings_rows = result.fetchall()

        # Build rankings response
        rankings = []
        for row in rankings_rows:
            # Parse top buyers JSON
            top_buyers_data = row.top_buyers_json if row.top_buyers_json else []
            top_buyers = [buyer['buyer'] for buyer in top_buyers_data] if top_buyers_data else []

            rankings.append({
                "rank": row.rank,
                "supplier_id": row.supplier_name,  # Use name as ID (no UUID in data)
                "company_name": row.supplier_name,  # Alias for frontend compatibility
                "supplier_name": row.supplier_name,  # Keep for backwards compatibility
                "total_wins": row.total_wins,
                "total_offers": row.total_offers,
                "win_rate": round(float(row.win_rate), 1),
                "total_contract_value_mkd": float(row.total_contract_value_mkd),
                "avg_discount_percent": round(float(row.avg_discount_percent), 1) if row.avg_discount_percent else 0.0,
                "main_categories": list(row.main_categories) if row.main_categories else [],
                "top_buyers": top_buyers
            })

        # Calculate market stats
        market_stats_query = text(f"""
            SELECT
                COUNT(DISTINCT supplier_name) as total_suppliers,
                AVG(
                    CASE
                        WHEN total_offers > 0
                        THEN (total_wins::NUMERIC / total_offers::NUMERIC * 100)
                        ELSE 0
                    END
                ) as avg_win_rate,
                COALESCE(SUM(total_contract_value), 0) as total_market_value_mkd
            FROM (
                SELECT
                    o.supplier_name,
                    COUNT(*) as total_offers,
                    COUNT(*) FILTER (WHERE o.is_winner = TRUE) as total_wins,
                    COALESCE(SUM(o.total_bid_mkd) FILTER (WHERE o.is_winner = TRUE), 0) as total_contract_value
                FROM epazar_offers o
                JOIN epazar_tenders t ON o.tender_id = t.tender_id
                WHERE 1=1 {category_filter}
                GROUP BY o.supplier_name
                HAVING COUNT(*) FILTER (WHERE o.is_winner = TRUE) > 0
            ) supplier_stats
        """)

        market_result = await db.execute(market_stats_query, params)
        market_row = market_result.fetchone()

        market_stats = {
            "total_suppliers": market_row.total_suppliers or 0,
            "avg_win_rate": round(float(market_row.avg_win_rate), 1) if market_row.avg_win_rate else 0.0,
            "total_market_value_mkd": float(market_row.total_market_value_mkd) if market_row.total_market_value_mkd else 0.0
        }

        return {
            "rankings": rankings,
            "market_stats": market_stats
        }

    except Exception as e:
        logger.error(f"Error fetching supplier rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
