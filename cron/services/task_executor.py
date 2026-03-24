"""
Task executor for the Cron Service v2.0.

Handles the execution of a single scheduled task:
1. Mark task as executing (via DB Service).
2. Dispatch message to Message Dispatch Hub.
3. On success: mark completed (one_time) or reschedule (recurring).
4. On failure: increment retry count, reschedule or mark failed.
5. Publish lifecycle events for telemetry.
"""

import logging
from datetime import timedelta
from typing import Any, Dict

from ..models.domain import ScheduledTask, TaskStatus, TaskType
from ..models.events import TaskDispatchedEvent, TaskFailedEvent
from ..utils.helpers import compute_next_run_at, generate_event_id, utc_now
from .db_client import DatabaseServiceClient
from .dispatcher import MessageDispatchClient

logger = logging.getLogger(__name__)

# Exponential backoff base for retries (seconds)
RETRY_BACKOFF_BASE = 60


class TaskExecutor:
    """
    Executes a single scheduled task through the dispatch pipeline.
    """

    def __init__(
        self,
        db_client: DatabaseServiceClient,
        dispatch_client: MessageDispatchClient,
        event_publisher: Any = None,  # Optional event publisher for telemetry
    ):
        """
        Initialize the TaskExecutor.

        Args:
            db_client: HTTP client for the Database Service.
            dispatch_client: HTTP client for the Message Dispatch Hub.
            event_publisher: Optional event publisher for lifecycle events.
        """
        self._db = db_client
        self._dispatch = dispatch_client
        self._events = event_publisher

    async def execute(self, task: ScheduledTask) -> Dict[str, Any]:
        """
        Execute a single scheduled task.

        Args:
            task: The ScheduledTask to execute.

        Returns:
            Dict with:
                - task_id (str)
                - success (bool)
                - error (str | None)
        """
        task_id = task.task_id

        # Step 1: Mark as executing
        await self._db.update_task(task_id, {
            "status": TaskStatus.EXECUTING.value,
            "updated_at": utc_now().isoformat(),
        })

        # Step 2: Check expiration
        if task.expires_at and utc_now() > task.expires_at:
            logger.info("Task %s has expired. Cancelling.", task_id)
            await self._db.update_task(task_id, {
                "status": TaskStatus.CANCELLED.value,
                "updated_at": utc_now().isoformat(),
            })
            return {"task_id": task_id, "success": False, "error": "task_expired"}

        # Step 3: Dispatch to Message Dispatch Hub
        result = await self._dispatch.dispatch_message(task)

        if result["success"]:
            return await self._handle_success(task)
        else:
            return await self._handle_failure(task, result["error"])

    async def _handle_success(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle successful dispatch."""
        now = utc_now()
        task_id = task.task_id

        if task.task_type == TaskType.ONE_TIME:
            # One-time task: mark as completed
            await self._db.update_task(task_id, {
                "status": TaskStatus.COMPLETED.value,
                "last_run_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            logger.info("Task %s (one_time) completed successfully.", task_id)
        else:
            # Recurring task: reschedule for next run
            next_run = compute_next_run_at(
                cron_expression=task.schedule_config.cron_expression,
                interval_seconds=task.schedule_config.interval_seconds,
                from_time=now,
            )
            updates = {
                "status": TaskStatus.SCHEDULED.value,
                "last_run_at": now.isoformat(),
                "retry_count": 0,  # Reset retry count on success
                "updated_at": now.isoformat(),
            }
            if next_run:
                updates["next_run_at"] = next_run.isoformat()

            await self._db.update_task(task_id, updates)
            logger.info(
                "Task %s (recurring) dispatched, next_run_at=%s",
                task_id,
                next_run.isoformat() if next_run else "unknown",
            )

        # Publish success event (best-effort)
        await self._publish_dispatched_event(task)

        return {"task_id": task_id, "success": True, "error": None}

    async def _handle_failure(
        self, task: ScheduledTask, error: str
    ) -> Dict[str, Any]:
        """Handle dispatch failure with retry logic."""
        now = utc_now()
        task_id = task.task_id
        new_retry_count = task.retry_count + 1

        if new_retry_count >= task.max_retries:
            # Exhausted retries: mark as failed permanently
            await self._db.update_task(task_id, {
                "status": TaskStatus.FAILED.value,
                "retry_count": new_retry_count,
                "last_run_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            logger.error(
                "Task %s failed permanently after %d retries: %s",
                task_id,
                new_retry_count,
                error,
            )
            # Publish failure event (best-effort)
            await self._publish_failed_event(task, error, new_retry_count)
        else:
            # Schedule retry with exponential backoff
            backoff_seconds = RETRY_BACKOFF_BASE * (2 ** task.retry_count)
            retry_at = now + timedelta(seconds=backoff_seconds)

            await self._db.update_task(task_id, {
                "status": TaskStatus.SCHEDULED.value,
                "retry_count": new_retry_count,
                "next_run_at": retry_at.isoformat(),
                "last_run_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            logger.warning(
                "Task %s failed (attempt %d/%d), retrying at %s: %s",
                task_id,
                new_retry_count,
                task.max_retries,
                retry_at.isoformat(),
                error,
            )

        return {"task_id": task_id, "success": False, "error": error}

    # ------------------------------------------------------------------ #
    # Event Publishing (best-effort)
    # ------------------------------------------------------------------ #

    async def _publish_dispatched_event(self, task: ScheduledTask) -> None:
        """Publish a task.dispatched telemetry event."""
        if self._events is None:
            return
        try:
            event = TaskDispatchedEvent(
                event_id=generate_event_id(),
                task_id=task.task_id,
                user_id=task.user_id,
                channel=task.channel,
                conversation_id=task.conversation_id,
                owner_service=task.owner_service,
            )
            await self._events.publish(
                "proactive.task.dispatched",
                event.model_dump(mode="json"),
            )
        except Exception as e:
            logger.error("Failed to publish dispatched event: %s", str(e))

    async def _publish_failed_event(
        self, task: ScheduledTask, error: str, retry_count: int
    ) -> None:
        """Publish a task.failed telemetry event."""
        if self._events is None:
            return
        try:
            event = TaskFailedEvent(
                event_id=generate_event_id(),
                task_id=task.task_id,
                user_id=task.user_id,
                owner_service=task.owner_service,
                error=error,
                retry_count=retry_count,
            )
            await self._events.publish(
                "proactive.task.failed",
                event.model_dump(mode="json"),
            )
        except Exception as e:
            logger.error("Failed to publish failed event: %s", str(e))
