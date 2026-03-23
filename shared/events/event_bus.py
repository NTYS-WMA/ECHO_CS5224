"""
In-Process Async Event Bus
==========================

Lightweight pub/sub event bus using asyncio queues.

This is the "Internal Asynchronous Messaging Layer" from the architecture doc,
implemented as an in-process component for the single-EC2 deployment model.

Each topic gets its own asyncio.Queue. Subscribers register an async callback
and the bus dispatches events to all subscribers of that topic concurrently.

Swap this for Redis Streams / RabbitMQ / SQS when scaling beyond one host.

Usage:
    from shared.events.event_bus import event_bus

    # Subscribe
    async def handle_message(event: dict):
        print(event)

    event_bus.subscribe("conversation.message.received", handle_message)

    # Publish
    await event_bus.publish("conversation.message.received", {"event_id": "evt-001", ...})
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Type alias for subscriber callbacks
Subscriber = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Simple in-process async pub/sub event bus."""

    def __init__(self) -> None:
        # topic -> list of async callback functions
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        # track background dispatch tasks so they don't get garbage-collected
        self._background_tasks: set[asyncio.Task] = set()

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        """Register an async callback for a topic."""
        self._subscribers[topic].append(callback)
        logger.info("Subscribed %s to topic '%s'", callback.__qualname__, topic)

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        """
        Publish an event to a topic.

        All subscribers are invoked concurrently as background tasks so the
        publisher is never blocked by slow consumers.
        """
        subscribers = self._subscribers.get(topic, [])
        if not subscribers:
            logger.debug("No subscribers for topic '%s' — event dropped: %s", topic, event.get("event_id", "?"))
            return

        logger.info(
            "Publishing event '%s' to topic '%s' (%d subscriber(s))",
            event.get("event_id", "?"),
            topic,
            len(subscribers),
        )

        for callback in subscribers:
            task = asyncio.create_task(self._safe_dispatch(topic, callback, event))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _safe_dispatch(self, topic: str, callback: Subscriber, event: dict[str, Any]) -> None:
        """Invoke a subscriber inside a try/except so one failure doesn't break others."""
        try:
            await callback(event)
        except Exception:
            logger.exception(
                "Subscriber %s failed on topic '%s', event_id=%s",
                callback.__qualname__,
                topic,
                event.get("event_id", "?"),
            )

    def list_topics(self) -> list[str]:
        """Return all topics that have at least one subscriber."""
        return [t for t, subs in self._subscribers.items() if subs]


#Module-level singleton
event_bus = EventBus()
