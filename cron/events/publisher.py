"""
Event publisher for the Cron Service v4.0.

Publishes events to the Internal Messaging Layer via HTTP, and also
supports direct HTTP callback delivery to registered service URLs.
"""

import asyncio
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes events to the event broker and/or direct HTTP callbacks.
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
            broker_url, enabled,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        logger.info("EventPublisher closed.")

    # ------------------------------------------------------------------ #
    # Publish to event broker
    # ------------------------------------------------------------------ #

    async def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Publish an event to the broker via HTTP POST.
        Retries on transient failures.
        """
        if not self._enabled:
            logger.debug("Event publishing disabled. Skipping topic=%s.", topic)
            return False

        url = f"{self._broker_url}/api/v1/events"
        body = {"topic": topic, "payload": payload}
        return await self._post_with_retry(url, body, label=f"topic={topic}")

    # ------------------------------------------------------------------ #
    # Direct HTTP callback
    # ------------------------------------------------------------------ #

    async def callback(self, url: str, payload: Dict[str, Any]) -> bool:
        """
        POST the event directly to a callback URL registered by the caller.
        Retries on transient failures.
        """
        if not self._enabled:
            logger.debug("Event publishing disabled. Skipping callback=%s.", url)
            return False

        return await self._post_with_retry(url, payload, label=f"callback={url}")

    # ------------------------------------------------------------------ #
    # Internal retry logic
    # ------------------------------------------------------------------ #

    async def _post_with_retry(
        self, url: str, body: Dict[str, Any], label: str
    ) -> bool:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 2):
            try:
                client = await self._get_client()
                response = await client.post(url, json=body)
                response.raise_for_status()
                logger.info("Event published to %s.", label)
                return True
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if attempt <= self._max_retries:
                    wait = 0.5 * attempt
                    logger.warning(
                        "Publish attempt %d/%d to %s failed (%s). Retrying in %.1fs…",
                        attempt, self._max_retries + 1, label, str(exc), wait,
                    )
                    await asyncio.sleep(wait)
            except Exception as exc:
                last_error = exc
                break

        logger.error(
            "Failed to publish event to %s after %d attempts: %s",
            label, self._max_retries + 1, str(last_error),
        )
        return False
