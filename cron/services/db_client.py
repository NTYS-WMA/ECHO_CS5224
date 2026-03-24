"""
HTTP client for the Database Service module.

All task persistence operations are delegated to the Database Service
via its REST API. The Cron Service does NOT directly
access any database.

Interface called:
    - POST   /api/v1/scheduled_tasks              — Create a task record
    - GET    /api/v1/scheduled_tasks               — List / query tasks
    - GET    /api/v1/scheduled_tasks/{task_id}     — Get a single task
    - PUT    /api/v1/scheduled_tasks/{task_id}     — Update a task record
    - DELETE /api/v1/scheduled_tasks/{task_id}     — Delete a task record
    - POST   /api/v1/scheduled_tasks/query_due     — Query tasks due for execution

TO BE UPDATED: All endpoints are assumed. The Database Service module
has not yet published its official API. The contracts below are based
on the data model defined in models/domain.py and will be updated once
the Database Service team confirms the interface.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..models.domain import ScheduledTask, TaskStatus

logger = logging.getLogger(__name__)


class DatabaseServiceClient:
    """
    HTTP client for the Database Service — scheduled_tasks collection.

    All methods return parsed domain objects or None on failure.
    """

    def __init__(self, base_url: str, timeout_seconds: int = 10):
        """
        Initialize the client.

        Args:
            base_url: Base URL of the Database Service.
            timeout_seconds: HTTP request timeout.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._endpoint = f"{self._base_url}/api/v1/scheduled_tasks"

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #

    async def create_task(self, task: ScheduledTask) -> Optional[ScheduledTask]:
        """
        Persist a new scheduled task.

        Calls: POST /api/v1/scheduled_tasks

        Args:
            task: The ScheduledTask domain object to persist.

        Returns:
            The persisted ScheduledTask (with any server-side defaults applied),
            or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._endpoint,
                    json=task.model_dump(mode="json"),
                )
                response.raise_for_status()
                return ScheduledTask(**response.json())
        except Exception as e:
            logger.error("Failed to create task via DB Service: %s", str(e))
            return None

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """
        Retrieve a single task by ID.

        Calls: GET /api/v1/scheduled_tasks/{task_id}

        Args:
            task_id: The task identifier.

        Returns:
            ScheduledTask or None if not found / on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._endpoint}/{task_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return ScheduledTask(**response.json())
        except Exception as e:
            logger.error("Failed to get task %s via DB Service: %s", task_id, str(e))
            return None

    async def list_tasks(
        self,
        owner_service: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ScheduledTask], int]:
        """
        List tasks with optional filters and pagination.

        Calls: GET /api/v1/scheduled_tasks?owner_service=...&status=...

        Args:
            owner_service: Filter by registrant service.
            status: Filter by task status.
            user_id: Filter by target user.
            channel: Filter by target channel.
            task_type: Filter by task type.
            limit: Page size.
            offset: Pagination offset.

        Returns:
            Tuple of (list of ScheduledTask, total count).
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if owner_service:
            params["owner_service"] = owner_service
        if status:
            params["status"] = status
        if user_id:
            params["user_id"] = user_id
        if channel:
            params["channel"] = channel
        if task_type:
            params["task_type"] = task_type

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self._endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                tasks = [ScheduledTask(**t) for t in data.get("tasks", [])]
                total = data.get("total", len(tasks))
                return tasks, total
        except Exception as e:
            logger.error("Failed to list tasks via DB Service: %s", str(e))
            return [], 0

    async def query_due_tasks(
        self,
        now: datetime,
        max_tasks: int = 100,
    ) -> List[ScheduledTask]:
        """
        Query tasks that are due for execution (next_run_at <= now, status = scheduled).

        Calls: POST /api/v1/scheduled_tasks/query_due

        TO BE UPDATED: This is a specialized query endpoint assumed for the
        polling engine. The Database Service may implement this differently
        (e.g., as a query parameter on the list endpoint).

        Args:
            now: Current UTC datetime.
            max_tasks: Maximum number of due tasks to return.

        Returns:
            List of due ScheduledTask objects.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._endpoint}/query_due",
                    json={
                        "now": now.isoformat(),
                        "max_tasks": max_tasks,
                        "status": TaskStatus.SCHEDULED.value,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return [ScheduledTask(**t) for t in data.get("tasks", [])]
        except Exception as e:
            logger.error("Failed to query due tasks via DB Service: %s", str(e))
            return []

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #

    async def update_task(
        self,
        task_id: str,
        updates: Dict[str, Any],
    ) -> Optional[ScheduledTask]:
        """
        Update fields of an existing task.

        Calls: PUT /api/v1/scheduled_tasks/{task_id}

        Args:
            task_id: The task identifier.
            updates: Dictionary of fields to update (JSON-serializable).

        Returns:
            Updated ScheduledTask or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.put(
                    f"{self._endpoint}/{task_id}",
                    json=updates,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return ScheduledTask(**response.json())
        except Exception as e:
            logger.error(
                "Failed to update task %s via DB Service: %s", task_id, str(e)
            )
            return None

    # ------------------------------------------------------------------ #
    # DELETE
    # ------------------------------------------------------------------ #

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete (cancel) a task.

        Calls: DELETE /api/v1/scheduled_tasks/{task_id}

        Args:
            task_id: The task identifier.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.delete(f"{self._endpoint}/{task_id}")
                if response.status_code == 404:
                    return False
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(
                "Failed to delete task %s via DB Service: %s", task_id, str(e)
            )
            return False

    # ------------------------------------------------------------------ #
    # Aggregation helpers
    # ------------------------------------------------------------------ #

    async def count_tasks_by_status(self, status: str) -> int:
        """
        Count tasks with a given status.

        TO BE UPDATED: This may be a dedicated endpoint or a query parameter
        on the list endpoint with count-only mode.

        Args:
            status: Task status to count.

        Returns:
            Count of matching tasks.
        """
        # Fallback: use list with limit=0 to get total count
        _, total = await self.list_tasks(status=status, limit=1, offset=0)
        return total
