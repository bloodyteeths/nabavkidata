"""
Competitor Tracking API Endpoints
Monitor and analyze competing companies in the tender ecosystem
Phase 5.1 - UI Refactor Roadmap
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from database import get_db
from api.auth import get_current_user
from models import User
from schemas import (
    TrackedCompetitorCreate,
    TrackedCompetitorResponse,
    TrackedCompetitorListResponse,
    CompetitorStatsResponse,
    CompetitorTender,
    CompetitorSearchResult,
    CompetitorSearchResponse,
    MessageResponse
)

router = APIRouter(prefix="/competitors", tags=["Competitor Tracking"])


# ============================================================================
# LIST TRACKED COMPETITORS
# ============================================================================

@router.get("", response_model=TrackedCompetitorListResponse)
async def list_tracked_competitors(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of user's tracked competitors

    Returns all companies the authenticated user is monitoring with basic info.
    """
    query = text("""
        SELECT
            tracking_id,
            user_id,
            company_name,
            tax_id,
            notes,
            created_at
        FROM tracked_competitors
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """)

    result = await db.execute(query, {"user_id": str(current_user.user_id)})
    rows = result.fetchall()

    items = [
        TrackedCompetitorResponse(
            tracking_id=row.tracking_id,
            user_id=row.user_id,
            company_name=row.company_name,
            tax_id=row.tax_id,
            notes=row.notes,
            created_at=row.created_at
        )
        for row in rows
    ]

    return TrackedCompetitorListResponse(
        total=len(items),
        items=items
    )


# ============================================================================
# ADD TRACKED COMPETITOR
# ============================================================================

@router.post("", response_model=TrackedCompetitorResponse, status_code=status.HTTP_201_CREATED)
async def add_tracked_competitor(
    competitor: TrackedCompetitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a company to user's tracked competitors list

    - Validates company exists in tender_bidders
    - Prevents duplicate tracking
    - Returns tracked competitor details
    """
    # Check if company exists in tender_bidders
    check_query = text("""
        SELECT COUNT(*) as count
        FROM tender_bidders
        WHERE company_name = :company_name
    """)

    check_result = await db.execute(check_query, {"company_name": competitor.company_name})
    count = check_result.scalar()

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company '{competitor.company_name}' not found in tender database. Please search for valid company names first."
        )

    # Insert tracked competitor (ON CONFLICT to handle duplicates)
    insert_query = text("""
        INSERT INTO tracked_competitors (user_id, company_name, tax_id, notes)
        VALUES (:user_id, :company_name, :tax_id, :notes)
        ON CONFLICT (user_id, company_name) DO UPDATE
        SET tax_id = EXCLUDED.tax_id, notes = EXCLUDED.notes
        RETURNING tracking_id, user_id, company_name, tax_id, notes, created_at
    """)

    result = await db.execute(insert_query, {
        "user_id": str(current_user.user_id),
        "company_name": competitor.company_name,
        "tax_id": competitor.tax_id,
        "notes": competitor.notes
    })

    await db.commit()
    row = result.fetchone()

    # Update competitor_stats if not exists
    await _update_competitor_stats(db, competitor.company_name)

    return TrackedCompetitorResponse(
        tracking_id=row.tracking_id,
        user_id=row.user_id,
        company_name=row.company_name,
        tax_id=row.tax_id,
        notes=row.notes,
        created_at=row.created_at
    )


# ============================================================================
# REMOVE TRACKED COMPETITOR
# ============================================================================

@router.delete("/{tracking_id}", response_model=MessageResponse)
async def remove_tracked_competitor(
    tracking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a company from user's tracked competitors

    - Validates ownership
    - Deletes tracking record
    """
    delete_query = text("""
        DELETE FROM tracked_competitors
        WHERE tracking_id = :tracking_id AND user_id = :user_id
        RETURNING company_name
    """)

    result = await db.execute(delete_query, {
        "tracking_id": str(tracking_id),
        "user_id": str(current_user.user_id)
    })

    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked competitor not found or you don't have permission to delete it"
        )

    await db.commit()

    return MessageResponse(
        message="Competitor removed from tracking",
        detail=f"Stopped tracking {row.company_name}"
    )


# ============================================================================
# GET COMPETITOR STATISTICS
# ============================================================================

@router.get("/{company_name}/stats", response_model=CompetitorStatsResponse)
async def get_competitor_stats(
    company_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed statistics for a competitor company

    Returns:
    - Total bids and wins
    - Win rate percentage
    - Average bid discount from estimate
    - Top CPV categories
    - Recent tender participation (last 10)
    """
    # Update stats first to ensure fresh data
    await _update_competitor_stats(db, company_name)

    # Get stats from competitor_stats table
    stats_query = text("""
        SELECT
            company_name,
            total_bids,
            total_wins,
            win_rate,
            avg_bid_discount,
            top_cpv_codes,
            top_categories,
            last_updated
        FROM competitor_stats
        WHERE company_name = :company_name
    """)

    result = await db.execute(stats_query, {"company_name": company_name})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No statistics found for company '{company_name}'"
        )

    # Get recent tenders
    recent_query = text("""
        SELECT
            t.tender_id,
            t.title,
            t.procuring_entity,
            tb.bid_amount_mkd,
            t.estimated_value_mkd,
            tb.is_winner,
            tb.rank,
            t.closing_date,
            t.status
        FROM tender_bidders tb
        JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name = :company_name
        ORDER BY t.closing_date DESC NULLS LAST
        LIMIT 10
    """)

    recent_result = await db.execute(recent_query, {"company_name": company_name})
    recent_rows = recent_result.fetchall()

    recent_tenders = [
        CompetitorTender(
            tender_id=r.tender_id,
            title=r.title,
            procuring_entity=r.procuring_entity,
            bid_amount_mkd=r.bid_amount_mkd,
            estimated_value_mkd=r.estimated_value_mkd,
            is_winner=r.is_winner or False,
            rank=r.rank,
            closing_date=r.closing_date,
            status=r.status
        )
        for r in recent_rows
    ]

    return CompetitorStatsResponse(
        company_name=row.company_name,
        total_bids=row.total_bids or 0,
        total_wins=row.total_wins or 0,
        win_rate=float(row.win_rate) if row.win_rate else None,
        avg_bid_discount=float(row.avg_bid_discount) if row.avg_bid_discount else None,
        top_cpv_codes=row.top_cpv_codes or [],
        top_categories=row.top_categories or [],
        recent_tenders=recent_tenders,
        last_updated=row.last_updated
    )


# ============================================================================
# SEARCH COMPANIES
# ============================================================================

@router.get("/search", response_model=CompetitorSearchResponse)
async def search_companies(
    q: str = Query(..., min_length=2, description="Search query for company names"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for companies in the tender bidders database

    Use this to find valid company names before adding to tracked list.
    Returns companies matching the search query with their statistics.
    """
    search_query = text("""
        SELECT
            tb.company_name,
            tb.company_tax_id as tax_id,
            COUNT(*) as total_bids,
            COUNT(*) FILTER (WHERE tb.is_winner = true) as total_wins,
            ROUND((COUNT(*) FILTER (WHERE tb.is_winner = true)::numeric / NULLIF(COUNT(*), 0) * 100), 2) as win_rate,
            SUM(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner = true) as total_contract_value
        FROM tender_bidders tb
        WHERE tb.company_name ILIKE :search_pattern
        GROUP BY tb.company_name, tb.company_tax_id
        ORDER BY total_wins DESC, total_bids DESC
        LIMIT :limit
    """)

    result = await db.execute(search_query, {
        "search_pattern": f"%{q}%",
        "limit": limit
    })

    rows = result.fetchall()

    items = [
        CompetitorSearchResult(
            company_name=row.company_name,
            tax_id=row.tax_id,
            total_bids=row.total_bids or 0,
            total_wins=row.total_wins or 0,
            win_rate=float(row.win_rate) if row.win_rate else None,
            total_contract_value=row.total_contract_value
        )
        for row in rows
    ]

    return CompetitorSearchResponse(
        total=len(items),
        items=items
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _update_competitor_stats(db: AsyncSession, company_name: str):
    """
    Update or create statistics for a competitor company

    Aggregates data from tender_bidders and tenders tables:
    - Total bids and wins
    - Win rate
    - Average bid discount
    - Top CPV codes and categories
    """
    update_query = text("""
        INSERT INTO competitor_stats (
            company_name,
            total_bids,
            total_wins,
            win_rate,
            avg_bid_discount,
            top_cpv_codes,
            top_categories,
            last_updated
        )
        SELECT
            :company_name,
            COUNT(*) as total_bids,
            COUNT(*) FILTER (WHERE tb.is_winner = true) as total_wins,
            ROUND((COUNT(*) FILTER (WHERE tb.is_winner = true)::numeric / NULLIF(COUNT(*), 0) * 100), 2) as win_rate,
            ROUND(AVG(
                CASE
                    WHEN t.estimated_value_mkd > 0 AND tb.bid_amount_mkd > 0
                    THEN ((t.estimated_value_mkd - tb.bid_amount_mkd) / t.estimated_value_mkd * 100)
                    ELSE NULL
                END
            ), 2) as avg_bid_discount,
            (
                SELECT jsonb_agg(cpv_data ORDER BY bid_count DESC)
                FROM (
                    SELECT
                        t.cpv_code,
                        t.category,
                        COUNT(*) as bid_count
                    FROM tender_bidders tb2
                    JOIN tenders t ON tb2.tender_id = t.tender_id
                    WHERE tb2.company_name = :company_name
                        AND t.cpv_code IS NOT NULL
                    GROUP BY t.cpv_code, t.category
                    ORDER BY bid_count DESC
                    LIMIT 5
                ) as cpv_data
            ) as top_cpv_codes,
            (
                SELECT jsonb_agg(cat_data ORDER BY bid_count DESC)
                FROM (
                    SELECT
                        t.category,
                        COUNT(*) as bid_count
                    FROM tender_bidders tb2
                    JOIN tenders t ON tb2.tender_id = t.tender_id
                    WHERE tb2.company_name = :company_name
                        AND t.category IS NOT NULL
                    GROUP BY t.category
                    ORDER BY bid_count DESC
                    LIMIT 5
                ) as cat_data
            ) as top_categories,
            CURRENT_TIMESTAMP
        FROM tender_bidders tb
        LEFT JOIN tenders t ON tb.tender_id = t.tender_id
        WHERE tb.company_name = :company_name
        GROUP BY tb.company_name
        ON CONFLICT (company_name) DO UPDATE SET
            total_bids = EXCLUDED.total_bids,
            total_wins = EXCLUDED.total_wins,
            win_rate = EXCLUDED.win_rate,
            avg_bid_discount = EXCLUDED.avg_bid_discount,
            top_cpv_codes = EXCLUDED.top_cpv_codes,
            top_categories = EXCLUDED.top_categories,
            last_updated = CURRENT_TIMESTAMP
    """)

    await db.execute(update_query, {"company_name": company_name})
    await db.commit()
