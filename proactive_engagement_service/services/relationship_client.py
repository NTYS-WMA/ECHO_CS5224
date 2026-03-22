"""
HTTP client for the Relationship Service.

Used by the Proactive Engagement Service to:
1. Search for proactive engagement candidates based on inactivity and affinity.
2. Retrieve relationship context for individual users.

Interfaces called:
    - POST /api/v1/relationships/proactive-candidates/search
    - GET /api/v1/relationships/{user_id}/context
"""

import logging
from typing import List, Optional

import httpx

from ..models.requests import CandidateSearchFilters, TimeContext
from ..models.responses import CandidateItem

logger = logging.getLogger(__name__)


class RelationshipServiceClient:
    """HTTP client for the Relationship Service."""

    def __init__(self, base_url: str, timeout_seconds: int = 15):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the Relationship Service.
            timeout_seconds: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def search_proactive_candidates(
        self,
        filters: CandidateSearchFilters,
        time_context: TimeContext,
        correlation_id: Optional[str] = None,
    ) -> List[CandidateItem]:
        """
        Search for proactive engagement candidates.

        Calls: POST /api/v1/relationships/proactive-candidates/search

        Args:
            filters: Candidate selection filters.
            time_context: Time context for the scan.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            List of CandidateItem objects.
        """
        url = f"{self._base_url}/api/v1/relationships/proactive-candidates/search"
        payload = {
            "filters": filters.model_dump(),
            "time_context": time_context.model_dump(),
        }
        if correlation_id:
            payload["correlation_id"] = correlation_id

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return [CandidateItem(**c) for c in data.get("candidates", [])]
        except httpx.HTTPStatusError as e:
            logger.error(
                "Relationship Service returned HTTP %d for candidate search: %s",
                e.response.status_code,
                str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to search proactive candidates: %s", str(e)
            )
            raise

    async def get_relationship_context(self, user_id: str) -> Optional[dict]:
        """
        Retrieve relationship context for a specific user.

        Calls: GET /api/v1/relationships/{user_id}/context

        Args:
            user_id: Internal user identifier.

        Returns:
            Relationship context dict, or None if unavailable.
        """
        url = f"{self._base_url}/api/v1/relationships/{user_id}/context"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("No relationship context found for user %s", user_id)
                return None
            logger.error(
                "Relationship Service returned HTTP %d for user %s: %s",
                e.response.status_code,
                user_id,
                str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to get relationship context for user %s: %s",
                user_id,
                str(e),
            )
            raise
