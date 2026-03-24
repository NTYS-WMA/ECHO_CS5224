"""
Schedule and scheduler control routes for the Cron Service v3.0.
"""

from fastapi import APIRouter, HTTPException

from ..models.requests import ManualTriggerRequest
from ..models.responses import (
    ManualTriggerResponse,
    ScheduleEntryResponse,
    ScheduleListResponse,
    SchedulerStatusResponse,
)
from ..services.scheduler import CronScheduler

router = APIRouter(prefix="/api/v1", tags=["schedules"])


def get_scheduler() -> CronScheduler:
    """Dependency — wired in app.py at startup."""
    from ..app import get_app_scheduler

    return get_app_scheduler()


# ------------------------------------------------------------------ #
# List schedules
# ------------------------------------------------------------------ #


@router.get(
    "/schedules",
    response_model=ScheduleListResponse,
    summary="List all configured schedules",
)
async def list_schedules():
    """Return all configured cron schedules and their state."""
    scheduler = get_scheduler()
    entries = scheduler.get_schedules()
    return ScheduleListResponse(
        schedules=[
            ScheduleEntryResponse(**e.model_dump()) for e in entries
        ],
        total=len(entries),
    )


# ------------------------------------------------------------------ #
# Get single schedule
# ------------------------------------------------------------------ #


@router.get(
    "/schedules/{schedule_name}",
    response_model=ScheduleEntryResponse,
    summary="Get a single schedule by name",
)
async def get_schedule(schedule_name: str):
    """Return a single schedule entry."""
    scheduler = get_scheduler()
    entry = scheduler.get_schedule(schedule_name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_name}' not found.")
    return ScheduleEntryResponse(**entry.model_dump())


# ------------------------------------------------------------------ #
# Scheduler status
# ------------------------------------------------------------------ #


@router.get(
    "/scheduler/status",
    response_model=SchedulerStatusResponse,
    summary="Get scheduler status",
)
async def get_status():
    """Return the current scheduler status."""
    scheduler = get_scheduler()
    return SchedulerStatusResponse(**scheduler.get_status())


# ------------------------------------------------------------------ #
# Manual trigger
# ------------------------------------------------------------------ #


@router.post(
    "/scheduler/trigger/{schedule_name}",
    response_model=ManualTriggerResponse,
    summary="Manually trigger a schedule",
)
async def trigger_schedule(
    schedule_name: str,
    request: ManualTriggerRequest = ManualTriggerRequest(),
):
    """Manually fire a schedule (for ops/testing)."""
    scheduler = get_scheduler()
    result = await scheduler.trigger(
        schedule_name=schedule_name,
        payload_override=request.payload_override,
    )
    if not result.published and result.error:
        raise HTTPException(status_code=404, detail=result.error)
    return result
