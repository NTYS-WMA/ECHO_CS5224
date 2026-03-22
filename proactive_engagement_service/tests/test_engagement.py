"""
Unit tests for the Proactive Engagement Service.

Tests cover eligibility checking, utility functions, and API route validation.
"""

import pytest

from ..models.domain import EligibilityCheckResult, UserProfileConsent, UserQuietHours
from ..services.eligibility_checker import EligibilityChecker
from ..utils.helpers import get_tier_from_score, is_within_quiet_hours


# ------------------------------------------------------------------ #
# Eligibility Checker Tests
# ------------------------------------------------------------------ #


class TestEligibilityChecker:
    """Test the eligibility checker logic."""

    def setup_method(self):
        self.checker = EligibilityChecker(
            default_quiet_start="22:00",
            default_quiet_end="07:00",
        )

    def test_consent_denied(self):
        profile = UserProfileConsent(
            user_id="usr_001",
            proactive_messaging_consent=False,
            timezone="Asia/Singapore",
        )
        result = self.checker.check_eligibility(
            profile_consent=profile,
            current_time_iso="2026-03-12T09:00:00+00:00",
        )
        assert not result.eligible
        assert result.skip_reason == "consent_denied"

    def test_consent_granted_outside_quiet_hours(self):
        profile = UserProfileConsent(
            user_id="usr_002",
            proactive_messaging_consent=True,
            quiet_hours=UserQuietHours(start="22:00", end="07:00"),
            timezone="Asia/Singapore",
        )
        # 10:00 SGT is outside quiet hours (22:00-07:00)
        result = self.checker.check_eligibility(
            profile_consent=profile,
            current_time_iso="2026-03-12T02:00:00+00:00",  # 10:00 SGT
        )
        assert result.eligible
        assert result.skip_reason is None

    def test_within_quiet_hours(self):
        profile = UserProfileConsent(
            user_id="usr_003",
            proactive_messaging_consent=True,
            quiet_hours=UserQuietHours(start="22:00", end="07:00"),
            timezone="Asia/Singapore",
        )
        # 23:00 SGT is within quiet hours (22:00-07:00)
        result = self.checker.check_eligibility(
            profile_consent=profile,
            current_time_iso="2026-03-12T15:00:00+00:00",  # 23:00 SGT
        )
        assert not result.eligible
        assert result.skip_reason == "quiet_hours"


# ------------------------------------------------------------------ #
# Utility Function Tests
# ------------------------------------------------------------------ #


class TestGetTierFromScore:
    """Test the affinity score to tier mapping."""

    def test_acquaintance(self):
        assert get_tier_from_score(0.15) == "acquaintance"
        assert get_tier_from_score(0.30) == "acquaintance"

    def test_friend(self):
        assert get_tier_from_score(0.31) == "friend"
        assert get_tier_from_score(0.60) == "friend"

    def test_close_friend(self):
        assert get_tier_from_score(0.61) == "close_friend"
        assert get_tier_from_score(0.80) == "close_friend"

    def test_best_friend(self):
        assert get_tier_from_score(0.81) == "best_friend"
        assert get_tier_from_score(1.0) == "best_friend"


class TestQuietHours:
    """Test the quiet hours utility function."""

    def test_within_spanning_midnight(self):
        # 23:30 SGT should be within 22:00-07:00
        result = is_within_quiet_hours(
            current_time_str="2026-03-12T15:30:00+00:00",
            quiet_start="22:00",
            quiet_end="07:00",
            user_timezone="Asia/Singapore",
        )
        assert result is True

    def test_outside_spanning_midnight(self):
        # 10:00 SGT should be outside 22:00-07:00
        result = is_within_quiet_hours(
            current_time_str="2026-03-12T02:00:00+00:00",
            quiet_start="22:00",
            quiet_end="07:00",
            user_timezone="Asia/Singapore",
        )
        assert result is False

    def test_within_not_spanning_midnight(self):
        # 03:00 SGT should be within 01:00-06:00
        result = is_within_quiet_hours(
            current_time_str="2026-03-11T19:00:00+00:00",
            quiet_start="01:00",
            quiet_end="06:00",
            user_timezone="Asia/Singapore",
        )
        assert result is True


# ------------------------------------------------------------------ #
# API Route Validation Tests
# ------------------------------------------------------------------ #


class TestRouteValidation:
    """Test API route request validation."""

    def setup_method(self):
        from fastapi.testclient import TestClient
        from ..app import create_app

        self.app = create_app()
        self.client = TestClient(self.app)

    def test_health_check(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self):
        response = self.client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_status_endpoint(self):
        response = self.client.get("/api/v1/proactive/status")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "proactive-engagement-service"
        assert "topics_consumed" in data
        assert "topics_published" in data
