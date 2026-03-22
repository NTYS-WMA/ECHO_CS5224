"""
HTTP client for the AI Generation Service.

Used by the Proactive Engagement Service to request AI-generated
proactive outreach messages via the template-based execution engine.

Interface called:
    - POST /api/v1/generation/execute  (primary, v2.0)
    - POST /api/v1/generation/proactive-messages  (legacy fallback)
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Default template ID for proactive outreach.
# TO BE UPDATED: The template_id may change if the business team registers
# a custom template via POST /api/v1/templates.
DEFAULT_PROACTIVE_TEMPLATE_ID = "tpl_proactive_outreach"


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

    def _build_context_block(
        self,
        relationship_tier: str,
        affinity_score: float,
        days_inactive: int,
        recent_summary: Optional[str] = None,
        timezone: Optional[str] = None,
        tone: str = "friendly",
    ) -> str:
        """
        Assemble the context_block variable for the proactive outreach template.

        The business layer (this service) is responsible for assembling the
        core prompt content. The AI service only manages the system-level
        prompt and renders the template.

        Args:
            relationship_tier: User's relationship tier.
            affinity_score: User's affinity score (0-1).
            days_inactive: Days since last interaction.
            recent_summary: Optional recent memory summary.
            timezone: Optional user timezone.
            tone: Desired tone for the message.

        Returns:
            Formatted context block string.
        """
        parts = [
            f"Relationship tier: {relationship_tier}",
            f"Affinity score: {affinity_score:.2f}",
            f"Days since last interaction: {days_inactive}",
            f"Desired tone: {tone}",
        ]
        if timezone:
            parts.append(f"User timezone: {timezone}")
        if recent_summary:
            parts.append(f"Recent context about the user: {recent_summary}")
        return "\n".join(parts)

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
        template_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Request an AI-generated proactive outreach message.

        Uses the template-based /execute endpoint (v2.0). The business layer
        assembles the context_block variable; the AI service renders the
        template and executes the generation.

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
            template_id: Optional custom template ID (defaults to tpl_proactive_outreach).

        Returns:
            Dict with 'response_id', 'template_id', 'output', 'model',
            and optional 'usage', or None if generation fails.
        """
        # Assemble the context_block — this is the business layer's responsibility
        context_block = self._build_context_block(
            relationship_tier=relationship_tier,
            affinity_score=affinity_score,
            days_inactive=days_inactive,
            recent_summary=recent_summary,
            timezone=timezone,
            tone=tone,
        )

        url = f"{self._base_url}/api/v1/generation/execute"
        payload = {
            "user_id": user_id,
            "template_id": template_id or DEFAULT_PROACTIVE_TEMPLATE_ID,
            "variables": {
                "context_block": context_block,
            },
            "generation_config": {
                "max_tokens": max_tokens,
            },
        }

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
