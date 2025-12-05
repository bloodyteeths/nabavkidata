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

    # Sector keyword mapping for AI-based matching
    SECTOR_KEYWORDS = {
        "it": ["софтвер", "ИТ", "информатички", "компјутер", "систем", "апликација", "веб", "дигитал", "software", "IT", "computer", "digital", "hardware", "сервер", "мрежа"],
        "construction": ["градежн", "изградба", "реконструкција", "санација", "објект", "зграда", "пат", "construction", "building", "infrastructure"],
        "consulting": ["консултант", "советодавн", "consulting", "advisory", "студија", "анализа"],
        "equipment": ["опрема", "машини", "апарат", "уред", "equipment", "machinery", "device"],
        "medical": ["медицин", "здравств", "болница", "лек", "фармацевт", "medical", "health", "hospital", "pharma"],
        "education": ["образова", "училиш", "универзитет", "обука", "education", "school", "training"],
        "transport": ["транспорт", "превоз", "возил", "transport", "vehicle", "logistics"],
        "food": ["храна", "пијалоц", "прехран", "food", "beverage", "catering"],
        "cleaning": ["чистење", "хигиена", "одржување", "cleaning", "maintenance", "hygiene"],
        "security": ["безбедност", "обезбедување", "заштита", "security", "protection", "surveillance"],
        "energy": ["енергија", "електрична", "струја", "гориво", "energy", "electricity", "fuel"],
        "printing": ["печатење", "печатница", "printing", "publishing"]
    }

    async def search(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Tuple[Tender, float]]:
        """Hybrid search: uses preferences for SCORING, not filtering"""

        # Get user preferences
        prefs = await self._get_preferences(user_id)

        # Check if user has any meaningful preferences
        has_preferences = prefs and (
            (prefs.sectors and len(prefs.sectors) > 0) or
            (prefs.cpv_codes and len(prefs.cpv_codes) > 0) or
            (prefs.entities and len(prefs.entities) > 0) or
            prefs.min_budget or prefs.max_budget
        )

        if not has_preferences:
            return await self._fallback_search(limit)

        # Get all open tenders - preferences are for scoring, not filtering
        query = select(Tender).where(Tender.status == 'open')

        # Only apply hard filters for exclude_keywords (things user explicitly doesn't want)
        if prefs.exclude_keywords:
            for kw in prefs.exclude_keywords:
                query = query.where(~Tender.title.ilike(f"%{kw}%"))

        # Get recent open tenders
        result = await self.db.execute(query.order_by(desc(Tender.created_at)).limit(200))
        all_candidates = result.scalars().all()

        # Score each tender based on preferences (not filter!)
        scored_candidates = []
        for tender in all_candidates:
            score = 0.3  # Base score for being an open tender
            tender_text = f"{tender.title or ''} {tender.description or ''}".lower()

            # Boost score for sector match (keyword matching)
            if prefs.sectors:
                for sector in prefs.sectors:
                    keywords = self.SECTOR_KEYWORDS.get(sector, [])
                    for keyword in keywords:
                        if keyword.lower() in tender_text:
                            score += 0.25  # Sector match boost
                            break

            # Boost score for CPV match
            if prefs.cpv_codes:
                if tender.cpv_code and tender.cpv_code not in ["Услуги", "Стоки", "Работи"]:
                    for cpv in prefs.cpv_codes:
                        if tender.cpv_code.startswith(cpv[:2]):
                            score += 0.2  # CPV code match boost
                            break
                else:
                    # Use AI to infer CPV match
                    is_match, _ = self.cpv_matcher.matches_user_preferences(
                        tender_title=tender.title or "",
                        tender_description=tender.description or "",
                        tender_category=tender.category or "",
                        user_cpv_codes=prefs.cpv_codes
                    )
                    if is_match:
                        score += 0.15  # AI-inferred CPV match boost

            # Boost score for entity match
            if prefs.entities and tender.procuring_entity:
                for entity in prefs.entities:
                    if entity.lower() in tender.procuring_entity.lower():
                        score += 0.2  # Entity match boost
                        break

            # Boost score for budget match (only if user has budget preferences)
            if tender.estimated_value_mkd and (prefs.min_budget or prefs.max_budget):
                in_budget = True
                if prefs.min_budget and tender.estimated_value_mkd < float(prefs.min_budget):
                    in_budget = False
                if prefs.max_budget and tender.estimated_value_mkd > float(prefs.max_budget):
                    in_budget = False
                if in_budget:
                    score += 0.1  # Budget match boost

            scored_candidates.append((tender, min(score, 1.0)))

        # Sort by score (highest first) and return top results
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        return scored_candidates[:limit]

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
                title="Зголемена активност во вашите сектори",
                description=f"{count} нови тендери во вашите преферирани сектори овој месец",
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
                title="Можности во вашиот буџет",
                description=f"{count} отворени тендери во вашиот буџетски опсег",
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
                title="Приближуваат рокови",
                description=f"{count} релевантни тендери завршуваат во наредните 7 дена",
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
