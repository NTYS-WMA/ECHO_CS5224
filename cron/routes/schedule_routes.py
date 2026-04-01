"""
Legacy schedule routes — kept for backward compatibility.

In v4.0, schedule management is done via /api/v1/events endpoints.
These routes delegate to the new event_routes where possible.
"""

from fastapi import APIRouter

from ..models.responses import SchedulerStatusResponse
from ..services.scheduler import CronScheduler

router = APIRouter(prefix="/api/v1/legacy", tags=["legacy-schedules"])


def get_scheduler() -> CronScheduler:
    from ..app import get_app_scheduler
    return get_app_scheduler()


@router.get(
    "/scheduler/status",
    response_model=SchedulerStatusResponse,
    summary="[Legacy] Get scheduler status",
)
async def get_status():
    scheduler = get_scheduler()
    status = scheduler.get_status()
    from ..config.settings import get_settings
    settings = get_settings()
    return SchedulerStatusResponse(
        **status,
        db_manager_url=settings.DB_MANAGER_URL,
    )
