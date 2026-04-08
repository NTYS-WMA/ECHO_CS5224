"""
Event registration and management routes for the Cron Service v4.0.

External services use these endpoints to register, query, update,
and cancel scheduled events.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..clients.db_manager_client import DBManagerClient
from ..models.requests import ManualTriggerRequest, RegisterEventRequest, UpdateEventRequest
from ..models.responses import (
    EventListResponse,
    ManualTriggerResponse,
    RegisterEventResponse,
    ScheduledEventResponse,
    SchedulerStatusResponse,
)
from ..services.scheduler import CronScheduler
from ..utils.helpers import compute_next_run_at, utc_now

router = APIRouter(prefix="/api/v1", tags=["events"])


def _get_scheduler() -> CronScheduler:
    from ..app import get_app_scheduler
    return get_app_scheduler()


def _get_db_client() -> DBManagerClient:
    from ..app import get_app_db_client
    return get_app_db_client()


# ------------------------------------------------------------------ #
# Register a new event
# ------------------------------------------------------------------ #


@router.post(
    "/events",
    response_model=RegisterEventResponse,
    status_code=201,
    summary="Register a new scheduled event",
)
async def register_event(request: RegisterEventRequest):
    """
    Register a scheduled event from an external service.

    **One-time events**: set `scheduled_at` to the future UTC time.
    **Recurring events**: set `event_type` to 'recurring' and provide
    `cron_expression` or `interval_seconds`.

    The `payload` field is fully customizable — put whatever context
    your service needs (user_id, conversation_id, template name, etc.).
    """
    db_client = _get_db_client()

    # Compute next_fire_at
    now = utc_now()
    if request.scheduled_at and request.event_type == "one_time":
        next_fire = request.scheduled_at
    else:
        next_fire = compute_next_run_at(
            scheduled_at=request.scheduled_at,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            from_time=now,
        )

    if next_fire is None:
        raise HTTPException(
            400,
            "Cannot compute next fire time. Provide scheduled_at, "
            "cron_expression, or interval_seconds.",
        )

    data = {
        "event_name": request.event_name,
        "event_type": request.event_type,
        "caller_service": request.caller_service,
        "callback_url": request.callback_url,
        "topic": request.topic,
        "cron_expression": request.cron_expression,
        "interval_seconds": request.interval_seconds,
        "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None,
        "payload": request.payload,
        "next_fire_at": next_fire.isoformat() if next_fire else None,
        "max_fires": request.max_fires,
        "correlation_id": request.correlation_id,
        "group_key": request.group_key,
    }

    try:
        result = await db_client.create_event(data)
    except Exception as e:
        raise HTTPException(500, f"Failed to register event: {str(e)}")

    return RegisterEventResponse(
        id=result["id"],
        event_name=result["event_name"],
        event_type=result["event_type"],
        status=result["status"],
        next_fire_at=result.get("next_fire_at"),
    )


# ------------------------------------------------------------------ #
# List events
# ------------------------------------------------------------------ #


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="List scheduled events",
)
async def list_events(
    caller_service: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    group_key: Optional[str] = Query(None),
    event_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List scheduled events with optional filters."""
    db_client = _get_db_client()
    result = await db_client.list_events(
        caller_service=caller_service,
        status=status,
        group_key=group_key,
        event_name=event_name,
        limit=limit,
        offset=offset,
    )
    events = [ScheduledEventResponse(**e) for e in result.get("events", [])]
    return EventListResponse(
        events=events,
        total=result.get("total", 0),
        limit=limit,
        offset=offset,
    )


# ------------------------------------------------------------------ #
# Get single event
# ------------------------------------------------------------------ #


@router.get(
    "/events/{event_id}",
    response_model=ScheduledEventResponse,
    summary="Get a scheduled event by ID",
)
async def get_event(event_id: str):
    db_client = _get_db_client()
    result = await db_client.get_event(event_id)
    if result is None:
        raise HTTPException(404, f"Event '{event_id}' not found.")
    return ScheduledEventResponse(**result)


# ------------------------------------------------------------------ #
# Update event
# ------------------------------------------------------------------ #


@router.put(
    "/events/{event_id}",
    response_model=ScheduledEventResponse,
    summary="Update a scheduled event",
)
async def update_event(event_id: str, request: UpdateEventRequest):
    db_client = _get_db_client()
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    # If schedule changed, recompute next_fire_at
    if any(k in updates for k in ("cron_expression", "interval_seconds", "scheduled_at")):
        now = utc_now()
        next_fire = compute_next_run_at(
            scheduled_at=updates.get("scheduled_at"),
            cron_expression=updates.get("cron_expression"),
            interval_seconds=updates.get("interval_seconds"),
            from_time=now,
        )
        if next_fire:
            updates["next_fire_at"] = next_fire.isoformat()

    # Serialize datetime fields
    for key in ("scheduled_at", "next_fire_at"):
        if key in updates and hasattr(updates[key], "isoformat"):
            updates[key] = updates[key].isoformat()

    result = await db_client.update_event(event_id, updates)
    if result is None:
        raise HTTPException(404, f"Event '{event_id}' not found.")
    return ScheduledEventResponse(**result)


# ------------------------------------------------------------------ #
# Cancel / Pause / Resume
# ------------------------------------------------------------------ #


@router.post(
    "/events/{event_id}/cancel",
    summary="Cancel a scheduled event",
)
async def cancel_event(event_id: str):
    db_client = _get_db_client()
    success = await db_client.update_status(event_id, "cancelled")
    if not success:
        raise HTTPException(404, f"Event '{event_id}' not found.")
    return {"event_id": event_id, "status": "cancelled"}


@router.post(
    "/events/{event_id}/pause",
    summary="Pause a scheduled event",
)
async def pause_event(event_id: str):
    db_client = _get_db_client()
    success = await db_client.update_status(event_id, "paused")
    if not success:
        raise HTTPException(404, f"Event '{event_id}' not found.")
    return {"event_id": event_id, "status": "paused"}


@router.post(
    "/events/{event_id}/resume",
    summary="Resume a paused event",
)
async def resume_event(event_id: str):
    db_client = _get_db_client()
    success = await db_client.update_status(event_id, "active")
    if not success:
        raise HTTPException(404, f"Event '{event_id}' not found.")
    return {"event_id": event_id, "status": "active"}


# ------------------------------------------------------------------ #
# Delete
# ------------------------------------------------------------------ #


@router.delete(
    "/events/{event_id}",
    summary="Delete a scheduled event",
)
async def delete_event(event_id: str):
    db_client = _get_db_client()
    success = await db_client.delete_event(event_id)
    if not success:
        raise HTTPException(404, f"Event '{event_id}' not found.")
    return {"deleted": True, "event_id": event_id}


@router.delete(
    "/events/by-group/{group_key}",
    summary="Delete all events for a group key",
)
async def delete_by_group(group_key: str):
    db_client = _get_db_client()
    count = await db_client.delete_by_group(group_key)
    return {"deleted": count, "group_key": group_key}


# ------------------------------------------------------------------ #
# Manual trigger
# ------------------------------------------------------------------ #


@router.post(
    "/events/{event_id}/trigger",
    response_model=ManualTriggerResponse,
    summary="Manually trigger a scheduled event",
)
async def trigger_event(
    event_id: str,
    request: ManualTriggerRequest = ManualTriggerRequest(),
):
    scheduler = _get_scheduler()
    result = await scheduler.trigger(
        event_id=event_id,
        payload_override=request.payload_override,
    )
    if not result.published and result.error:
        raise HTTPException(404, detail=result.error)
    return result


# ------------------------------------------------------------------ #
# Scheduler status
# ------------------------------------------------------------------ #


@router.get(
    "/scheduler/status",
    response_model=SchedulerStatusResponse,
    summary="Get scheduler status",
)
async def get_status():
    scheduler = _get_scheduler()
    status = scheduler.get_status()
    from ..config.settings import get_settings
    settings = get_settings()
    return SchedulerStatusResponse(
        **status,
        db_manager_url=settings.DB_MANAGER_URL,
    )
