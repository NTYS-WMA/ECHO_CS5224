"""
HTTP client for the Memory Service (MyMem0).

Used by the Proactive Engagement Service to retrieve recent memory
summaries for personalization of proactive outreach messages.

Interface called:
    - POST /search (semantic memory search)

TO BE UPDATED: The Memory Service integration guide documents the /search
endpoint for semantic search. We use this to retrieve the most relevant
recent memories as context for proactive message generation.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MemoryServiceClient:
    """HTTP client for the Memory Service (MyMem0)."""

    def __init__(self, base_url: str, timeout_seconds: int = 10):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the Memory Service.
            timeout_seconds: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def get_recent_summary(self, user_id: str) -> Optional[str]:
        """
        Retrieve a recent memory summary for the user.

        Uses the Memory Service's semantic search endpoint to find the most
        relevant recent memories and concatenates them into a summary string.

        Calls: POST /search

        Args:
            user_id: Internal user identifier.

        Returns:
            A concatenated summary string, or None if no memories are found.
        """
        url = f"{self._base_url}/search"
        payload = {
            "query": "recent activities and preferences",
            "user_id": user_id,
            "limit": 5,
            "threshold": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if not results:
                return None

            # Concatenate the top memories into a summary
            summaries = [r.get("memory", "") for r in results if r.get("memory")]
            if not summaries:
                return None

            return "; ".join(summaries)

        except httpx.HTTPStatusError as e:
            logger.warning(
                "Memory Service returned HTTP %d for user %s: %s",
                e.response.status_code,
                user_id,
                str(e),
            )
            return None
        except Exception as e:
            logger.warning(
                "Failed to retrieve memory summary for user %s: %s",
                user_id,
                str(e),
            )
            return None
