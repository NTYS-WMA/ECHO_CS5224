"""
Scheduler engine for the Cron Service v4.0.

A database-backed background loop that:
1. Polls DB Manager for due events (next_fire_at <= now, status = 'active').
2. Dispatches each event via EventPublisher (topic) or HTTP callback.
3. Updates the event status in DB (completed for one-time, next_fire_at for recurring).
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..clients.db_manager_client import DBManagerClient
from ..events.publisher import EventPublisher
from ..models.events import CronTriggeredEvent
from ..models.responses import ManualTriggerResponse
from ..utils.helpers import compute_next_run_at, generate_event_id, utc_now

logger = logging.getLogger(__name__)


class CronScheduler:
    """
    Database-backed cron scheduler that polls for due events and dispatches them.
    """

    def __init__(
        self,
        publisher: EventPublisher,
        db_client: DBManagerClient,
        tick_interval_seconds: int = 30,
    ):
        self._publisher = publisher
        self._db_client = db_client
        self._tick_interval = tick_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_tick_at: Optional[datetime] = None
        self._total_polled = 0
        self._total_fired = 0

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def running(self) -> bool:
        return self._running

    @property
    def tick_interval_seconds(self) -> int:
        return self._tick_interval

    @property
    def last_tick_at(self) -> Optional[datetime]:
        return self._last_tick_at

    # ------------------------------------------------------------------ #
    # Start / Stop
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        if self._running:
            logger.warning("Scheduler is already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info(
            "Cron scheduler started (tick_interval=%ds).",
            self._tick_interval,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Cron scheduler stopped.")

    # ------------------------------------------------------------------ #
    # Tick loop
    # ------------------------------------------------------------------ #

    async def _tick_loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error("Tick failed: %s", str(e), exc_info=True)
            try:
                await asyncio.sleep(self._tick_interval)
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        """Single tick: poll DB for due events and fire them."""
        now = utc_now()
        self._last_tick_at = now

        # Poll DB Manager for due events
        try:
            due_events = await self._db_client.poll_due_events(now=now, limit=50)
        except Exception as e:
            logger.error("Failed to poll due events from DB Manager: %s", str(e))
            return

        self._total_polled += len(due_events)

        if not due_events:
            return

        fired = 0
        for event_data in due_events:
            try:
                success = await self._fire_event(event_data, now)
                if success:
                    fired += 1
                    self._total_fired += 1
            except Exception as e:
                logger.error(
                    "Error firing event %s (%s): %s",
                    event_data.get("id"),
                    event_data.get("event_name"),
                    str(e),
                )
                # Mark as failed in DB
                try:
                    await self._db_client.update_status(
                        event_data["id"], "failed"
                    )
                except Exception:
                    pass

        if fired > 0:
            logger.info("Tick completed: %d event(s) fired.", fired)

    # ------------------------------------------------------------------ #
    # Fire a single event
    # ------------------------------------------------------------------ #

    async def _fire_event(
        self, event_data: Dict[str, Any], now: datetime
    ) -> bool:
        """Dispatch an event and update its DB record."""
        event_id = event_data["id"]
        event_name = event_data.get("event_name", "unknown")
        event_type = event_data.get("event_type", "one_time")
        topic = event_data.get("topic")
        callback_url = event_data.get("callback_url")
        payload = event_data.get("payload", {})

        # Build the triggered event envelope
        triggered = CronTriggeredEvent(
            event_id=generate_event_id(),
            event_type=topic or event_name,
            scheduled_event_id=event_id,
            event_name=event_name,
            caller_service=event_data.get("caller_service", "unknown"),
            payload=payload,
            correlation_id=event_data.get("correlation_id"),
            group_key=event_data.get("group_key"),
        )

        # Dispatch: prefer topic (via broker), fall back to callback_url
        success = False
        if topic:
            success = await self._publisher.publish(
                topic=topic,
                payload=triggered.model_dump(mode="json"),
            )
        if callback_url:
            cb_success = await self._publisher.callback(
                url=callback_url,
                payload=triggered.model_dump(mode="json"),
            )
            success = success or cb_success

        if not success:
            logger.error(
                "Event '%s' (%s) failed to dispatch.", event_name, event_id
            )
            return False

        logger.info(
            "Event '%s' (%s) fired → topic=%s, callback=%s",
            event_name, event_id, topic, callback_url,
        )

        # Determine next state
        if event_type == "recurring":
            # Check if max_fires reached
            fire_count = event_data.get("fire_count", 0) + 1
            max_fires = event_data.get("max_fires")
            if max_fires is not None and fire_count >= max_fires:
                new_status = "completed"
                next_fire = None
            else:
                new_status = "active"
                next_fire = compute_next_run_at(
                    cron_expression=event_data.get("cron_expression"),
                    interval_seconds=event_data.get("interval_seconds"),
                    from_time=now,
                )
        else:
            # One-time event → mark completed
            new_status = "completed"
            next_fire = None

        # Update DB
        await self._db_client.mark_fired(
            event_id=event_id,
            fired_at=now,
            next_fire_at=next_fire,
            new_status=new_status,
        )

        return True

    # ------------------------------------------------------------------ #
    # Manual trigger
    # ------------------------------------------------------------------ #

    async def trigger(
        self,
        event_id: str,
        payload_override: Optional[Dict[str, Any]] = None,
    ) -> ManualTriggerResponse:
        """Manually trigger a scheduled event (for ops/testing)."""
        event_data = await self._db_client.get_event(event_id)
        if event_data is None:
            return ManualTriggerResponse(
                event_id=event_id,
                event_name="unknown",
                published=False,
                error=f"Event '{event_id}' not found.",
            )

        payload = payload_override if payload_override is not None else event_data.get("payload", {})
        topic = event_data.get("topic")
        callback_url = event_data.get("callback_url")
        event_name = event_data.get("event_name", "unknown")

        triggered = CronTriggeredEvent(
            event_id=generate_event_id(),
            event_type=topic or event_name,
            scheduled_event_id=event_id,
            event_name=event_name,
            caller_service=event_data.get("caller_service", "unknown"),
            payload=payload,
            correlation_id=event_data.get("correlation_id"),
            group_key=event_data.get("group_key"),
        )

        success = False
        if topic:
            success = await self._publisher.publish(
                topic=topic,
                payload=triggered.model_dump(mode="json"),
            )
        if callback_url:
            cb_success = await self._publisher.callback(
                url=callback_url,
                payload=triggered.model_dump(mode="json"),
            )
            success = success or cb_success

        return ManualTriggerResponse(
            event_id=event_id,
            event_name=event_name,
            topic=topic,
            callback_url=callback_url,
            published=success,
            error=None if success else "Failed to dispatch event.",
        )

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "tick_interval_seconds": self._tick_interval,
            "total_events_polled": self._total_polled,
            "total_events_fired": self._total_fired,
            "last_tick_at": self._last_tick_at,
        }

    # ------------------------------------------------------------------ #
    # Register built-in default schedules into DB
    # ------------------------------------------------------------------ #

    async def register_defaults(
        self, schedules: list, caller_service: str = "cron-service"
    ) -> None:
        """
        Register built-in default schedules into the database.
        Skips if an event with the same name + caller already exists.
        """
        for cfg in schedules:
            try:
                existing = await self._db_client.list_events(
                    caller_service=caller_service,
                    event_name=cfg.name,
                )
                if existing.get("total", 0) > 0:
                    logger.info(
                        "Default schedule '%s' already registered, skipping.",
                        cfg.name,
                    )
                    continue

                now = utc_now()
                next_fire = compute_next_run_at(
                    cron_expression=cfg.cron_expression,
                    interval_seconds=cfg.interval_seconds,
                    from_time=now,
                )

                await self._db_client.create_event({
                    "event_name": cfg.name,
                    "event_type": "recurring",
                    "caller_service": caller_service,
                    "topic": cfg.topic,
                    "cron_expression": cfg.cron_expression,
                    "interval_seconds": cfg.interval_seconds,
                    "payload": cfg.payload,
                    "next_fire_at": next_fire.isoformat() if next_fire else None,
                })
                logger.info(
                    "Registered default schedule '%s' → topic=%s, next=%s",
                    cfg.name,
                    cfg.topic,
                    next_fire.isoformat() if next_fire else "N/A",
                )
            except Exception as e:
                logger.warning(
                    "Failed to register default schedule '%s': %s",
                    cfg.name, str(e),
                )
