"""
HTTP client for the AI Generation Service.

Used by the Proactive Engagement Service to request AI-generated
proactive outreach messages.

Interface called:
    - POST /api/v1/generation/proactive-messages
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class AIGenerationServiceClient:
    """HTTP client for the AI Generation Service."""

    def __init__(self, base_url: str, timeout_seconds: int = 30):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the AI Generation Service.
            timeout_seconds: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def generate_proactive_message(
        self,
        user_id: str,
        relationship_tier: str,
        affinity_score: float,
        days_inactive: int,
        recent_summary: Optional[str] = None,
        timezone: Optional[str] = None,
        max_tokens: int = 120,
        tone: str = "friendly",
        correlation_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Request an AI-generated proactive outreach message.

        Calls: POST /api/v1/generation/proactive-messages

        Args:
            user_id: Internal user identifier.
            relationship_tier: User's relationship tier.
            affinity_score: User's affinity score (0-1).
            days_inactive: Days since last interaction.
            recent_summary: Optional recent memory summary.
            timezone: Optional user timezone.
            max_tokens: Maximum tokens for the generated message.
            tone: Desired tone.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            Dict with 'response_id', 'output', 'model', and optional 'usage',
            or None if generation fails.
        """
        url = f"{self._base_url}/api/v1/generation/proactive-messages"
        payload = {
            "user_id": user_id,
            "relationship": {
                "tier": relationship_tier,
                "affinity_score": affinity_score,
                "days_inactive": days_inactive,
            },
            "context": {},
            "constraints": {
                "max_tokens": max_tokens,
                "tone": tone,
            },
        }

        if recent_summary:
            payload["context"]["recent_summary"] = recent_summary
        if timezone:
            payload["context"]["timezone"] = timezone
        if correlation_id:
            payload["correlation_id"] = correlation_id

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "AI Generation Service returned HTTP %d for user %s: %s",
                e.response.status_code,
                user_id,
                str(e),
            )
            return None
        except httpx.TimeoutException:
            logger.error(
                "AI Generation Service timed out for user %s after %ds",
                user_id,
                self._timeout,
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to generate proactive message for user %s: %s",
                user_id,
                str(e),
            )
            return None
