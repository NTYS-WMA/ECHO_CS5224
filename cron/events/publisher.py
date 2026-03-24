"""
Event publisher for the Cron Service v2.0.

Publishes task lifecycle events to the Internal Messaging Layer via HTTP.

Topics published:
    - cron.task.dispatched: A task was successfully dispatched.
    - cron.task.failed: A task exhausted retries and failed permanently.
"""

import asyncio
import json
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes events to the Internal Messaging Layer via HTTP POST.

    Each event is posted to ``{broker_url}/api/v1/events`` with the topic
    included in the JSON body.  Failed publishes are retried with a short
    linear back-off.  All publish calls are best-effort — failures are
    logged but never propagated to the caller.
    """

    def __init__(
        self,
        broker_url: str,
        enabled: bool = True,
        timeout_seconds: int = 5,
        max_retries: int = 2,
    ):
        self._broker_url = broker_url.rstrip("/")
        self._enabled = enabled
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        logger.info(
            "EventPublisher initialized (broker=%s, enabled=%s).",
            broker_url,
            enabled,
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create the shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        logger.info("EventPublisher closed.")

    # ------------------------------------------------------------------ #
    # Publishing
    # ------------------------------------------------------------------ #

    async def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Publish an event to a topic.

        The event is POSTed as JSON to the broker endpoint.  On transient
        failures the call is retried up to ``max_retries`` times.

        Args:
            topic: Event topic name (e.g. ``cron.task.dispatched``).
            payload: JSON-serializable event body.

        Returns:
            True if published successfully, False otherwise.
        """
        if not self._enabled:
            logger.debug("Event publishing disabled. Skipping topic=%s.", topic)
            return False

        url = f"{self._broker_url}/api/v1/events"
        body = {"topic": topic, "payload": payload}

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 2):  # 1-based, inclusive
            try:
                client = await self._get_client()
                response = await client.post(url, json=body)
                response.raise_for_status()
                logger.info(
                    "Event published to topic=%s (event_type=%s, event_id=%s).",
                    topic,
                    payload.get("event_type", "unknown"),
                    payload.get("event_id", "unknown"),
                )
                return True
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if attempt <= self._max_retries:
                    wait = 0.5 * attempt
                    logger.warning(
                        "Publish attempt %d/%d to topic=%s failed (%s). "
                        "Retrying in %.1fs …",
                        attempt,
                        self._max_retries + 1,
                        topic,
                        str(exc),
                        wait,
                    )
                    await asyncio.sleep(wait)
            except Exception as exc:
                last_error = exc
                break  # non-retryable

        logger.error(
            "Failed to publish event to topic=%s after %d attempts: %s",
            topic,
            self._max_retries + 1,
            str(last_error),
        )
        return False
