"""
Task management API routes for the Cron Service v2.0.

Provides CRUD endpoints for service registrants to manage scheduled
proactive message tasks.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models.requests import RegisterTaskRequest, UpdateTaskRequest
from ..models.responses import TaskDeletedResponse, TaskListResponse, TaskResponse
from ..services.task_service import TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def get_task_service() -> TaskService:
    """
    Dependency injection for TaskService.

    Wired in app.py at startup.
    """
    from ..app import get_app_task_service

    return get_app_task_service()


# ------------------------------------------------------------------ #
# REGISTER
# ------------------------------------------------------------------ #


@router.post(
    "",
    response_model=TaskResponse,
    status_code=201,
    summary="Register a new scheduled task",
    description=(
        "Service registrants call this endpoint to schedule a proactive "
        "message task. The service computes next_run_at and persists the "
        "task via the Database Service."
    ),
)
async def register_task(
    request: RegisterTaskRequest,
    service: TaskService = Depends(get_task_service),
):
    """Register a new scheduled task."""
    task = await service.register_task(request)
    if task is None:
        raise HTTPException(
            status_code=400,
            detail="Failed to register task. Check schedule configuration.",
        )
    return TaskResponse.from_domain(task)


# ------------------------------------------------------------------ #
# LIST
# ------------------------------------------------------------------ #


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List scheduled tasks",
    description="List tasks with optional filters and pagination.",
)
async def list_tasks(
    owner_service: Optional[str] = Query(None, description="Filter by registrant service."),
    status: Optional[str] = Query(None, description="Filter by task status."),
    user_id: Optional[str] = Query(None, description="Filter by target user ID."),
    channel: Optional[str] = Query(None, description="Filter by target channel."),
    task_type: Optional[str] = Query(None, description="Filter by task type."),
    limit: int = Query(50, ge=1, le=500, description="Page size."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
    service: TaskService = Depends(get_task_service),
):
    """List tasks with optional filters."""
    tasks, total = await service.list_tasks(
        owner_service=owner_service,
        status=status,
        user_id=user_id,
        channel=channel,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(
        tasks=[TaskResponse.from_domain(t) for t in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


# ------------------------------------------------------------------ #
# GET
# ------------------------------------------------------------------ #


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
    description="Retrieve a single scheduled task by its ID.",
)
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    """Get a single task by ID."""
    task = await service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return TaskResponse.from_domain(task)


# ------------------------------------------------------------------ #
# UPDATE
# ------------------------------------------------------------------ #


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a scheduled task",
    description="Update fields of an existing task. Only provided fields are changed.",
)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    service: TaskService = Depends(get_task_service),
):
    """Update an existing task."""
    task = await service.update_task(task_id, request)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return TaskResponse.from_domain(task)


# ------------------------------------------------------------------ #
# DELETE
# ------------------------------------------------------------------ #


@router.delete(
    "/{task_id}",
    response_model=TaskDeletedResponse,
    summary="Cancel and delete a task",
    description="Cancel a scheduled task and remove it from the system.",
)
async def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    """Cancel and delete a task."""
    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return TaskDeletedResponse(task_id=task_id)


# ------------------------------------------------------------------ #
# PAUSE / RESUME
# ------------------------------------------------------------------ #


@router.post(
    "/{task_id}/pause",
    response_model=TaskResponse,
    summary="Pause a scheduled task",
    description="Pause a task in 'scheduled' status. It will not fire until resumed.",
)
async def pause_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    """Pause a scheduled task."""
    task = await service.pause_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} not found or cannot be paused in current state.",
        )
    return TaskResponse.from_domain(task)


@router.post(
    "/{task_id}/resume",
    response_model=TaskResponse,
    summary="Resume a paused task",
    description="Resume a paused task. next_run_at is recomputed from the current time.",
)
async def resume_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    """Resume a paused task."""
    task = await service.resume_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} not found or cannot be resumed in current state.",
        )
    return TaskResponse.from_domain(task)
