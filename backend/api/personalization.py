"""
Personalization API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from database import get_db
from models import User
from models_user_personalization import UserPreferences, UserBehavior
from schemas_user_personalization import (
    PreferencesCreate,
    PreferencesUpdate,
    PreferencesResponse,
    BehaviorLog,
    BehaviorResponse,
    DashboardResponse,
    RecommendedTender,
    InterestVectorResponse
)
from services.personalization_engine import (
    HybridSearchEngine,
    InsightGenerator,
    CompetitorTracker
)

router = APIRouter(prefix="/api/personalization", tags=["personalization"])


# Search history schema
class SearchHistoryLog(BaseModel):
    query_text: Optional[str] = None
    filters: Optional[dict] = {}
    results_count: Optional[int] = None
    clicked_tender_id: Optional[str] = None


def generate_match_reasons(tender, user_prefs: Optional[UserPreferences]) -> List[str]:
    """Generate meaningful match reasons based on user preferences"""
    reasons = []

    if not user_prefs:
        # No preferences - show generic reasons
        if tender.status == 'open':
            reasons.append("Отворен тендер")
        return reasons if reasons else ["Нов тендер"]

    # Check sector match
    if user_prefs.sectors and tender.category:
        # Map sector IDs to names for display
        sector_names = {
            "it": "ИТ и Софтвер",
            "construction": "Градежништво",
            "consulting": "Консултантски услуги",
            "equipment": "Опрема и машини",
            "medical": "Медицина и здравство",
            "education": "Образование",
            "transport": "Транспорт",
            "food": "Храна и пијалоци",
            "cleaning": "Чистење и одржување",
            "security": "Обезбедување",
            "energy": "Енергетика",
            "printing": "Печатење"
        }
        for sector_id in user_prefs.sectors:
            sector_name = sector_names.get(sector_id, sector_id)
            if tender.category and (sector_id.lower() in tender.category.lower() or
                                    sector_name.lower() in tender.category.lower()):
                reasons.append(f"Сектор: {sector_name}")
                break

    # Check CPV code match
    if user_prefs.cpv_codes and tender.cpv_code:
        for cpv in user_prefs.cpv_codes:
            if tender.cpv_code.startswith(cpv[:2]):  # Match first 2 digits at minimum
                reasons.append(f"CPV код: {tender.cpv_code[:8]}")
                break

    # Check entity match
    if user_prefs.entities and tender.procuring_entity:
        for entity in user_prefs.entities:
            if entity.lower() in tender.procuring_entity.lower():
                reasons.append(f"Организација: {entity[:30]}")
                break

    # Check budget range match
    if tender.estimated_value_mkd:
        in_budget = True
        if user_prefs.min_budget and tender.estimated_value_mkd < user_prefs.min_budget:
            in_budget = False
        if user_prefs.max_budget and tender.estimated_value_mkd > user_prefs.max_budget:
            in_budget = False
        if in_budget and (user_prefs.min_budget or user_prefs.max_budget):
            reasons.append("Во вашиот буџет")

    # If no specific matches but tender is open
    if not reasons:
        if tender.status == 'open':
            reasons.append("Отворен тендер")
        else:
            reasons.append("Поврзан тендер")

    return reasons[:3]  # Limit to 3 reasons


# ============================================================================
# PREFERENCES
# ============================================================================

@router.post("/preferences", response_model=PreferencesResponse, status_code=201)
async def create_preferences(
    prefs: PreferencesCreate,
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Create user preferences"""

    # Check if exists
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Preferences already exist. Use PUT to update.")

    db_prefs = UserPreferences(user_id=user_id, **prefs.dict())
    db.add(db_prefs)
    await db.commit()
    await db.refresh(db_prefs)

    return PreferencesResponse.from_orm(db_prefs)


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Get user preferences"""

    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db.execute(query)
    prefs = result.scalar_one_or_none()

    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not found")

    return PreferencesResponse.from_orm(prefs)


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    prefs_update: PreferencesUpdate,
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Update user preferences"""

    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db.execute(query)
    db_prefs = result.scalar_one_or_none()

    if not db_prefs:
        raise HTTPException(status_code=404, detail="Preferences not found")

    update_data = prefs_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_prefs, field, value)

    await db.commit()
    await db.refresh(db_prefs)

    return PreferencesResponse.from_orm(db_prefs)


# ============================================================================
# BEHAVIOR TRACKING
# ============================================================================

@router.post("/behavior", response_model=BehaviorResponse, status_code=201)
async def log_behavior(
    behavior: BehaviorLog,
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Log user behavior"""

    db_behavior = UserBehavior(
        user_id=user_id,
        **behavior.dict()
    )
    db.add(db_behavior)
    await db.commit()
    await db.refresh(db_behavior)

    return BehaviorResponse.from_orm(db_behavior)


@router.get("/behavior", response_model=List[BehaviorResponse])
async def get_behavior_history(
    user_id: UUID,  # TODO: Get from auth
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get user behavior history"""

    query = select(UserBehavior).where(
        UserBehavior.user_id == user_id
    ).order_by(
        UserBehavior.created_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    behaviors = result.scalars().all()

    return [BehaviorResponse.from_orm(b) for b in behaviors]


# ============================================================================
# PERSONALIZED DASHBOARD
# ============================================================================

@router.get("/dashboard", response_model=DashboardResponse)
async def get_personalized_dashboard(
    user_id: UUID,  # TODO: Get from auth
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get personalized dashboard"""

    # Get user preferences for match reasons
    prefs_query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    prefs_result = await db.execute(prefs_query)
    user_prefs = prefs_result.scalar_one_or_none()

    # Hybrid search
    search_engine = HybridSearchEngine(db)
    scored_tenders = await search_engine.search(user_id, limit=limit)

    # Convert to response format with meaningful match reasons
    recommended = []
    for tender, score in scored_tenders:
        match_reasons = generate_match_reasons(tender, user_prefs)

        recommended.append(RecommendedTender(
            tender_id=tender.tender_id,
            title=tender.title,
            category=tender.category,
            procuring_entity=tender.procuring_entity,
            estimated_value_mkd=tender.estimated_value_mkd,
            closing_date=tender.closing_date,
            score=score,
            match_reasons=match_reasons
        ))

    # Competitor activity
    competitor_tracker = CompetitorTracker(db)
    competitor_activity = await competitor_tracker.get_competitor_activity(user_id, limit=10)

    # Insights
    insight_generator = InsightGenerator(db)
    insights = await insight_generator.generate_insights(user_id)

    # Stats
    stats = {
        "recommended_count": len(recommended),
        "competitor_activity_count": len(competitor_activity),
        "insights_count": len(insights)
    }

    return DashboardResponse(
        recommended_tenders=recommended,
        competitor_activity=competitor_activity,
        insights=insights,
        stats=stats
    )


@router.get("/insights")
async def get_insights(
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Get personalized insights only"""

    insight_generator = InsightGenerator(db)
    insights = await insight_generator.generate_insights(user_id)

    return {"insights": insights}


# ============================================================================
# INTEREST VECTOR
# ============================================================================

@router.get("/interest-vector", response_model=InterestVectorResponse)
async def get_interest_vector(
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Get user interest vector metadata"""

    from models_user_personalization import UserInterestVector

    query = select(UserInterestVector).where(UserInterestVector.user_id == user_id)
    result = await db.execute(query)
    vector = result.scalar_one_or_none()

    if not vector:
        raise HTTPException(status_code=404, detail="Interest vector not found")

    return InterestVectorResponse.from_orm(vector)


@router.post("/interest-vector/refresh")
async def refresh_interest_vector(
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Manually refresh user interest vector"""

    from services.personalization_engine import InterestVectorBuilder

    builder = InterestVectorBuilder(db)
    await builder.update_user_vector(user_id)

    return {"message": "Interest vector updated"}


# ============================================================================
# EMAIL DIGESTS
# ============================================================================

@router.get("/digests")
async def get_user_digests(
    user_id: UUID,  # TODO: Get from auth
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get user's email digests"""
    from sqlalchemy import text

    # Check if table exists first
    try:
        check_query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'email_digests')")
        check_result = await db.execute(check_query)
        table_exists = check_result.scalar()

        if not table_exists:
            # Table doesn't exist yet - return empty results
            return {
                "total": 0,
                "items": []
            }
    except Exception:
        # If we can't check, return empty results
        return {
            "total": 0,
            "items": []
        }

    from models_user_personalization import EmailDigest

    query = select(EmailDigest).where(
        EmailDigest.user_id == user_id
    ).order_by(
        EmailDigest.digest_date.desc()
    ).limit(limit).offset(offset)

    result = await db.execute(query)
    digests = result.scalars().all()

    return {
        "total": len(digests),
        "items": [
            {
                "id": str(d.digest_id),
                "date": d.digest_date.isoformat(),
                "tender_count": d.tender_count,
                "competitor_activity_count": d.competitor_activity_count,
                "sent": d.sent,
                "sent_at": d.sent_at.isoformat() if d.sent_at else None,
                "preview": {
                    "text": d.digest_text[:200] if d.digest_text else "",
                }
            }
            for d in digests
        ]
    }


@router.get("/digests/{digest_id}")
async def get_digest_detail(
    digest_id: UUID,
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Get detailed digest content"""
    from sqlalchemy import text

    # Check if table exists first
    try:
        check_query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'email_digests')")
        check_result = await db.execute(check_query)
        table_exists = check_result.scalar()

        if not table_exists:
            raise HTTPException(status_code=404, detail="Digest not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Digest not found")

    from models_user_personalization import EmailDigest

    query = select(EmailDigest).where(
        EmailDigest.digest_id == digest_id,
        EmailDigest.user_id == user_id
    )

    result = await db.execute(query)
    digest = result.scalar_one_or_none()

    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    return {
        "id": str(digest.digest_id),
        "date": digest.digest_date.isoformat(),
        "tender_count": digest.tender_count,
        "competitor_activity_count": digest.competitor_activity_count,
        "html": digest.digest_html,
        "text": digest.digest_text,
        "sent": digest.sent,
        "sent_at": digest.sent_at.isoformat() if digest.sent_at else None,
    }


# ============================================================================
# SEARCH HISTORY
# ============================================================================

@router.post("/search-history", status_code=201)
async def log_search(
    search: SearchHistoryLog,
    user_id: UUID,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db)
):
    """Log a search query for personalization"""
    try:
        # Check if table exists
        check_query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'search_history')")
        check_result = await db.execute(check_query)
        table_exists = check_result.scalar()

        if not table_exists:
            return {"message": "Search logged (table pending migration)"}

        # Insert search history
        insert_query = text("""
            INSERT INTO search_history (user_id, query_text, filters, results_count, clicked_tender_id)
            VALUES (:user_id, :query_text, :filters, :results_count, :clicked_tender_id)
        """)
        await db.execute(insert_query, {
            "user_id": str(user_id),
            "query_text": search.query_text,
            "filters": str(search.filters) if search.filters else "{}",
            "results_count": search.results_count,
            "clicked_tender_id": search.clicked_tender_id
        })
        await db.commit()

        return {"message": "Search logged successfully"}
    except Exception as e:
        # Don't fail the request if logging fails
        print(f"Failed to log search: {e}")
        return {"message": "Search logged (with warning)"}


@router.get("/search-history")
async def get_search_history(
    user_id: UUID,  # TODO: Get from auth
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get user's recent search history"""
    try:
        # Check if table exists
        check_query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'search_history')")
        check_result = await db.execute(check_query)
        table_exists = check_result.scalar()

        if not table_exists:
            return {"total": 0, "items": []}

        # Get recent searches
        query = text("""
            SELECT search_id, query_text, filters, results_count, clicked_tender_id, created_at
            FROM search_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        result = await db.execute(query, {"user_id": str(user_id), "limit": limit})
        rows = result.fetchall()

        return {
            "total": len(rows),
            "items": [
                {
                    "id": str(row[0]),
                    "query_text": row[1],
                    "filters": row[2],
                    "results_count": row[3],
                    "clicked_tender_id": row[4],
                    "created_at": row[5].isoformat() if row[5] else None
                }
                for row in rows
            ]
        }
    except Exception as e:
        print(f"Failed to get search history: {e}")
        return {"total": 0, "items": []}


@router.get("/popular-searches")
async def get_popular_searches(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Get popular search queries across all users"""
    try:
        # Check if table exists
        check_query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'search_history')")
        check_result = await db.execute(check_query)
        table_exists = check_result.scalar()

        if not table_exists:
            return {"items": []}

        # Get popular searches
        query = text("""
            SELECT query_text, COUNT(*) as search_count
            FROM search_history
            WHERE query_text IS NOT NULL AND query_text != ''
            GROUP BY query_text
            ORDER BY search_count DESC
            LIMIT :limit
        """)
        result = await db.execute(query, {"limit": limit})
        rows = result.fetchall()

        return {
            "items": [
                {"query": row[0], "count": row[1]}
                for row in rows
            ]
        }
    except Exception as e:
        print(f"Failed to get popular searches: {e}")
        return {"items": []}
