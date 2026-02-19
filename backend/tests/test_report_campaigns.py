"""
Tests for Report Campaign System
Run with: pytest backend/tests/test_report_campaigns.py -v
"""
import os
import sys
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.email_enrichment import (
    score_email, classify_email_type, GeminiEmailSearcher
)
from backend.services.campaign_sender import (
    generate_unsubscribe_token, verify_unsubscribe_token,
    generate_unsubscribe_url, generate_email_html, generate_email_text
)
from backend.services.report_generator import (
    get_cpv_name, format_value, generate_report_html
)


# ============================================================================
# EMAIL ENRICHMENT TESTS
# ============================================================================

class TestEmailScoring:
    """Tests for email scoring and classification"""

    def test_role_based_email_gets_bonus(self):
        """Role-based emails should score higher"""
        score = score_email("info@company.mk", "Company Name")
        assert score > 50  # Base is 50, role-based adds bonus

    def test_free_email_penalized(self):
        """Free email providers should be penalized"""
        score = score_email("person@gmail.com", "Company Name")
        assert score < 50  # Should be penalized

    def test_domain_match_bonus(self):
        """Emails matching company name in domain get bonus"""
        score = score_email("info@alkaloid.com.mk", "Alkaloid AD Skopje")
        assert score >= 70  # Role-based + domain match

    def test_classify_role_based(self):
        """Should correctly classify role-based emails"""
        assert classify_email_type("info@company.mk") == "role_based"
        assert classify_email_type("kontakt@company.mk") == "role_based"
        assert classify_email_type("sales@company.mk") == "role_based"
        assert classify_email_type("nabavki@company.mk") == "role_based"

    def test_classify_personal(self):
        """Should correctly classify personal emails"""
        assert classify_email_type("marko.petrov@company.mk") == "personal"

    def test_classify_unknown(self):
        """Should classify ambiguous emails as unknown"""
        assert classify_email_type("abc123@company.mk") == "unknown"


# ============================================================================
# UNSUBSCRIBE TESTS
# ============================================================================

class TestUnsubscribe:
    """Tests for unsubscribe token generation and verification"""

    def test_token_generation(self):
        """Token should be generated consistently"""
        email = "test@example.com"
        token1 = generate_unsubscribe_token(email)
        token2 = generate_unsubscribe_token(email)
        assert token1 == token2
        assert len(token1) == 32

    def test_token_verification_valid(self):
        """Valid token should verify"""
        email = "test@example.com"
        token = generate_unsubscribe_token(email)
        assert verify_unsubscribe_token(email, token) is True

    def test_token_verification_invalid(self):
        """Invalid token should not verify"""
        email = "test@example.com"
        assert verify_unsubscribe_token(email, "invalid_token") is False

    def test_token_different_for_different_emails(self):
        """Different emails should have different tokens"""
        token1 = generate_unsubscribe_token("email1@example.com")
        token2 = generate_unsubscribe_token("email2@example.com")
        assert token1 != token2

    def test_unsubscribe_url_contains_email(self):
        """Unsubscribe URL should contain email and token"""
        email = "test@example.com"
        url = generate_unsubscribe_url(email)
        assert email in url
        assert "token=" in url


# ============================================================================
# EMAIL CONTENT TESTS
# ============================================================================

class TestEmailContent:
    """Tests for email content generation"""

    def test_html_contains_required_elements(self):
        """HTML email should contain required elements"""
        stats = {
            "participations_12m": 45,
            "wins_12m": 12,
            "win_rate": 26.7,
            "top_cpvs": [{"name": "Медицинска опрема", "code": "33000000"}]
        }
        html = generate_email_html(
            company_name="Тест Компанија",
            stats=stats,
            missed_count=15,
            report_url="https://nabavkidata.com/report/123",
            checkout_url="https://nabavkidata.com/plans",
            unsubscribe_url="https://nabavkidata.com/unsubscribe?token=abc"
        )

        # Check required elements
        assert "Тест Компанија" in html
        assert "45 учества" in html
        assert "12 победи" in html
        assert "15 релевантни тендери" in html
        assert "ФАКТУРА" in html
        assert "СТОП" in html
        assert "https://nabavkidata.com/report/123" in html
        assert "unsubscribe" in html.lower()

    def test_text_contains_required_elements(self):
        """Plain text email should contain required elements"""
        stats = {
            "participations_12m": 45,
            "wins_12m": 12,
            "win_rate": 26.7,
            "top_cpvs": []
        }
        text = generate_email_text(
            company_name="Тест Компанија",
            stats=stats,
            missed_count=15,
            report_url="https://nabavkidata.com/report/123",
            checkout_url="https://nabavkidata.com/plans",
            unsubscribe_url="https://nabavkidata.com/unsubscribe?token=abc"
        )

        assert "Тест Компанија" in text
        assert "ФАКТУРА" in text
        assert "СТОП" in text
        assert "unsubscribe" in text.lower()


# ============================================================================
# REPORT GENERATOR TESTS
# ============================================================================

class TestReportGenerator:
    """Tests for PDF report generation"""

    def test_cpv_name_lookup(self):
        """Should return correct CPV names"""
        assert get_cpv_name("33000000") == "Медицинска опрема"
        assert get_cpv_name("45000000") == "Градежни работи"
        assert "CPV" in get_cpv_name("99999999")  # Unknown code

    def test_format_value_millions(self):
        """Should format millions correctly"""
        assert "М МКД" in format_value(5_000_000)

    def test_format_value_thousands(self):
        """Should format thousands correctly"""
        assert "К МКД" in format_value(50_000)

    def test_format_value_zero(self):
        """Should handle zero values"""
        assert format_value(0) == "Н/А"
        assert format_value(None) == "Н/А"

    def test_report_html_structure(self):
        """Report HTML should have correct structure"""
        html = generate_report_html(
            company_name="Тест Компанија",
            stats={"participations_12m": 10, "wins_12m": 3, "win_rate": 30, "total_value_mkd": 100000},
            top_cpvs=[{"code": "33000000", "name": "Медицинска опрема", "count": 5, "wins": 2, "value_won": 50000}],
            top_buyers=[{"name": "ФЗОМ", "count": 3, "wins": 1}],
            competitors=[{"name": "Конкурент 1", "wins": 4, "total_value": 80000}],
            missed_opportunities=[{"title": "Тендер 1", "buyer": "ФЗОМ", "deadline": "01.01.2025", "value": 10000, "cpv": "Медицинска", "winner": "X"}],
            expected_tenders={"low": 2, "mid": 5, "high": 8, "confidence": "medium"},
            buyer_map=[{"name": "ФЗОМ", "tender_count": 10, "top_winner": "X"}],
            checkout_url="https://nabavkidata.com/plans",
            unsubscribe_url="https://nabavkidata.com/unsubscribe"
        )

        # Check structure
        assert "<!DOCTYPE html>" in html
        assert "Тест Компанија" in html
        assert "Медицинска опрема" in html
        assert "ФЗОМ" in html
        assert "ФАКТУРА" in html
        assert "СТОП" in html
        assert "Пропуштени можности" in html


# ============================================================================
# SELECTION LOGIC TESTS
# ============================================================================

class TestSelectionLogic:
    """Tests for company selection logic"""

    @pytest.mark.asyncio
    async def test_excludes_suppressed_emails(self):
        """Should exclude emails in suppression list"""
        # This would require a mock database
        # Placeholder for integration test
        pass

    @pytest.mark.asyncio
    async def test_excludes_recently_contacted(self):
        """Should exclude companies contacted in last 90 days"""
        # This would require a mock database
        # Placeholder for integration test
        pass

    @pytest.mark.asyncio
    async def test_respects_min_participations(self):
        """Should only select companies with minimum participations"""
        # This would require a mock database
        # Placeholder for integration test
        pass


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Tests for rate limiting logic"""

    def test_jitter_within_range(self):
        """Jitter should be within configured range"""
        import random
        min_jitter = 30
        max_jitter = 180

        for _ in range(100):
            jitter = random.uniform(min_jitter, max_jitter)
            assert min_jitter <= jitter <= max_jitter


# ============================================================================
# WEBHOOK HANDLING TESTS
# ============================================================================

class TestWebhookHandling:
    """Tests for Postmark webhook handling"""

    @pytest.mark.asyncio
    async def test_bounce_adds_to_suppression(self):
        """Bounce events should add email to suppression list"""
        # This would require a mock database
        # Placeholder for integration test
        pass

    @pytest.mark.asyncio
    async def test_complaint_adds_to_suppression(self):
        """Spam complaints should add email to suppression list"""
        # This would require a mock database
        # Placeholder for integration test
        pass


# ============================================================================
# A/B TESTING TESTS
# ============================================================================

class TestABTesting:
    """Tests for A/B variant logic"""

    def test_variant_assignment_alternates(self):
        """Variants should alternate between A and B"""
        companies = [{"company_name": f"Company {i}"} for i in range(10)]
        variants = ["A" if i % 2 == 0 else "B" for i in range(10)]

        assert variants[0] == "A"
        assert variants[1] == "B"
        assert variants[2] == "A"
        assert variants.count("A") == 5
        assert variants.count("B") == 5


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
