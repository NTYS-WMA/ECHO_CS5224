"""
Event publisher for the Proactive Engagement Service.

Publishes domain events to the Internal Asynchronous Messaging Layer.

Topics published:
    - conversation.outbound: Proactive messages for channel delivery.
    - proactive.dispatch.completed: Telemetry event after scan completion.

TO BE UPDATED: Replace the stub broker client with the actual messaging
layer client once the infrastructure component is finalized.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from ..models.events import (
    OutboundResponseItem,
    ProactiveDispatchCompletedEvent,
    ProactiveOutboundEvent,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes Proactive Engagement Service domain events to the messaging layer.
    """

    def __init__(self, broker_url: str, enabled: bool = True):
        self._broker_url = broker_url
        self._enabled = enabled
        self._client = None  # TO BE UPDATED: Initialize actual broker client

    async def connect(self) -> None:
        """
        Establish connection to the message broker.

        TO BE UPDATED: Implement actual broker connection logic.
        """
        if not self._enabled:
            logger.info("Event publishing is disabled; skipping broker connection.")
            return
        logger.info("Event publisher connected to broker at %s", self._broker_url)

    async def disconnect(self) -> None:
        """
        Gracefully close the broker connection.

        TO BE UPDATED: Implement actual broker disconnection logic.
        """
        if self._client:
            pass  # TO BE UPDATED: Close actual broker connection
        logger.info("Event publisher disconnected.")

    async def publish_proactive_outbound(
        self,
        event_id: str,
        user_id: str,
        channel: str,
        conversation_id: str,
        responses: List[OutboundResponseItem],
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Publish a proactive outbound message to conversation.outbound topic.

        This event is consumed by the Channel Gateway / Channel Delivery Worker
        for actual message delivery to the user.

        Args:
            event_id: Unique event identifier.
            user_id: Internal user identifier.
            channel: Delivery channel (e.g., 'telegram').
            conversation_id: Conversation identifier for routing.
            responses: List of response items to deliver.
            correlation_id: Optional correlation ID for tracing.
            metadata: Optional additional metadata.
        """
        event = ProactiveOutboundEvent(
            event_id=event_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            channel=channel,
            conversation_id=conversation_id,
            responses=responses,
            metadata=metadata or {"source": "proactive_engagement"},
        )
        await self._publish("conversation.outbound", event.model_dump_json())

    async def publish_dispatch_completed(
        self,
        event_id: str,
        correlation_id: Optional[str],
        candidates_scanned: int,
        messages_dispatched: int,
        messages_skipped: int,
    ) -> None:
        """
        Publish a proactive.dispatch.completed telemetry event.

        Args:
            event_id: Unique event identifier.
            correlation_id: Correlation ID from the scan trigger.
            candidates_scanned: Total candidates evaluated.
            messages_dispatched: Messages successfully dispatched.
            messages_skipped: Candidates skipped due to policy.
        """
        event = ProactiveDispatchCompletedEvent(
            event_id=event_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            stats={
                "candidates_scanned": candidates_scanned,
                "messages_dispatched": messages_dispatched,
                "messages_skipped": messages_skipped,
            },
        )
        await self._publish("proactive.dispatch.completed", event.model_dump_json())

    async def _publish(self, topic: str, payload: str) -> None:
        """
        Publish a serialized event to the specified topic.

        TO BE UPDATED: Replace with actual broker publish call.
        """
        if not self._enabled:
            logger.debug(
                "Event publishing disabled. Would publish to '%s': %s",
                topic,
                payload[:200],
            )
            return

        try:
            # TO BE UPDATED: Replace with actual broker publish logic
            logger.info("Published event to topic '%s': %s", topic, payload[:200])
        except Exception as e:
            logger.error(
                "Failed to publish event to topic '%s': %s", topic, str(e)
            )
