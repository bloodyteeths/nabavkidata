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
            conditions.append("""
                (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, ''))
                @@ plainto_tsquery('simple', :search)
                OR title ILIKE :search_like
                OR description ILIKE :search_like)
            """)
            params['search'] = search
            params['search_like'] = f"%{search}%"

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
            conditions.append("""
                (item_name ILIKE :search
                OR item_description ILIKE :search
                OR cpv_code ILIKE :search)
            """)
            params['search'] = f"%{search}%"

        if cpv_code:
            conditions.append("cpv_code LIKE :cpv_code")
            params['cpv_code'] = f"{cpv_code}%"

        if min_price is not None:
            conditions.append("estimated_unit_price_mkd >= :min_price")
            params['min_price'] = min_price

        if max_price is not None:
            conditions.append("estimated_unit_price_mkd <= :max_price")
            params['max_price'] = max_price

        if unit:
            conditions.append("unit ILIKE :unit")
            params['unit'] = f"%{unit}%"

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        # Validate sort field
        valid_sort_fields = ['item_name', 'estimated_unit_price_mkd', 'quantity', 'estimated_total_price_mkd', 'cpv_code']
        if sort_by not in valid_sort_fields:
            sort_by = 'item_name'

        sort_direction = 'DESC' if sort_order.lower() == 'desc' else 'ASC'

        # Get total count
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM epazar_items WHERE 1=1 {where_clause}"),
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
                ORDER BY {sort_by} {sort_direction} NULLS LAST
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
                    (SELECT COALESCE(SUM(estimated_value_mkd), 0) FROM epazar_tenders) as total_value_mkd,
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

@router.post("/tenders/{tender_id}/summarize")
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
        }

        # Call AI service (using existing RAG infrastructure)
        from ai.rag_query import generate_tender_summary

        summary = await generate_tender_summary(context)

        return {
            'tender_id': tender_id,
            'summary': summary,
            'items_count': len(items),
            'offers_count': len(offers),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing tender {tender_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suppliers/{supplier_id}/analyze")
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
