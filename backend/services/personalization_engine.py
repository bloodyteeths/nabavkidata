"""
Personalization Engine
Hybrid search, interest vectors, insights

Uses Google Gemini for embeddings (768 dimensions)
"""
import sys
import os
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ai'))

from models import Tender, User
from models_user_personalization import UserPreferences, UserBehavior, UserInterestVector
from schemas_user_personalization import RecommendedTender, CompetitorActivity, PersonalizedInsight

try:
    from embeddings import EmbeddingGenerator
    from rag_query import RAGQueryPipeline
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False


class HybridSearchEngine:
    """Combines preference-based and vector-based search with AI-powered CPV matching"""

    def __init__(self, db: AsyncSession):
        self.db = db
        if AI_AVAILABLE:
            self.embedder = EmbeddingGenerator()
        # Import CPV matcher for AI-based category matching
        from services.cpv_matcher import get_cpv_matcher
        self.cpv_matcher = get_cpv_matcher()

    async def search(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Tuple[Tender, float]]:
        """Hybrid search: preferences + interest vector + AI CPV matching"""

        # Get user preferences
        prefs = await self._get_preferences(user_id)
        if not prefs:
            return await self._fallback_search(limit)

        # Preference-based filter
        query = select(Tender).where(Tender.status == 'open')
        filters = []

        if prefs.sectors:
            filters.append(Tender.category.in_(prefs.sectors))

        # CPV filtering - we'll do AI matching after fetching candidates
        # since most tenders don't have actual CPV codes
        if prefs.cpv_codes:
            # Only filter by CPV if tender has actual CPV code (not category name)
            cpv_filters = [Tender.cpv_code.startswith(code) for code in prefs.cpv_codes]
            # Don't add this filter - we'll use AI matching instead
            # filters.append(or_(*cpv_filters))
            pass

        if prefs.entities:
            entity_filters = [Tender.procuring_entity.ilike(f"%{e}%") for e in prefs.entities]
            filters.append(or_(*entity_filters))
        if prefs.min_budget:
            filters.append(Tender.estimated_value_mkd >= prefs.min_budget)
        if prefs.max_budget:
            filters.append(Tender.estimated_value_mkd <= prefs.max_budget)
        if prefs.exclude_keywords:
            for kw in prefs.exclude_keywords:
                filters.append(~Tender.title.ilike(f"%{kw}%"))

        if filters:
            query = query.where(and_(*filters))

        # Get more candidates to filter with AI CPV matching
        result = await self.db.execute(query.order_by(desc(Tender.created_at)).limit(200))
        all_candidates = result.scalars().all()

        # Apply AI-based CPV matching if user has CPV preferences
        if prefs.cpv_codes:
            candidates = []
            for tender in all_candidates:
                # Check if tender has real CPV code
                if tender.cpv_code and tender.cpv_code not in ["Услуги", "Стоки", "Работи"]:
                    # Use actual CPV code
                    for cpv in prefs.cpv_codes:
                        if tender.cpv_code.startswith(cpv[:2]):
                            candidates.append(tender)
                            break
                else:
                    # Use AI to infer CPV from title/description
                    is_match, _ = self.cpv_matcher.matches_user_preferences(
                        tender_title=tender.title or "",
                        tender_description=tender.description or "",
                        tender_category=tender.category or "",
                        user_cpv_codes=prefs.cpv_codes
                    )
                    if is_match:
                        candidates.append(tender)

                # Stop if we have enough candidates
                if len(candidates) >= 100:
                    break
        else:
            candidates = all_candidates[:100]

        # Vector ranking
        scored = await self._vector_rank(user_id, candidates)

        return scored[:limit]

    async def _get_preferences(self, user_id: str) -> Optional[UserPreferences]:
        query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _vector_rank(
        self,
        user_id: str,
        tenders: List[Tender]
    ) -> List[Tuple[Tender, float]]:
        """Rank tenders by interest vector similarity"""

        if not AI_AVAILABLE or not tenders:
            return [(t, 0.5) for t in tenders]

        # Get user interest vector
        query = select(UserInterestVector).where(UserInterestVector.user_id == user_id)
        result = await self.db.execute(query)
        user_vector = result.scalar_one_or_none()

        if not user_vector:
            return [(t, 0.5) for t in tenders]

        # Compute similarity scores
        scored = []
        for tender in tenders:
            text = f"{tender.title} {tender.description or ''} {tender.category or ''}"
            tender_emb = await self.embedder.generate_embedding(text)

            similarity = self._cosine_similarity(user_vector.embedding, tender_emb)
            scored.append((tender, float(similarity)))

        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        a_np = np.array(a)
        b_np = np.array(b)
        return np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np))

    async def _fallback_search(self, limit: int) -> List[Tuple[Tender, float]]:
        query = select(Tender).where(Tender.status == 'open').order_by(desc(Tender.created_at)).limit(limit)
        result = await self.db.execute(query)
        tenders = result.scalars().all()
        return [(t, 0.5) for t in tenders]


class InterestVectorBuilder:
    """Builds user interest vector from behavior"""

    def __init__(self, db: AsyncSession):
        self.db = db
        if AI_AVAILABLE:
            self.embedder = EmbeddingGenerator()

    async def update_user_vector(self, user_id: str):
        """Update user interest vector from recent behavior"""

        if not AI_AVAILABLE:
            return

        # Get recent interactions (last 90 days)
        cutoff = datetime.utcnow() - timedelta(days=90)
        query = select(UserBehavior).where(
            and_(
                UserBehavior.user_id == user_id,
                UserBehavior.created_at >= cutoff
            )
        ).order_by(desc(UserBehavior.created_at)).limit(100)

        result = await self.db.execute(query)
        behaviors = result.scalars().all()

        if not behaviors:
            return

        # Get tender texts
        tender_texts = []
        weights = []

        for behavior in behaviors:
            tender_query = select(Tender).where(Tender.tender_id == behavior.tender_id)
            tender_result = await self.db.execute(tender_query)
            tender = tender_result.scalar_one_or_none()

            if tender:
                text = f"{tender.title} {tender.description or ''} {tender.category or ''}"
                tender_texts.append(text)

                # Weight by action type
                weight = {'view': 1.0, 'click': 1.5, 'save': 2.0, 'share': 2.5}.get(behavior.action, 1.0)
                weights.append(weight)

        if not tender_texts:
            return

        # Generate embeddings
        embeddings = await self.embedder.generate_embeddings_batch(tender_texts)

        # Weighted average
        weighted_emb = np.average(embeddings, axis=0, weights=weights)
        interest_vector = weighted_emb.tolist()

        # Upsert user interest vector
        query = select(UserInterestVector).where(UserInterestVector.user_id == user_id)
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.embedding = interest_vector
            existing.interaction_count = len(behaviors)
            existing.last_updated = datetime.utcnow()
            existing.version += 1
        else:
            new_vector = UserInterestVector(
                user_id=user_id,
                embedding=interest_vector,
                interaction_count=len(behaviors),
                last_updated=datetime.utcnow()
            )
            self.db.add(new_vector)

        await self.db.commit()


class InsightGenerator:
    """Generates personalized insights"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_insights(self, user_id: str) -> List[PersonalizedInsight]:
        """Generate AI insights for user"""

        insights = []

        # Insight 1: Trending sectors
        trend = await self._trending_sector_insight(user_id)
        if trend:
            insights.append(trend)

        # Insight 2: Budget opportunities
        opportunity = await self._budget_opportunity_insight(user_id)
        if opportunity:
            insights.append(opportunity)

        # Insight 3: Closing soon alert
        alert = await self._closing_soon_insight(user_id)
        if alert:
            insights.append(alert)

        return insights

    async def _trending_sector_insight(self, user_id: str) -> Optional[PersonalizedInsight]:
        prefs_query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.db.execute(prefs_query)
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.sectors:
            return None

        cutoff = datetime.utcnow() - timedelta(days=30)
        count_query = select(func.count()).select_from(Tender).where(
            and_(
                Tender.category.in_(prefs.sectors),
                Tender.created_at >= cutoff
            )
        )
        count = await self.db.scalar(count_query)

        if count > 10:
            return PersonalizedInsight(
                insight_type="trend",
                title="Increased Activity in Your Sectors",
                description=f"{count} new tenders in your preferred sectors this month",
                confidence=0.85
            )
        return None

    async def _budget_opportunity_insight(self, user_id: str) -> Optional[PersonalizedInsight]:
        prefs_query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.db.execute(prefs_query)
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.min_budget:
            return None

        count_query = select(func.count()).select_from(Tender).where(
            and_(
                Tender.status == 'open',
                Tender.estimated_value_mkd >= prefs.min_budget,
                Tender.estimated_value_mkd <= prefs.max_budget if prefs.max_budget else True
            )
        )
        count = await self.db.scalar(count_query)

        if count > 5:
            return PersonalizedInsight(
                insight_type="opportunity",
                title="Budget-Matched Opportunities",
                description=f"{count} open tenders within your budget range",
                confidence=0.90
            )
        return None

    async def _closing_soon_insight(self, user_id: str) -> Optional[PersonalizedInsight]:
        cutoff = datetime.utcnow() + timedelta(days=7)

        prefs_query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.db.execute(prefs_query)
        prefs = result.scalar_one_or_none()

        filters = [Tender.status == 'open', Tender.closing_date <= cutoff]
        if prefs and prefs.sectors:
            filters.append(Tender.category.in_(prefs.sectors))

        count_query = select(func.count()).select_from(Tender).where(and_(*filters))
        count = await self.db.scalar(count_query)

        if count > 0:
            return PersonalizedInsight(
                insight_type="alert",
                title="Deadlines Approaching",
                description=f"{count} relevant tenders closing within 7 days",
                confidence=1.0
            )
        return None


class CompetitorTracker:
    """Tracks competitor activity"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_competitor_activity(self, user_id: str, limit: int = 10) -> List[CompetitorActivity]:
        """Get tenders where competitors are involved"""

        prefs_query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.db.execute(prefs_query)
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.competitor_companies:
            return []

        activities = []

        for competitor in prefs.competitor_companies:
            query = select(Tender).where(
                Tender.winner.ilike(f"%{competitor}%")
            ).order_by(desc(Tender.updated_at)).limit(5)

            result = await self.db.execute(query)
            tenders = result.scalars().all()

            for tender in tenders:
                activities.append(CompetitorActivity(
                    tender_id=tender.tender_id,
                    title=tender.title,
                    competitor_name=competitor,
                    status=tender.status,
                    estimated_value_mkd=tender.estimated_value_mkd,
                    closing_date=tender.closing_date
                ))

        return activities[:limit]
