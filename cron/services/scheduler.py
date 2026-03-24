"""
Polling scheduler engine for the Cron Service v2.0.

Implements an internal polling loop that periodically queries the
Database Service for due tasks (next_run_at <= now, status = scheduled)
and dispatches them through the TaskExecutor.

The scheduler runs as a background asyncio task within the FastAPI
application lifecycle.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.responses import PollCycleResponse, PollExecutionResult
from ..utils.helpers import generate_poll_id, utc_now
from .db_client import DatabaseServiceClient
from .task_executor import TaskExecutor

logger = logging.getLogger(__name__)


class PollingScheduler:
    """
    Background polling engine that discovers and executes due tasks.

    Lifecycle:
        start() → runs poll loop in background → stop()
    """

    def __init__(
        self,
        db_client: DatabaseServiceClient,
        executor: TaskExecutor,
        poll_interval_seconds: int = 30,
        max_tasks_per_poll: int = 100,
    ):
        """
        Initialize the PollingScheduler.

        Args:
            db_client: HTTP client for the Database Service.
            executor: TaskExecutor for dispatching individual tasks.
            poll_interval_seconds: Seconds between poll cycles.
            max_tasks_per_poll: Max tasks to process per cycle.
        """
        self._db = db_client
        self._executor = executor
        self._poll_interval = poll_interval_seconds
        self._max_tasks = max_tasks_per_poll
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_poll_at: Optional[datetime] = None

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._running

    @property
    def poll_interval_seconds(self) -> int:
        """Configured polling interval."""
        return self._poll_interval

    @property
    def last_poll_at(self) -> Optional[datetime]:
        """Timestamp of the last completed poll cycle."""
        return self._last_poll_at

    # ------------------------------------------------------------------ #
    # Start / Stop
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            logger.warning("Scheduler is already running.")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "Polling scheduler started (interval=%ds, max_tasks=%d).",
            self._poll_interval,
            self._max_tasks,
        )

    async def stop(self) -> None:
        """Stop the background polling loop gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Polling scheduler stopped.")

    # ------------------------------------------------------------------ #
    # Poll Loop
    # ------------------------------------------------------------------ #

    async def _poll_loop(self) -> None:
        """
        Main polling loop.

        Runs indefinitely until stop() is called, sleeping between cycles.
        """
        while self._running:
            try:
                await self._execute_poll_cycle(self._max_tasks)
            except Exception as e:
                logger.error("Poll cycle failed unexpectedly: %s", str(e))

            # Sleep until next cycle
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------ #
    # Single Poll Cycle
    # ------------------------------------------------------------------ #

    async def _execute_poll_cycle(
        self, max_tasks: int
    ) -> PollCycleResponse:
        """
        Execute a single poll cycle.

        1. Query Database Service for due tasks.
        2. Execute each task via TaskExecutor.
        3. Return aggregated results.

        Args:
            max_tasks: Maximum number of due tasks to process.

        Returns:
            PollCycleResponse with per-task results.
        """
        poll_id = generate_poll_id()
        start_time = time.monotonic()
        now = utc_now()

        logger.debug("Poll cycle %s started.", poll_id)

        # Query due tasks from Database Service
        due_tasks = await self._db.query_due_tasks(now=now, max_tasks=max_tasks)
        tasks_found = len(due_tasks)

        if tasks_found == 0:
            self._last_poll_at = now
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug("Poll cycle %s: no due tasks.", poll_id)
            return PollCycleResponse(
                poll_id=poll_id,
                tasks_found=0,
                tasks_dispatched=0,
                tasks_failed=0,
                results=[],
                duration_ms=round(duration_ms, 2),
            )

        logger.info("Poll cycle %s: found %d due tasks.", poll_id, tasks_found)

        # Execute each task
        results: List[PollExecutionResult] = []
        dispatched = 0
        failed = 0

        for task in due_tasks:
            try:
                outcome = await self._executor.execute(task)
                success = outcome.get("success", False)
                error = outcome.get("error")

                results.append(PollExecutionResult(
                    task_id=task.task_id,
                    success=success,
                    error=error,
                ))

                if success:
                    dispatched += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(
                    "Unexpected error executing task %s: %s",
                    task.task_id,
                    str(e),
                )
                results.append(PollExecutionResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(e),
                ))
                failed += 1

        self._last_poll_at = now
        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Poll cycle %s completed: %d found, %d dispatched, %d failed (%.1fms).",
            poll_id,
            tasks_found,
            dispatched,
            failed,
            duration_ms,
        )

        return PollCycleResponse(
            poll_id=poll_id,
            tasks_found=tasks_found,
            tasks_dispatched=dispatched,
            tasks_failed=failed,
            results=results,
            duration_ms=round(duration_ms, 2),
        )

    # ------------------------------------------------------------------ #
    # Manual Trigger (for ops / testing)
    # ------------------------------------------------------------------ #

    async def trigger_poll(self, max_tasks: int = 100) -> PollCycleResponse:
        """
        Manually trigger a single poll cycle.

        Used for testing and operational purposes. Does not affect
        the background polling loop schedule.

        Args:
            max_tasks: Maximum number of due tasks to process.

        Returns:
            PollCycleResponse with per-task results.
        """
        logger.info("Manual poll trigger requested (max_tasks=%d).", max_tasks)
        return await self._execute_poll_cycle(max_tasks)

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    async def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status including task counts.

        Returns:
            Dict with running state, interval, last_poll_at, and task counts.
        """
        # Get counts from DB Service
        pending_count = await self._db.count_tasks_by_status("scheduled")
        executing_count = await self._db.count_tasks_by_status("executing")

        return {
            "running": self._running,
            "poll_interval_seconds": self._poll_interval,
            "last_poll_at": self._last_poll_at,
            "tasks_pending": pending_count,
            "tasks_executing": executing_count,
        }
