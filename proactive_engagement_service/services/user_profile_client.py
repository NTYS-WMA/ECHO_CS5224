"""
HTTP client for the User Profile Service.

Used by the Proactive Engagement Service to retrieve user consent flags,
quiet hours preferences, and timezone information for eligibility checks.

Interface called:
    - GET /api/v1/users/{user_id}/profile
"""

import logging
from typing import Optional

import httpx

from ..models.domain import UserProfileConsent, UserQuietHours

logger = logging.getLogger(__name__)


class UserProfileServiceClient:
    """HTTP client for the User Profile Service."""

    def __init__(self, base_url: str, timeout_seconds: int = 10):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the User Profile Service.
            timeout_seconds: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def get_user_consent_and_preferences(
        self, user_id: str
    ) -> Optional[UserProfileConsent]:
        """
        Retrieve user consent and quiet hours preferences.

        Calls: GET /api/v1/users/{user_id}/profile

        Extracts only the fields relevant to proactive engagement eligibility:
        consent.proactive_messaging, preferences.quiet_hours, and timezone.

        Args:
            user_id: Internal user identifier.

        Returns:
            UserProfileConsent object, or None if the profile is unavailable.
        """
        url = f"{self._base_url}/api/v1/users/{user_id}/profile"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            # Extract consent
            consent = data.get("consent", {})
            proactive_consent = consent.get("proactive_messaging", False)

            # Extract quiet hours
            preferences = data.get("preferences", {})
            quiet_hours_data = preferences.get("quiet_hours")
            quiet_hours = None
            if quiet_hours_data:
                quiet_hours = UserQuietHours(
                    start=quiet_hours_data.get("start", "22:00"),
                    end=quiet_hours_data.get("end", "07:00"),
                )

            # Extract timezone
            user_timezone = data.get("timezone")

            return UserProfileConsent(
                user_id=user_id,
                proactive_messaging_consent=proactive_consent,
                quiet_hours=quiet_hours,
                timezone=user_timezone,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("User profile not found for user %s", user_id)
                return None
            logger.error(
                "User Profile Service returned HTTP %d for user %s: %s",
                e.response.status_code,
                user_id,
                str(e),
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to get user profile for user %s: %s", user_id, str(e)
            )
            return None

    async def get_user_channel_info(self, user_id: str) -> Optional[dict]:
        """
        Retrieve user channel and conversation information.

        Calls: GET /api/v1/users/{user_id}/profile

        Extracts channel and external_user_id for outbound delivery routing.

        TO BE UPDATED: The User Profile Service response may not include
        conversation_id directly. A separate lookup or derivation may be needed.

        Args:
            user_id: Internal user identifier.

        Returns:
            Dict with 'channel', 'external_user_id', and derived 'conversation_id',
            or None if unavailable.
        """
        url = f"{self._base_url}/api/v1/users/{user_id}/profile"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            channel = data.get("channel", "telegram")
            external_user_id = data.get("external_user_id", "")

            # TO BE UPDATED: Derive conversation_id from channel and external_user_id.
            # This derivation assumes the Telegram convention used in the architecture spec.
            platform_chat_id = external_user_id.split(":")[-1] if ":" in external_user_id else external_user_id
            conversation_id = f"{channel}-chat-{platform_chat_id}"

            return {
                "channel": channel,
                "external_user_id": external_user_id,
                "conversation_id": conversation_id,
            }

        except Exception as e:
            logger.error(
                "Failed to get channel info for user %s: %s", user_id, str(e)
            )
            return None
