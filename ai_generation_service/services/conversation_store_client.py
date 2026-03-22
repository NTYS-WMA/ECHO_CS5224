"""
Client for the Conversation Persistence Store.

Used by the AI Generation Service to retrieve conversation messages
when processing summarization requests that reference a message window
by ID range.

TO BE UPDATED: The Conversation Persistence Store endpoint and API
contract are assumed based on the architecture spec. Update this client
once the store's API is finalized and deployed.
"""

import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


class ConversationStoreClient:
    """
    HTTP client for the Conversation Persistence Store.

    Provides methods to retrieve conversation messages by window range.
    """

    def __init__(self, base_url: str, timeout_seconds: int = 10):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the Conversation Persistence Store.
            timeout_seconds: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def get_messages_by_window(
        self,
        conversation_id: str,
        from_message_id: str,
        to_message_id: str,
    ) -> List[dict]:
        """
        Retrieve conversation messages within a specified window.

        TO BE UPDATED: This endpoint is assumed based on the architecture spec.
        The actual Conversation Persistence Store API may differ.

        Assumed endpoint:
            GET /api/v1/conversations/{conversation_id}/messages
                ?from_id={from_message_id}&to_id={to_message_id}

        Args:
            conversation_id: The conversation identifier.
            from_message_id: Starting message ID (inclusive).
            to_message_id: Ending message ID (inclusive).

        Returns:
            List of message dicts with 'role', 'content', and 'timestamp' keys.
        """
        url = f"{self._base_url}/api/v1/conversations/{conversation_id}/messages"
        params = {
            "from_id": from_message_id,
            "to_id": to_message_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("messages", [])
        except httpx.HTTPStatusError as e:
            logger.error(
                "Conversation store returned HTTP %d for conversation %s: %s",
                e.response.status_code,
                conversation_id,
                str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to retrieve messages from conversation store for %s: %s",
                conversation_id,
                str(e),
            )
            raise
