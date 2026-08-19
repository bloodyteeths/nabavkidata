"""
KG (Kyrgyzstan) Tenders API — Phase 2

Reads from kg.tenders schema (separate from MK public.tenders).
Serves ZA Invest and future KG-side users.

Endpoints under /api/kg prefix.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from db_pool import get_asyncpg_pool
from api.corruption import build_bilingual_search_condition_ru, latin_to_russian

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/kg",
    tags=["KG Tenders"],
)


class KGTender(BaseModel):
    tender_id: str
    tender_number: Optional[str] = None
    title: Optional[str] = None
    buyer_name: Optional[str] = None
    tender_type: Optional[str] = None
    procurement_method: Optional[str] = None
    amount_kgs: Optional[float] = None
    date_published: Optional[datetime] = None
    date_contest: Optional[datetime] = None
    status: Optional[str] = None
    source: Optional[str] = None


class KGTenderList(BaseModel):
    tenders: List[KGTender]
    total: int
    limit: int
    offset: int


@router.get("/tenders", response_model=KGTenderList)
async def list_kg_tenders(
    search: Optional[str] = Query(None, description="Bilingual search (Latin or Cyrillic)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_amount: Optional[float] = Query(None, description="Minimum amount in KGS"),
    max_amount: Optional[float] = Query(None, description="Maximum amount in KGS"),
    days_ahead: int = Query(30, description="Deadline within N days"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List KG tenders with bilingual Latin/Russian search + filters."""
    pool = await get_asyncpg_pool()

    where = ["date_contest > NOW()"]
    params: list = []
    param_num = 0

    if search:
        # Search across title + description + buyer_name (bilingual)
        param_num += 1
        title_cond, title_sp = build_bilingual_search_condition_ru("title", search, param_num)
        params.extend(title_sp)
        param_num += len(title_sp) - 1

        param_num += 1
        desc_cond, desc_sp = build_bilingual_search_condition_ru("description", search, param_num)
        params.extend(desc_sp)
        param_num += len(desc_sp) - 1

        param_num += 1
        buyer_cond, buyer_sp = build_bilingual_search_condition_ru("buyer_name", search, param_num)
        params.extend(buyer_sp)
        param_num += len(buyer_sp) - 1

        where.append(f"({title_cond} OR {desc_cond} OR {buyer_cond})")

    if status:
        param_num += 1
        where.append(f"status = ${param_num}")
        params.append(status)

    if min_amount is not None:
        param_num += 1
        where.append(f"amount_kgs >= ${param_num}")
        params.append(min_amount)

    if max_amount is not None:
        param_num += 1
        where.append(f"amount_kgs <= ${param_num}")
        params.append(max_amount)

    if days_ahead:
        param_num += 1
        where.append(f"date_contest <= NOW() + INTERVAL '{int(days_ahead)} days'")

    where_sql = " AND ".join(where) if where else "TRUE"

    sql_count = f"SELECT COUNT(*) FROM kg.tenders WHERE {where_sql}"
    sql_data = f"""
        SELECT tender_id, tender_number, title, buyer_name, tender_type,
               procurement_method, amount_kgs, date_published, date_contest,
               status, source
        FROM kg.tenders
        WHERE {where_sql}
        ORDER BY date_contest ASC NULLS LAST
        LIMIT {int(limit)} OFFSET {int(offset)}
    """

    async with pool.acquire() as conn:
        total = await conn.fetchval(sql_count, *params)
        rows = await conn.fetch(sql_data, *params)

    return KGTenderList(
        tenders=[KGTender(**dict(r)) for r in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/tenders/{tender_id}", response_model=KGTender)
async def get_kg_tender(tender_id: str):
    """Get a single KG tender by tender_id."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT tender_id, tender_number, title, buyer_name, tender_type,
                   procurement_method, amount_kgs, date_published, date_contest,
                   status, source
            FROM kg.tenders WHERE tender_id = $1
            """,
            tender_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Tender not found")
    return KGTender(**dict(row))


@router.get("/stats")
async def kg_stats():
    """Basic KG DB stats — for platform health check + ZA Invest sanity."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM kg.tenders")
        active = await conn.fetchval("SELECT COUNT(*) FROM kg.tenders WHERE date_contest > NOW()")
        newest = await conn.fetchval("SELECT MAX(first_seen_at) FROM kg.tenders")
        by_source = await conn.fetch(
            "SELECT source, COUNT(*) as n FROM kg.tenders GROUP BY source ORDER BY n DESC"
        )
    return {
        "total": total,
        "active": active,
        "newest_first_seen_at": newest,
        "by_source": [{"source": r["source"], "count": r["n"]} for r in by_source],
    }
