"""
SEO API endpoints — lightweight, public, cached.
Returns minimal data for Next.js generateMetadata() and JSON-LD.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional
import logging

from database import get_db
from models import Tender, Supplier, ProcuringEntity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/seo", tags=["seo"])


@router.get("/tender/{tender_id:path}")
async def seo_tender(tender_id: str, db: AsyncSession = Depends(get_db)):
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")
    result = await db.execute(
        select(
            Tender.tender_id,
            Tender.title,
            Tender.description,
            Tender.procuring_entity,
            Tender.estimated_value_mkd,
            Tender.actual_value_mkd,
            Tender.status,
            Tender.closing_date,
            Tender.publication_date,
            Tender.opening_date,
            Tender.cpv_code,
            Tender.winner,
            Tender.procedure_type,
            Tender.category,
        ).where(Tender.tender_id == tender_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Tender not found")

    return {
        "tender_id": row.tender_id,
        "title": row.title,
        "description": row.description,
        "procuring_entity": row.procuring_entity,
        "estimated_value_mkd": float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
        "actual_value_mkd": float(row.actual_value_mkd) if row.actual_value_mkd else None,
        "status": row.status,
        "closing_date": str(row.closing_date) if row.closing_date else None,
        "publication_date": str(row.publication_date) if row.publication_date else None,
        "opening_date": str(row.opening_date) if row.opening_date else None,
        "cpv_code": row.cpv_code,
        "winner": row.winner,
        "procedure_type": row.procedure_type,
        "category": row.category,
    }


@router.get("/supplier/{supplier_id}")
async def seo_supplier(supplier_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Supplier.supplier_id,
            Supplier.company_name,
            Supplier.tax_id,
            Supplier.city,
            Supplier.total_bids,
            Supplier.total_wins,
            Supplier.win_rate,
            Supplier.total_contract_value_mkd,
        ).where(Supplier.supplier_id == supplier_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return {
        "supplier_id": str(row.supplier_id),
        "company_name": row.company_name,
        "tax_id": row.tax_id,
        "city": row.city,
        "country": "MK",
        "total_bids": row.total_bids,
        "total_wins": row.total_wins,
        "win_rate": float(row.win_rate) if row.win_rate else None,
        "total_value_won_mkd": float(row.total_contract_value_mkd) if row.total_contract_value_mkd else None,
    }


@router.get("/sitemap/tenders")
async def sitemap_tenders(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50000, le=50000),
    db: AsyncSession = Depends(get_db),
):
    """Return tender IDs and updated_at for sitemap generation, paginated at 50K."""
    offset = (page - 1) * limit
    result = await db.execute(
        select(Tender.tender_id, Tender.updated_at, Tender.status)
        .order_by(Tender.tender_id)
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    return {
        "page": page,
        "count": len(rows),
        "items": [
            {
                "tender_id": r.tender_id,
                "updated_at": str(r.updated_at) if r.updated_at else None,
                "status": r.status,
            }
            for r in rows
        ],
    }


@router.get("/sitemap/tenders/count")
async def sitemap_tenders_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(Tender.tender_id)))
    total = result.scalar()
    return {"total": total, "pages": (total + 49999) // 50000}


@router.get("/sitemap/suppliers")
async def sitemap_suppliers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50000, le=50000),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    result = await db.execute(
        select(Supplier.supplier_id, Supplier.company_name)
        .order_by(Supplier.supplier_id)
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    return {
        "page": page,
        "count": len(rows),
        "items": [
            {"supplier_id": str(r.supplier_id), "company_name": r.company_name}
            for r in rows
        ],
    }


@router.get("/sitemap/suppliers/count")
async def sitemap_suppliers_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(Supplier.supplier_id)))
    total = result.scalar()
    return {"total": total, "pages": (total + 49999) // 50000}


@router.get("/entity/{entity_id}")
async def seo_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            ProcuringEntity.entity_id,
            ProcuringEntity.entity_name,
            ProcuringEntity.entity_type,
            ProcuringEntity.category,
            ProcuringEntity.city,
            ProcuringEntity.total_tenders,
            ProcuringEntity.total_value_mkd,
        ).where(ProcuringEntity.entity_id == entity_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Entity not found")

    return {
        "entity_id": str(row.entity_id),
        "entity_name": row.entity_name,
        "entity_type": row.entity_type,
        "category": row.category,
        "city": row.city,
        "total_tenders": row.total_tenders or 0,
        "total_value_mkd": float(row.total_value_mkd) if row.total_value_mkd else None,
    }


@router.get("/entity/{entity_id}/tenders")
async def seo_entity_tenders(
    entity_id: str,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    ent = await db.execute(
        select(ProcuringEntity.entity_name).where(ProcuringEntity.entity_id == entity_id)
    )
    name_row = ent.first()
    if not name_row:
        raise HTTPException(status_code=404, detail="Entity not found")

    result = await db.execute(
        select(
            Tender.tender_id,
            Tender.title,
            Tender.status,
            Tender.estimated_value_mkd,
            Tender.closing_date,
            Tender.winner,
        )
        .where(Tender.procuring_entity == name_row.entity_name)
        .order_by(Tender.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return {
        "entity_name": name_row.entity_name,
        "tenders": [
            {
                "tender_id": r.tender_id,
                "title": r.title,
                "status": r.status,
                "estimated_value_mkd": float(r.estimated_value_mkd) if r.estimated_value_mkd else None,
                "closing_date": str(r.closing_date) if r.closing_date else None,
                "winner": r.winner,
            }
            for r in rows
        ],
    }


@router.get("/sitemap/entities")
async def sitemap_entities(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50000, le=50000),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    result = await db.execute(
        select(ProcuringEntity.entity_id, ProcuringEntity.entity_name)
        .order_by(ProcuringEntity.entity_id)
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    return {
        "page": page,
        "count": len(rows),
        "items": [
            {"entity_id": str(r.entity_id), "entity_name": r.entity_name}
            for r in rows
        ],
    }


@router.get("/sitemap/entities/count")
async def sitemap_entities_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(ProcuringEntity.entity_id)))
    total = result.scalar()
    return {"total": total, "pages": (total + 49999) // 50000}


# ── Award endpoints (awarded tenders with a winner) ──────────────────────────

@router.get("/award/{tender_id:path}")
async def seo_award(tender_id: str, db: AsyncSession = Depends(get_db)):
    tender_id = tender_id.replace("%2F", "/").replace("%2f", "/")
    result = await db.execute(
        select(
            Tender.tender_id,
            Tender.title,
            Tender.description,
            Tender.procuring_entity,
            Tender.estimated_value_mkd,
            Tender.actual_value_mkd,
            Tender.winner,
            Tender.num_bidders,
            Tender.publication_date,
            Tender.closing_date,
            Tender.cpv_code,
            Tender.procedure_type,
            Tender.category,
        ).where(
            Tender.tender_id == tender_id,
            Tender.status == "awarded",
            Tender.winner.isnot(None),
            Tender.winner != "",
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Award not found")

    return {
        "tender_id": row.tender_id,
        "title": row.title,
        "description": row.description,
        "procuring_entity": row.procuring_entity,
        "estimated_value_mkd": float(row.estimated_value_mkd) if row.estimated_value_mkd else None,
        "actual_value_mkd": float(row.actual_value_mkd) if row.actual_value_mkd else None,
        "winner": row.winner,
        "num_bidders": row.num_bidders,
        "publication_date": str(row.publication_date) if row.publication_date else None,
        "closing_date": str(row.closing_date) if row.closing_date else None,
        "cpv_code": row.cpv_code,
        "procedure_type": row.procedure_type,
        "category": row.category,
    }


@router.get("/sitemap/awards")
async def sitemap_awards(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50000, le=50000),
    db: AsyncSession = Depends(get_db),
):
    """Return awarded tender IDs for sitemap generation, paginated at 50K."""
    offset = (page - 1) * limit
    result = await db.execute(
        select(Tender.tender_id, Tender.updated_at)
        .where(
            Tender.status == "awarded",
            Tender.winner.isnot(None),
            Tender.winner != "",
        )
        .order_by(Tender.publication_date.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    return {
        "page": page,
        "count": len(rows),
        "items": [
            {
                "tender_id": r.tender_id,
                "updated_at": str(r.updated_at) if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.get("/sitemap/awards/count")
async def sitemap_awards_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(func.count(Tender.tender_id)).where(
            Tender.status == "awarded",
            Tender.winner.isnot(None),
            Tender.winner != "",
        )
    )
    total = result.scalar()
    return {"total": total, "pages": (total + 49999) // 50000}
