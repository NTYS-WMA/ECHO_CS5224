"""
Task management service for the Cron Service v2.0.

Provides business logic for task registration, retrieval, update,
deletion, pause, and resume. All persistence is delegated to the
Database Service via DatabaseServiceClient.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.domain import (
    ScheduleConfig,
    ScheduledTask,
    TaskPayload,
    TaskStatus,
    TaskType,
)
from ..models.requests import RegisterTaskRequest, UpdateTaskRequest
from ..utils.helpers import compute_next_run_at, generate_task_id, utc_now
from .db_client import DatabaseServiceClient

logger = logging.getLogger(__name__)


class TaskService:
    """
    Business logic layer for scheduled task management.

    Validates inputs, computes next_run_at, and delegates persistence
    to the Database Service.
    """

    def __init__(self, db_client: DatabaseServiceClient):
        """
        Initialize the TaskService.

        Args:
            db_client: HTTP client for the Database Service.
        """
        self._db = db_client

    # ------------------------------------------------------------------ #
    # REGISTER
    # ------------------------------------------------------------------ #

    async def register_task(self, request: RegisterTaskRequest) -> Optional[ScheduledTask]:
        """
        Register a new scheduled task.

        Computes next_run_at from the schedule configuration and persists
        the task via the Database Service.

        Args:
            request: Task registration request from a service registrant.

        Returns:
            The created ScheduledTask, or None on failure.
        """
        now = utc_now()
        task_id = generate_task_id()

        # Compute next execution time
        next_run = compute_next_run_at(
            scheduled_at=request.schedule_config.scheduled_at,
            cron_expression=request.schedule_config.cron_expression,
            interval_seconds=request.schedule_config.interval_seconds,
            from_time=now,
        )

        if next_run is None:
            logger.error(
                "Cannot compute next_run_at for task from %s: invalid schedule config.",
                request.owner_service,
            )
            return None

        # Determine initial status
        initial_status = TaskStatus.SCHEDULED

        task = ScheduledTask(
            task_id=task_id,
            owner_service=request.owner_service,
            task_type=request.task_type,
            status=initial_status,
            channel=request.channel,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            payload=request.payload,
            schedule_config=request.schedule_config,
            next_run_at=next_run,
            last_run_at=None,
            retry_count=0,
            max_retries=request.max_retries,
            metadata=request.metadata,
            created_at=now,
            updated_at=now,
            expires_at=request.expires_at,
        )

        created = await self._db.create_task(task)
        if created:
            logger.info(
                "Task %s registered by %s for user %s, next_run_at=%s",
                task_id,
                request.owner_service,
                request.user_id,
                next_run.isoformat(),
            )
        return created

    # ------------------------------------------------------------------ #
    # GET
    # ------------------------------------------------------------------ #

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """
        Retrieve a single task by ID.

        Args:
            task_id: The task identifier.

        Returns:
            ScheduledTask or None if not found.
        """
        return await self._db.get_task(task_id)

    # ------------------------------------------------------------------ #
    # LIST
    # ------------------------------------------------------------------ #

    async def list_tasks(
        self,
        owner_service: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ScheduledTask], int]:
        """
        List tasks with optional filters and pagination.

        Args:
            owner_service: Filter by registrant service.
            status: Filter by task status.
            user_id: Filter by target user.
            channel: Filter by target channel.
            task_type: Filter by task type.
            limit: Page size.
            offset: Pagination offset.

        Returns:
            Tuple of (list of tasks, total count).
        """
        return await self._db.list_tasks(
            owner_service=owner_service,
            status=status,
            user_id=user_id,
            channel=channel,
            task_type=task_type,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #

    async def update_task(
        self, task_id: str, request: UpdateTaskRequest
    ) -> Optional[ScheduledTask]:
        """
        Update an existing task.

        Only provided fields are updated. If schedule_config changes,
        next_run_at is recomputed.

        Args:
            task_id: The task identifier.
            request: Update request with fields to change.

        Returns:
            Updated ScheduledTask or None if not found / on failure.
        """
        existing = await self._db.get_task(task_id)
        if existing is None:
            return None

        updates: Dict[str, Any] = {"updated_at": utc_now().isoformat()}

        if request.payload is not None:
            updates["payload"] = request.payload.model_dump(mode="json")

        if request.schedule_config is not None:
            updates["schedule_config"] = request.schedule_config.model_dump(mode="json")
            # Recompute next_run_at
            new_next_run = compute_next_run_at(
                scheduled_at=request.schedule_config.scheduled_at,
                cron_expression=request.schedule_config.cron_expression,
                interval_seconds=request.schedule_config.interval_seconds,
                from_time=utc_now(),
            )
            if new_next_run:
                updates["next_run_at"] = new_next_run.isoformat()

        if request.max_retries is not None:
            updates["max_retries"] = request.max_retries

        if request.metadata is not None:
            updates["metadata"] = request.metadata

        if request.expires_at is not None:
            updates["expires_at"] = request.expires_at.isoformat()

        updated = await self._db.update_task(task_id, updates)
        if updated:
            logger.info("Task %s updated.", task_id)
        return updated

    # ------------------------------------------------------------------ #
    # DELETE / CANCEL
    # ------------------------------------------------------------------ #

    async def delete_task(self, task_id: str) -> bool:
        """
        Cancel and delete a task.

        Args:
            task_id: The task identifier.

        Returns:
            True if deleted successfully, False if not found.
        """
        # First mark as cancelled, then delete
        await self._db.update_task(
            task_id,
            {"status": TaskStatus.CANCELLED.value, "updated_at": utc_now().isoformat()},
        )
        success = await self._db.delete_task(task_id)
        if success:
            logger.info("Task %s cancelled and deleted.", task_id)
        return success

    # ------------------------------------------------------------------ #
    # PAUSE / RESUME
    # ------------------------------------------------------------------ #

    async def pause_task(self, task_id: str) -> Optional[ScheduledTask]:
        """
        Pause a scheduled task.

        Only tasks in 'scheduled' status can be paused.

        Args:
            task_id: The task identifier.

        Returns:
            Updated ScheduledTask or None if not found / invalid state.
        """
        existing = await self._db.get_task(task_id)
        if existing is None:
            return None
        if existing.status != TaskStatus.SCHEDULED:
            logger.warning(
                "Cannot pause task %s in status %s.", task_id, existing.status
            )
            return None

        return await self._db.update_task(
            task_id,
            {"status": TaskStatus.PAUSED.value, "updated_at": utc_now().isoformat()},
        )

    async def resume_task(self, task_id: str) -> Optional[ScheduledTask]:
        """
        Resume a paused task.

        Only tasks in 'paused' status can be resumed. The next_run_at is
        recomputed from the current time.

        Args:
            task_id: The task identifier.

        Returns:
            Updated ScheduledTask or None if not found / invalid state.
        """
        existing = await self._db.get_task(task_id)
        if existing is None:
            return None
        if existing.status != TaskStatus.PAUSED:
            logger.warning(
                "Cannot resume task %s in status %s.", task_id, existing.status
            )
            return None

        now = utc_now()
        new_next_run = compute_next_run_at(
            scheduled_at=existing.schedule_config.scheduled_at,
            cron_expression=existing.schedule_config.cron_expression,
            interval_seconds=existing.schedule_config.interval_seconds,
            from_time=now,
        )

        updates: Dict[str, Any] = {
            "status": TaskStatus.SCHEDULED.value,
            "updated_at": now.isoformat(),
        }
        if new_next_run:
            updates["next_run_at"] = new_next_run.isoformat()

        return await self._db.update_task(task_id, updates)
