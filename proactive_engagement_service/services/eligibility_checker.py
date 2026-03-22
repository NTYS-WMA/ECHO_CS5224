"""
Eligibility checker for proactive engagement candidates.

Enforces consent, quiet-hours, and other policy checks before allowing
a proactive message to be generated and dispatched.
"""

import logging
from datetime import datetime, timezone

from ..models.domain import EligibilityCheckResult, UserProfileConsent
from ..utils.helpers import is_within_quiet_hours

logger = logging.getLogger(__name__)


class EligibilityChecker:
    """
    Evaluates whether a candidate is eligible for proactive messaging.

    Checks performed (in order):
    1. Consent check: User must have proactive_messaging consent enabled.
    2. Quiet hours check: Current time must not fall within user's quiet hours.
    """

    def __init__(self, default_quiet_start: str = "22:00", default_quiet_end: str = "07:00"):
        """
        Initialize the eligibility checker.

        Args:
            default_quiet_start: Default quiet hours start if user has no preference.
            default_quiet_end: Default quiet hours end if user has no preference.
        """
        self._default_quiet_start = default_quiet_start
        self._default_quiet_end = default_quiet_end

    def check_eligibility(
        self,
        profile_consent: UserProfileConsent,
        current_time_iso: str,
    ) -> EligibilityCheckResult:
        """
        Check if a user is eligible for proactive messaging.

        Args:
            profile_consent: User's consent and quiet hours data.
            current_time_iso: Current time in ISO 8601 format.

        Returns:
            EligibilityCheckResult indicating eligibility status.
        """
        user_id = profile_consent.user_id

        # 1. Consent check
        if not profile_consent.proactive_messaging_consent:
            logger.debug(
                "User %s ineligible: proactive_messaging consent denied", user_id
            )
            return EligibilityCheckResult(
                user_id=user_id,
                eligible=False,
                skip_reason="consent_denied",
            )

        # 2. Quiet hours check
        user_timezone = profile_consent.timezone or "UTC"
        quiet_start = (
            profile_consent.quiet_hours.start
            if profile_consent.quiet_hours
            else self._default_quiet_start
        )
        quiet_end = (
            profile_consent.quiet_hours.end
            if profile_consent.quiet_hours
            else self._default_quiet_end
        )

        if is_within_quiet_hours(current_time_iso, quiet_start, quiet_end, user_timezone):
            logger.debug(
                "User %s ineligible: within quiet hours (%s-%s, tz=%s)",
                user_id,
                quiet_start,
                quiet_end,
                user_timezone,
            )
            return EligibilityCheckResult(
                user_id=user_id,
                eligible=False,
                skip_reason="quiet_hours",
            )

        # All checks passed
        return EligibilityCheckResult(
            user_id=user_id,
            eligible=True,
            skip_reason=None,
        )
