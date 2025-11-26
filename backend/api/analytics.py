"""
Analytics API endpoints
Aggregated statistics and trends
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date, timedelta

from database import get_db
from models import Tender, ProcuringEntity

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class TenderStatsResponse(BaseModel):
    """Overall tender statistics"""
    total_tenders: int
    tenders_by_status: dict
    tenders_by_category: dict
    tenders_by_procedure_type: dict
    total_estimated_value_mkd: Optional[float]
    avg_estimated_value_mkd: Optional[float]
    tenders_last_7_days: int
    tenders_last_30_days: int


class EntityStatsResponse(BaseModel):
    """Entity statistics"""
    total_entities: int
    entities_by_city: dict
    top_entities_by_tenders: List[dict]


class TimeSeriesDataPoint(BaseModel):
    """Single data point in time series"""
    date: str
    count: int
    total_value_mkd: Optional[float] = None


class TrendsResponse(BaseModel):
    """Trend data response"""
    period: str
    tenders_over_time: List[TimeSeriesDataPoint]
    total_tenders: int
    total_value_mkd: Optional[float]


class ScrapeHistoryResponse(BaseModel):
    """Scrape run history"""
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    mode: str
    category: Optional[str]
    tenders_found: int
    tenders_new: int
    tenders_updated: int
    tenders_unchanged: int
    errors: int
    duration_seconds: Optional[float]
    status: str


class ScrapeHistoryListResponse(BaseModel):
    """List of scrape history records"""
    total: int
    items: List[ScrapeHistoryResponse]


# ============================================================================
# TENDER STATISTICS
# ============================================================================

@router.get("/tenders/stats", response_model=TenderStatsResponse)
async def get_tender_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall tender statistics

    Returns aggregated stats about all tenders in the database
    """
    # Total tenders
    total = await db.scalar(select(func.count()).select_from(Tender))

    # By status
    status_query = select(
        Tender.status,
        func.count(Tender.tender_id).label('count')
    ).group_by(Tender.status)
    status_result = await db.execute(status_query)
    by_status = {row.status or 'unknown': row.count for row in status_result}

    # By category
    category_query = select(
        Tender.category,
        func.count(Tender.tender_id).label('count')
    ).group_by(Tender.category)
    category_result = await db.execute(category_query)
    by_category = {row.category or 'unknown': row.count for row in category_result}

    # By procedure type
    procedure_query = select(
        Tender.procedure_type,
        func.count(Tender.tender_id).label('count')
    ).group_by(Tender.procedure_type)
    procedure_result = await db.execute(procedure_query)
    by_procedure = {row.procedure_type or 'unknown': row.count for row in procedure_result}

    # Total and average value
    value_query = select(
        func.sum(Tender.estimated_value_mkd).label('total'),
        func.avg(Tender.estimated_value_mkd).label('avg')
    )
    value_result = await db.execute(value_query)
    value_row = value_result.first()

    # Recent tenders
    now = datetime.utcnow()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    tenders_7d = await db.scalar(
        select(func.count()).select_from(Tender).where(Tender.created_at >= last_7_days)
    )
    tenders_30d = await db.scalar(
        select(func.count()).select_from(Tender).where(Tender.created_at >= last_30_days)
    )

    return TenderStatsResponse(
        total_tenders=total or 0,
        tenders_by_status=by_status,
        tenders_by_category=by_category,
        tenders_by_procedure_type=by_procedure,
        total_estimated_value_mkd=float(value_row.total) if value_row.total else None,
        avg_estimated_value_mkd=float(value_row.avg) if value_row.avg else None,
        tenders_last_7_days=tenders_7d or 0,
        tenders_last_30_days=tenders_30d or 0
    )


# ============================================================================
# ENTITY STATISTICS
# ============================================================================

@router.get("/entities/stats", response_model=EntityStatsResponse)
async def get_entity_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get procuring entity statistics

    Returns aggregated stats about entities
    """
    # Total entities
    total = await db.scalar(select(func.count()).select_from(ProcuringEntity))

    # By city
    city_query = select(
        ProcuringEntity.city,
        func.count(ProcuringEntity.entity_id).label('count')
    ).group_by(ProcuringEntity.city)
    city_result = await db.execute(city_query)
    by_city = {row.city or 'unknown': row.count for row in city_result}

    # Top entities by tender count
    top_query = select(ProcuringEntity).order_by(
        ProcuringEntity.total_tenders.desc()
    ).limit(10)
    top_result = await db.execute(top_query)
    top_entities = [
        {
            "entity_id": str(e.entity_id),
            "entity_name": e.entity_name,
            "total_tenders": e.total_tenders or 0,
            "total_value_mkd": float(e.total_value_mkd) if e.total_value_mkd else None
        }
        for e in top_result.scalars().all()
    ]

    return EntityStatsResponse(
        total_entities=total or 0,
        entities_by_city=by_city,
        top_entities_by_tenders=top_entities
    )


# ============================================================================
# TRENDS
# ============================================================================

@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y"),
    group_by: str = Query("day", description="Group by: day, week, month"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get tender trends over time

    Parameters:
    - period: Time period (7d, 30d, 90d, 1y)
    - group_by: Grouping (day, week, month)
    """
    # Calculate date range
    now = datetime.utcnow()
    period_days = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "1y": 365
    }
    days = period_days.get(period, 30)
    start_date = now - timedelta(days=days)

    # Build group by expression based on database
    if group_by == "week":
        date_trunc = "week"
    elif group_by == "month":
        date_trunc = "month"
    else:
        date_trunc = "day"

    # Query trends
    trends_query = text(f"""
        SELECT
            date_trunc('{date_trunc}', created_at) as period_date,
            COUNT(*) as count,
            SUM(estimated_value_mkd) as total_value
        FROM tenders
        WHERE created_at >= :start_date
        GROUP BY period_date
        ORDER BY period_date
    """)

    result = await db.execute(trends_query, {"start_date": start_date})
    rows = result.fetchall()

    data_points = [
        TimeSeriesDataPoint(
            date=row.period_date.isoformat() if row.period_date else "",
            count=row.count,
            total_value_mkd=float(row.total_value) if row.total_value else None
        )
        for row in rows
    ]

    # Calculate totals
    total_tenders = sum(dp.count for dp in data_points)
    total_value = sum(dp.total_value_mkd or 0 for dp in data_points)

    return TrendsResponse(
        period=period,
        tenders_over_time=data_points,
        total_tenders=total_tenders,
        total_value_mkd=total_value if total_value > 0 else None
    )


# ============================================================================
# SCRAPE HISTORY
# ============================================================================

@router.get("/scrape-history", response_model=ScrapeHistoryListResponse)
async def get_scrape_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get scrape run history

    Returns recent scrape runs with statistics
    """
    query = text("""
        SELECT
            id, started_at, completed_at, mode, category,
            tenders_found, tenders_new, tenders_updated,
            tenders_unchanged, errors, duration_seconds, status
        FROM scrape_history
        ORDER BY started_at DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"limit": limit})
    rows = result.fetchall()

    items = [
        ScrapeHistoryResponse(
            id=row.id,
            started_at=row.started_at,
            completed_at=row.completed_at,
            mode=row.mode or 'scrape',
            category=row.category,
            tenders_found=row.tenders_found or 0,
            tenders_new=row.tenders_new or 0,
            tenders_updated=row.tenders_updated or 0,
            tenders_unchanged=row.tenders_unchanged or 0,
            errors=row.errors or 0,
            duration_seconds=row.duration_seconds,
            status=row.status or 'unknown'
        )
        for row in rows
    ]

    return ScrapeHistoryListResponse(
        total=len(items),
        items=items
    )
