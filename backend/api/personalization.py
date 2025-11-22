"""
Personalization API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

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

    # Hybrid search
    search_engine = HybridSearchEngine(db)
    scored_tenders = await search_engine.search(user_id, limit=limit)

    # Convert to response format
    recommended = []
    for tender, score in scored_tenders:
        match_reasons = []
        if tender.category:
            match_reasons.append(f"Category: {tender.category}")
        if tender.cpv_code:
            match_reasons.append(f"CPV: {tender.cpv_code}")

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
