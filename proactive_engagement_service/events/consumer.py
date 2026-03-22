"""
Event consumer for the Proactive Engagement Service.

Consumes events from the Internal Asynchronous Messaging Layer:
    - proactive.scan.requested: Triggers a proactive engagement scan.

TO BE UPDATED: Replace the stub consumer with the actual messaging
layer consumer once the infrastructure component is finalized.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

from ..models.requests import ProactiveScanTriggerEvent

logger = logging.getLogger(__name__)


class EventConsumer:
    """
    Consumes events from the messaging layer and dispatches them to handlers.
    """

    def __init__(self, broker_url: str, enabled: bool = True):
        self._broker_url = broker_url
        self._enabled = enabled
        self._running = False
        self._scan_handler: Optional[Callable] = None

    def register_scan_handler(self, handler: Callable) -> None:
        """
        Register a handler for proactive.scan.requested events.

        Args:
            handler: Async callable that accepts a ProactiveScanTriggerEvent.
        """
        self._scan_handler = handler
        logger.info("Registered scan handler for proactive.scan.requested")

    async def start(self) -> None:
        """
        Start consuming events from the broker.

        TO BE UPDATED: Implement actual broker subscription logic.
        Currently this is a stub that logs readiness.
        """
        if not self._enabled:
            logger.info("Event consumption is disabled; consumer not started.")
            return

        self._running = True
        logger.info(
            "Event consumer started, listening on topic 'proactive.scan.requested' "
            "at %s",
            self._broker_url,
        )

        # TO BE UPDATED: Replace with actual broker consumption loop, e.g.:
        # async for message in broker.subscribe("proactive.scan.requested"):
        #     await self._handle_message(message)

    async def stop(self) -> None:
        """Stop the event consumer gracefully."""
        self._running = False
        logger.info("Event consumer stopped.")

    async def _handle_message(self, raw_payload: str) -> None:
        """
        Parse and dispatch a raw event message.

        TO BE UPDATED: Called by the actual broker consumption loop.

        Args:
            raw_payload: JSON-serialized event payload.
        """
        try:
            data = json.loads(raw_payload)
            event_type = data.get("event_type", "")

            if event_type == "proactive.scan.requested" and self._scan_handler:
                event = ProactiveScanTriggerEvent(**data)
                await self._scan_handler(event)
            else:
                logger.warning("Unhandled event type: %s", event_type)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse event payload: %s", str(e))
        except Exception as e:
            logger.error("Error handling event: %s", str(e))
