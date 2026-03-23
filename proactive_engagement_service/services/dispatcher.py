"""
HTTP client for the Message Dispatch Hub.

The Message Dispatch Hub is the central outbound message routing service
in the ECHO platform. It accepts outbound message payloads and routes
them to the appropriate channel gateway (Telegram, WhatsApp, Web, etc.).

Interface called:
    - POST /api/v1/messages/outbound — Send an outbound message

TO BE UPDATED: The Message Dispatch Hub has not yet published its
official API. The contract below is assumed based on the architecture
specification and will be updated once the owning team confirms.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from ..models.domain import ScheduledTask, TaskPayload
from ..models.events import OutboundMessagePayload
from ..utils.helpers import generate_event_id, utc_now

logger = logging.getLogger(__name__)


class MessageDispatchClient:
    """
    HTTP client for the Message Dispatch Hub.

    Sends outbound message payloads for delivery to end users.
    """

    def __init__(self, base_url: str, timeout_seconds: int = 15):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the Message Dispatch Hub.
            timeout_seconds: HTTP request timeout.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def dispatch_message(self, task: ScheduledTask) -> Dict[str, Any]:
        """
        Send an outbound message to the Message Dispatch Hub.

        Constructs the outbound payload from the task's payload and target
        information, then POSTs it to the dispatch hub.

        Args:
            task: The ScheduledTask to dispatch.

        Returns:
            Dict with dispatch result:
                - success (bool): Whether dispatch succeeded.
                - status_code (int): HTTP status code (0 if connection failed).
                - error (str | None): Error message if failed.
                - response (dict | None): Response body if successful.
        """
        # Build the outbound message payload
        outbound = OutboundMessagePayload(
            event_id=generate_event_id(),
            task_id=task.task_id,
            user_id=task.user_id,
            channel=task.channel,
            conversation_id=task.conversation_id,
            message_type=task.payload.message_type,
            content=task.payload.content,
            template_id=task.payload.template_id,
            template_variables=task.payload.template_variables,
            attachments=task.payload.attachments,
            metadata=task.metadata,
        )

        url = f"{self._base_url}/api/v1/messages/outbound"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=outbound.model_dump(mode="json"),
                )
                response.raise_for_status()
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "error": None,
                    "response": response.json(),
                }
        except httpx.HTTPStatusError as e:
            error_msg = (
                f"Dispatch Hub returned HTTP {e.response.status_code}: "
                f"{e.response.text[:200]}"
            )
            logger.error(
                "Failed to dispatch task %s: %s", task.task_id, error_msg
            )
            return {
                "success": False,
                "status_code": e.response.status_code,
                "error": error_msg,
                "response": None,
            }
        except httpx.TimeoutException:
            error_msg = f"Dispatch Hub timed out after {self._timeout}s"
            logger.error(
                "Failed to dispatch task %s: %s", task.task_id, error_msg
            )
            return {
                "success": False,
                "status_code": 0,
                "error": error_msg,
                "response": None,
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(
                "Failed to dispatch task %s: %s", task.task_id, error_msg
            )
            return {
                "success": False,
                "status_code": 0,
                "error": error_msg,
                "response": None,
            }
