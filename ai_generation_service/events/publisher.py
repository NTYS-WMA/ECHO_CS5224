"""
Event publisher for the AI Generation Service.

Publishes domain events to the Internal Asynchronous Messaging Layer.
Currently uses an abstract interface; the concrete broker implementation
(e.g., Redis Streams, RabbitMQ, or a local in-process queue) will be
injected at startup.

TO BE UPDATED: Replace the stub broker client with the actual messaging
layer client once the infrastructure component is finalized.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..models.events import GenerationCompletedEvent, GenerationFailedEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes AI Generation Service domain events to the messaging layer.

    Topics:
        - ai.generation.failed: Emitted on hard generation failures.
        - ai.generation.completed: Emitted for telemetry on successful generation.
    """

    def __init__(self, broker_url: str, enabled: bool = True):
        """
        Initialize the event publisher.

        Args:
            broker_url: Connection URL for the message broker.
            enabled: If False, events are logged but not published.
        """
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
        # TO BE UPDATED: Connect to the actual broker (e.g., Redis, RabbitMQ)
        logger.info("Event publisher connected to broker at %s", self._broker_url)

    async def disconnect(self) -> None:
        """
        Gracefully close the broker connection.

        TO BE UPDATED: Implement actual broker disconnection logic.
        """
        if self._client:
            # TO BE UPDATED: Close actual broker connection
            pass
        logger.info("Event publisher disconnected.")

    async def publish_generation_failed(
        self,
        event_id: str,
        user_id: str,
        operation: str,
        error_code: str,
        retryable: bool,
        fallback_attempted: bool,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Publish an ai.generation.failed event.

        Args:
            event_id: Unique event identifier.
            user_id: Internal user identifier.
            operation: The failed operation type.
            error_code: Machine-readable error code.
            retryable: Whether the failure is retryable.
            fallback_attempted: Whether fallback was attempted.
            correlation_id: Optional correlation ID for tracing.
        """
        event = GenerationFailedEvent(
            event_id=event_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            operation=operation,
            error_code=error_code,
            retryable=retryable,
            fallback_attempted=fallback_attempted,
        )
        await self._publish("ai.generation.failed", event.model_dump_json())

    async def publish_generation_completed(
        self,
        event_id: str,
        user_id: str,
        operation: str,
        model: str,
        usage: Optional[dict] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Publish an ai.generation.completed event for telemetry.

        Args:
            event_id: Unique event identifier.
            user_id: Internal user identifier.
            operation: The completed operation type.
            model: Model identifier used.
            usage: Token usage statistics.
            correlation_id: Optional correlation ID for tracing.
        """
        event = GenerationCompletedEvent(
            event_id=event_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            operation=operation,
            model=model,
            usage=usage,
        )
        await self._publish("ai.generation.completed", event.model_dump_json())

    async def _publish(self, topic: str, payload: str) -> None:
        """
        Publish a serialized event to the specified topic.

        TO BE UPDATED: Replace with actual broker publish call.

        Args:
            topic: The event topic/channel name.
            payload: JSON-serialized event payload.
        """
        if not self._enabled:
            logger.debug("Event publishing disabled. Would publish to '%s': %s", topic, payload)
            return

        try:
            # TO BE UPDATED: Replace with actual broker publish logic, e.g.:
            # await self._client.publish(topic, payload)
            logger.info("Published event to topic '%s': %s", topic, payload[:200])
        except Exception as e:
            # Event publishing failures should not break the main request flow.
            logger.error("Failed to publish event to topic '%s': %s", topic, str(e))
