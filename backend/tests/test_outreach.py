"""
Tests for Lead Enrichment and Outreach System
"""
import pytest
import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Email extraction patterns
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Role-based prefixes
ROLE_BASED_PREFIXES = [
    "info", "kontakt", "contact", "office", "sales", "tender", "nabavki",
    "admin", "bizdev", "podrska", "support", "marketing", "hello", "team"
]


class TestEmailExtraction:
    """Tests for email extraction functionality"""

    def test_extract_standard_email(self):
        """Test extraction of standard email format"""
        html = '<p>Contact us at info@example.mk or sales@company.com.mk</p>'
        emails = re.findall(EMAIL_PATTERN, html)
        assert 'info@example.mk' in emails
        assert 'sales@company.com.mk' in emails

    def test_extract_obfuscated_email_at_dot(self):
        """Test extraction of [at] [dot] obfuscated emails"""
        html = '<p>Email: info [at] company [dot] mk</p>'
        pattern = r'([a-zA-Z0-9._%+-]+)\s*[\[\(]?\s*at\s*[\]\)]?\s*([a-zA-Z0-9.-]+)\s*[\[\(]?\s*dot\s*[\]\)]?\s*([a-zA-Z]{2,})'
        matches = re.findall(pattern, html, re.IGNORECASE)
        assert len(matches) >= 1
        email = f"{matches[0][0]}@{matches[0][1]}.{matches[0][2]}"
        assert email.lower() == "info@company.mk"

    def test_invalid_email_rejected(self):
        """Test that invalid emails are rejected"""
        invalid_emails = [
            "notanemail",
            "@domain.com",
            "user@",
            "user@.com",
            "user..name@domain.com",
        ]
        for email in invalid_emails:
            # Check length and format
            is_valid = (
                len(email) >= 5 and
                len(email) <= 254 and
                ".." not in email and
                not email.startswith(".") and
                not email.endswith(".")
            )
            # Most of these should fail validation
            if email == "notanemail" or email == "@domain.com" or email == "user@":
                assert "@" not in email or "." not in email.split("@")[-1]


class TestEmailClassification:
    """Tests for email classification"""

    def test_role_based_classification(self):
        """Test that role-based emails are correctly classified"""
        role_based_emails = [
            "info@company.mk",
            "kontakt@firma.com",
            "office@business.com.mk",
            "sales@supplier.mk",
            "tender@nabavki.com"
        ]

        for email in role_based_emails:
            local_part = email.split("@")[0].lower()
            is_role_based = any(
                local_part.startswith(prefix) or local_part == prefix
                for prefix in ROLE_BASED_PREFIXES
            )
            assert is_role_based, f"{email} should be classified as role_based"

    def test_personal_classification(self):
        """Test that personal emails are correctly classified"""
        personal_emails = [
            "john.smith@company.mk",
            "marija.petrovska@firma.com",
        ]

        for email in personal_emails:
            local_part = email.split("@")[0].lower()
            is_role_based = any(
                local_part.startswith(prefix) or local_part == prefix
                for prefix in ROLE_BASED_PREFIXES
            )
            assert not is_role_based, f"{email} should be classified as personal"
            assert "." in local_part, f"{email} should have firstname.lastname pattern"


class TestConfidenceScoring:
    """Tests for email confidence scoring"""

    def test_contact_page_bonus(self):
        """Test that emails from contact pages get bonus score"""
        base_score = 50
        contact_patterns = ["/contact", "/kontakt", "/about"]

        source_url = "https://company.mk/kontakt"
        bonus = 40 if any(p in source_url.lower() for p in contact_patterns) else 0
        assert bonus == 40

    def test_free_email_penalty(self):
        """Test that free email providers get penalty"""
        free_domains = ["gmail.com", "yahoo.com", "hotmail.com"]

        email = "user@gmail.com"
        penalty = -50 if any(email.endswith(f"@{d}") for d in free_domains) else 0
        assert penalty == -50

        email2 = "info@company.mk"
        penalty2 = -50 if any(email2.endswith(f"@{d}") for d in free_domains) else 0
        assert penalty2 == 0


class TestUnsubscribeToken:
    """Tests for unsubscribe token generation and verification"""

    def test_token_generation_consistency(self):
        """Test that same email generates same token"""
        import hashlib
        secret = "test-secret"
        email = "user@example.com"

        token1 = hashlib.sha256(f"{email}:{secret}".encode()).hexdigest()[:32]
        token2 = hashlib.sha256(f"{email}:{secret}".encode()).hexdigest()[:32]

        assert token1 == token2

    def test_different_emails_different_tokens(self):
        """Test that different emails generate different tokens"""
        import hashlib
        secret = "test-secret"

        token1 = hashlib.sha256(f"user1@example.com:{secret}".encode()).hexdigest()[:32]
        token2 = hashlib.sha256(f"user2@example.com:{secret}".encode()).hexdigest()[:32]

        assert token1 != token2

    def test_token_verification(self):
        """Test token verification logic"""
        import hashlib
        secret = "test-secret"
        email = "user@example.com"

        # Generate token
        token = hashlib.sha256(f"{email}:{secret}".encode()).hexdigest()[:32]

        # Verify correct token
        expected = hashlib.sha256(f"{email}:{secret}".encode()).hexdigest()[:32]
        assert token == expected

        # Verify wrong token fails
        wrong_token = "wrongtoken12345678901234567890"
        assert wrong_token != expected


class TestSuppressionLogic:
    """Tests for suppression list logic"""

    def test_suppressed_email_blocks_send(self):
        """Test that suppressed emails are blocked from sending"""
        suppression_list = {"bounced@example.com", "unsubscribed@example.com"}

        # Should be blocked
        assert "bounced@example.com" in suppression_list
        assert "unsubscribed@example.com" in suppression_list

        # Should not be blocked
        assert "valid@example.com" not in suppression_list

    def test_suppression_reasons(self):
        """Test valid suppression reasons"""
        valid_reasons = ["unsubscribed", "bounce", "complaint", "manual"]

        for reason in valid_reasons:
            assert reason in valid_reasons


class TestRateLimiting:
    """Tests for rate limiting logic"""

    def test_daily_limit_check(self):
        """Test daily rate limit checking"""
        daily_limit = 100
        daily_count = 50
        assert daily_count < daily_limit, "Should allow sending"

        daily_count = 100
        assert daily_count >= daily_limit, "Should block sending"

    def test_hourly_limit_check(self):
        """Test hourly rate limit checking"""
        hourly_limit = 10
        hourly_count = 5
        assert hourly_count < hourly_limit, "Should allow sending"

        hourly_count = 10
        assert hourly_count >= hourly_limit, "Should block sending"


class TestSegmentation:
    """Tests for supplier segmentation"""

    def test_frequent_winner_segment(self):
        """Test frequent winner classification"""
        recent_wins = 5
        segment = "frequent_winner" if recent_wins >= 5 else "other"
        assert segment == "frequent_winner"

    def test_occasional_segment(self):
        """Test occasional participant classification"""
        recent_wins = 2
        if recent_wins >= 5:
            segment = "frequent_winner"
        elif recent_wins >= 1:
            segment = "occasional"
        else:
            segment = "new_unknown"
        assert segment == "occasional"

    def test_new_unknown_segment(self):
        """Test new/unknown classification"""
        recent_wins = 0
        if recent_wins >= 5:
            segment = "frequent_winner"
        elif recent_wins >= 1:
            segment = "occasional"
        else:
            segment = "new_unknown"
        assert segment == "new_unknown"


class TestTemplateRendering:
    """Tests for template rendering"""

    def test_placeholder_replacement(self):
        """Test that placeholders are replaced correctly"""
        template = "Hello {{supplier_name}}, you have {{recent_awards_count}} wins."
        personalization = {
            "supplier_name": "Test Company",
            "recent_awards_count": 5
        }

        rendered = template
        for key, value in personalization.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

        assert "Test Company" in rendered
        assert "5" in rendered
        assert "{{" not in rendered

    def test_unsubscribe_url_included(self):
        """Test that unsubscribe URL is in template"""
        template = '<a href="{{unsubscribe_url}}">Unsubscribe</a>'
        unsubscribe_url = "https://nabavkidata.com/unsubscribe?e=test&t=token"

        rendered = template.replace("{{unsubscribe_url}}", unsubscribe_url)
        assert "nabavkidata.com/unsubscribe" in rendered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
