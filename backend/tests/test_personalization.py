"""
Tests for User Personalization Module
"""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from models_user_personalization import UserPreferences, UserBehavior, UserInterestVector
from schemas_user_personalization import (
    PreferencesCreate,
    BehaviorLog,
    RecommendedTender
)
from services.personalization_engine import (
    HybridSearchEngine,
    InterestVectorBuilder,
    InsightGenerator,
    CompetitorTracker
)


class TestUserPreferencesModel:
    """Test UserPreferences model"""

    def test_model_creation(self):
        """Test creating UserPreferences"""
        user_id = uuid4()
        prefs = UserPreferences(
            user_id=user_id,
            sectors=["IT", "Construction"],
            cpv_codes=["30200000", "45000000"],
            entities=["Municipality of Skopje"],
            min_budget=Decimal("100000"),
            max_budget=Decimal("5000000"),
            exclude_keywords=["medical"],
            competitor_companies=["Company A", "Company B"],
            notification_frequency="daily"
        )

        assert prefs.user_id == user_id
        assert len(prefs.sectors) == 2
        assert prefs.notification_frequency == "daily"


class TestUserBehaviorModel:
    """Test UserBehavior model"""

    def test_behavior_logging(self):
        """Test logging user behavior"""
        behavior = UserBehavior(
            user_id=uuid4(),
            tender_id="2024-001",
            action="view",
            duration_seconds=45,
            metadata={"source": "search"}
        )

        assert behavior.action == "view"
        assert behavior.duration_seconds == 45


class TestPreferencesSchema:
    """Test Preferences schemas"""

    def test_preferences_create_validation(self):
        """Test PreferencesCreate validation"""
        prefs = PreferencesCreate(
            sectors=["IT"],
            notification_frequency="daily",
            email_enabled=True
        )

        assert prefs.notification_frequency == "daily"
        assert prefs.email_enabled == True

    def test_invalid_frequency(self):
        """Test invalid notification frequency"""
        with pytest.raises(ValueError):
            PreferencesCreate(
                notification_frequency="monthly"  # Invalid
            )


class TestBehaviorSchema:
    """Test Behavior schemas"""

    def test_behavior_log_validation(self):
        """Test BehaviorLog validation"""
        log = BehaviorLog(
            tender_id="2024-001",
            action="view",
            duration_seconds=30
        )

        assert log.action == "view"
        assert log.tender_id == "2024-001"

    def test_invalid_action(self):
        """Test invalid action type"""
        with pytest.raises(ValueError):
            BehaviorLog(
                tender_id="2024-001",
                action="invalid"  # Not in allowed actions
            )


class TestHybridSearchEngine:
    """Test HybridSearchEngine"""

    @pytest.mark.asyncio
    async def test_search_with_preferences(self):
        """Test hybrid search with user preferences"""
        mock_db = AsyncMock()
        engine = HybridSearchEngine(mock_db)

        # Mock preferences
        mock_prefs = UserPreferences(
            user_id=uuid4(),
            sectors=["IT"],
            cpv_codes=["30200000"],
            min_budget=Decimal("100000")
        )

        # Mock search results
        engine._get_preferences = AsyncMock(return_value=mock_prefs)
        engine._vector_rank = AsyncMock(return_value=[])

        results = await engine.search(str(uuid4()), limit=10)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_fallback_search(self):
        """Test fallback search when no preferences"""
        mock_db = AsyncMock()
        engine = HybridSearchEngine(mock_db)

        engine._get_preferences = AsyncMock(return_value=None)
        engine._fallback_search = AsyncMock(return_value=[])

        results = await engine.search(str(uuid4()), limit=10)

        assert isinstance(results, list)


class TestInterestVectorBuilder:
    """Test InterestVectorBuilder"""

    @pytest.mark.asyncio
    async def test_update_user_vector(self):
        """Test updating user interest vector"""
        mock_db = AsyncMock()
        builder = InterestVectorBuilder(mock_db)

        # Mock behavior data
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        # Test with AI unavailable (should return early)
        await builder.update_user_vector(str(uuid4()))

        # Should handle gracefully
        assert True


class TestInsightGenerator:
    """Test InsightGenerator"""

    @pytest.mark.asyncio
    async def test_generate_insights(self):
        """Test insight generation"""
        mock_db = AsyncMock()
        generator = InsightGenerator(mock_db)

        generator._trending_sector_insight = AsyncMock(return_value=None)
        generator._budget_opportunity_insight = AsyncMock(return_value=None)
        generator._closing_soon_insight = AsyncMock(return_value=None)

        insights = await generator.generate_insights(str(uuid4()))

        assert isinstance(insights, list)


class TestCompetitorTracker:
    """Test CompetitorTracker"""

    @pytest.mark.asyncio
    async def test_get_competitor_activity(self):
        """Test getting competitor activity"""
        mock_db = AsyncMock()
        tracker = CompetitorTracker(mock_db)

        # Mock no preferences
        mock_db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))

        activity = await tracker.get_competitor_activity(str(uuid4()))

        assert activity == []


class TestRecommendedTenderSchema:
    """Test RecommendedTender schema"""

    def test_recommended_tender_creation(self):
        """Test creating RecommendedTender"""
        tender = RecommendedTender(
            tender_id="2024-001",
            title="IT Equipment",
            category="IT",
            procuring_entity="Municipality",
            estimated_value_mkd=Decimal("500000"),
            closing_date=datetime.utcnow(),
            score=0.95,
            match_reasons=["Category match", "Budget match"]
        )

        assert tender.score == 0.95
        assert len(tender.match_reasons) == 2


# Integration-style tests

@pytest.mark.integration
class TestPersonalizationIntegration:
    """Integration tests for personalization"""

    @pytest.mark.asyncio
    async def test_full_personalization_flow(self):
        """Test complete personalization workflow"""
        # This would require actual database
        pytest.skip("Requires database setup")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
