"""
Scheduler engine for the Cron Service v3.0.

A lightweight background loop that:
1. Maintains a table of schedule entries with their next fire times.
2. On each tick, checks which schedules are due (next_fire_at <= now).
3. Publishes the corresponding event to the broker via EventPublisher.
4. Recomputes next_fire_at for the schedule.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config.settings import ScheduleEntryConfig
from ..events.publisher import EventPublisher
from ..models.domain import ScheduleEntry
from ..models.events import CronTriggeredEvent
from ..models.responses import ManualTriggerResponse
from ..utils.helpers import compute_next_run_at, generate_event_id, utc_now

logger = logging.getLogger(__name__)


class CronScheduler:
    """
    Lightweight cron scheduler that publishes events on schedule.
    """

    def __init__(
        self,
        publisher: EventPublisher,
        tick_interval_seconds: int = 30,
    ):
        self._publisher = publisher
        self._tick_interval = tick_interval_seconds
        self._schedules: Dict[str, ScheduleEntry] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_tick_at: Optional[datetime] = None

    # ------------------------------------------------------------------ #
    # Schedule management
    # ------------------------------------------------------------------ #

    def load_schedules(self, configs: List[ScheduleEntryConfig]) -> None:
        """Load schedule entries from configuration and compute initial fire times."""
        now = utc_now()
        for cfg in configs:
            next_fire = compute_next_run_at(
                cron_expression=cfg.cron_expression,
                interval_seconds=cfg.interval_seconds,
                from_time=now,
            )
            entry = ScheduleEntry(
                name=cfg.name,
                cron_expression=cfg.cron_expression,
                interval_seconds=cfg.interval_seconds,
                topic=cfg.topic,
                payload=cfg.payload,
                enabled=cfg.enabled,
                next_fire_at=next_fire,
            )
            self._schedules[cfg.name] = entry
            logger.info(
                "Loaded schedule '%s' → topic=%s, next_fire_at=%s, enabled=%s",
                cfg.name,
                cfg.topic,
                next_fire.isoformat() if next_fire else "N/A",
                cfg.enabled,
            )

    def get_schedules(self) -> List[ScheduleEntry]:
        """Return all schedule entries."""
        return list(self._schedules.values())

    def get_schedule(self, name: str) -> Optional[ScheduleEntry]:
        """Return a single schedule entry by name."""
        return self._schedules.get(name)

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
        """Start the background tick loop."""
        if self._running:
            logger.warning("Scheduler is already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info(
            "Cron scheduler started (tick_interval=%ds, schedules=%d).",
            self._tick_interval,
            len(self._schedules),
        )

    async def stop(self) -> None:
        """Stop the background tick loop."""
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
        """Main loop: check due schedules on each tick."""
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error("Tick failed: %s", str(e))
            try:
                await asyncio.sleep(self._tick_interval)
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        """Single tick: find due schedules and fire them."""
        now = utc_now()
        self._last_tick_at = now
        fired = 0

        for entry in self._schedules.values():
            if not entry.enabled:
                continue
            if entry.next_fire_at is None:
                continue
            if entry.next_fire_at > now:
                continue

            # Schedule is due — fire it
            success = await self._fire_schedule(entry, now)
            if success:
                fired += 1

            # Recompute next fire time regardless of success
            entry.next_fire_at = compute_next_run_at(
                cron_expression=entry.cron_expression,
                interval_seconds=entry.interval_seconds,
                from_time=now,
            )
            entry.last_fired_at = now

        if fired > 0:
            logger.info("Tick completed: %d schedule(s) fired.", fired)

    async def _fire_schedule(
        self, entry: ScheduleEntry, now: datetime
    ) -> bool:
        """Publish the event for a due schedule entry."""
        event = CronTriggeredEvent(
            event_id=generate_event_id(),
            event_type=entry.topic,
            schedule_name=entry.name,
            payload=entry.payload,
        )
        success = await self._publisher.publish(
            topic=entry.topic,
            payload=event.model_dump(mode="json"),
        )
        if success:
            logger.info(
                "Schedule '%s' fired → topic=%s (event_id=%s).",
                entry.name,
                entry.topic,
                event.event_id,
            )
        else:
            logger.error(
                "Schedule '%s' failed to publish to topic=%s.",
                entry.name,
                entry.topic,
            )
        return success

    # ------------------------------------------------------------------ #
    # Manual trigger
    # ------------------------------------------------------------------ #

    async def trigger(
        self,
        schedule_name: str,
        payload_override: Optional[Dict[str, Any]] = None,
    ) -> ManualTriggerResponse:
        """Manually trigger a schedule (for ops/testing)."""
        entry = self._schedules.get(schedule_name)
        if entry is None:
            return ManualTriggerResponse(
                schedule_name=schedule_name,
                topic="",
                published=False,
                error=f"Schedule '{schedule_name}' not found.",
            )

        event = CronTriggeredEvent(
            event_id=generate_event_id(),
            event_type=entry.topic,
            schedule_name=entry.name,
            payload=payload_override if payload_override is not None else entry.payload,
        )
        success = await self._publisher.publish(
            topic=entry.topic,
            payload=event.model_dump(mode="json"),
        )
        return ManualTriggerResponse(
            schedule_name=schedule_name,
            topic=entry.topic,
            published=success,
            error=None if success else "Failed to publish event.",
        )

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def get_status(self) -> Dict[str, Any]:
        """Return scheduler status."""
        total = len(self._schedules)
        active = sum(1 for s in self._schedules.values() if s.enabled)
        return {
            "running": self._running,
            "tick_interval_seconds": self._tick_interval,
            "total_schedules": total,
            "active_schedules": active,
            "last_tick_at": self._last_tick_at,
        }
