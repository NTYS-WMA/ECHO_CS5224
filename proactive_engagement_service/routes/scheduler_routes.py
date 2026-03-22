"""
Scheduler control API routes for the Proactive Engagement Service v2.0.

Provides endpoints for monitoring and manually triggering the
polling scheduler engine.
"""

from fastapi import APIRouter, Depends

from ..models.requests import ManualPollTriggerRequest
from ..models.responses import PollCycleResponse, SchedulerStatusResponse
from ..services.scheduler import PollingScheduler

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


def get_scheduler() -> PollingScheduler:
    """
    Dependency injection for PollingScheduler.

    Wired in app.py at startup.
    """
    from ..app import get_app_scheduler

    return get_app_scheduler()


# ------------------------------------------------------------------ #
# STATUS
# ------------------------------------------------------------------ #


@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="Get scheduler status",
    description=(
        "Returns the current state of the polling engine, including "
        "whether it is running, the configured interval, and task counts."
    ),
)
async def get_status(
    scheduler: PollingScheduler = Depends(get_scheduler),
):
    """Get the current scheduler status."""
    status = await scheduler.get_status()
    return SchedulerStatusResponse(**status)


# ------------------------------------------------------------------ #
# MANUAL TRIGGER
# ------------------------------------------------------------------ #


@router.post(
    "/trigger",
    response_model=PollCycleResponse,
    summary="Manually trigger a poll cycle",
    description=(
        "Trigger a single poll cycle for testing or operational purposes. "
        "Does not affect the background polling loop schedule."
    ),
)
async def trigger_poll(
    request: ManualPollTriggerRequest = ManualPollTriggerRequest(),
    scheduler: PollingScheduler = Depends(get_scheduler),
):
    """Manually trigger a single poll cycle."""
    return await scheduler.trigger_poll(max_tasks=request.max_tasks)
