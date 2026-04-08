"""API routes for scheduled events CRUD (consumed by Cron Service)."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.postgres import get_postgres_session_maker
from app.repositories.scheduled_events_repository import ScheduledEventsRepository

router = APIRouter(prefix="/scheduled-events", tags=["scheduled-events"])
repo = ScheduledEventsRepository()


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            output[key] = str(value)
        elif isinstance(value, datetime):
            output[key] = value.isoformat()
        else:
            output[key] = value
    return output


# ------------------------------------------------------------------ #
# Request / Response models
# ------------------------------------------------------------------ #


class CreateEventRequest(BaseModel):
    event_name: str = Field(..., description="Human-readable event name")
    event_type: str = Field("one_time", description="one_time or recurring")
    caller_service: str = Field(..., description="Service that registers this event")
    callback_url: Optional[str] = Field(None, description="HTTP callback URL")
    topic: Optional[str] = Field(None, description="Event broker topic")
    cron_expression: Optional[str] = Field(None, description="Cron expression for recurring")
    interval_seconds: Optional[int] = Field(None, description="Interval in seconds for recurring")
    scheduled_at: Optional[datetime] = Field(None, description="Exact fire time for one-time events")
    payload: dict[str, Any] = Field(default_factory=dict, description="Custom payload (JSONB)")
    next_fire_at: Optional[datetime] = Field(None, description="Pre-computed next fire time")
    max_fires: Optional[int] = Field(None, description="Max fire count (NULL=unlimited)")
    correlation_id: Optional[str] = Field(None, description="Tracing correlation ID")
    group_key: Optional[str] = Field(None, description="Caller-defined grouping key")


class UpdateEventRequest(BaseModel):
    event_name: Optional[str] = None
    status: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    payload: Optional[dict[str, Any]] = None
    next_fire_at: Optional[datetime] = None
    max_fires: Optional[int] = None
    correlation_id: Optional[str] = None
    group_key: Optional[str] = None


class MarkFiredRequest(BaseModel):
    fired_at: datetime
    next_fire_at: Optional[datetime] = None
    new_status: str = "active"


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #


@router.post("", status_code=201)
async def create_event(req: CreateEventRequest):
    """Register a new scheduled event."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        row = await repo.create_event(
            session,
            event_name=req.event_name,
            event_type=req.event_type,
            caller_service=req.caller_service,
            callback_url=req.callback_url,
            topic=req.topic,
            cron_expression=req.cron_expression,
            interval_seconds=req.interval_seconds,
            scheduled_at=req.scheduled_at,
            payload=req.payload,
            next_fire_at=req.next_fire_at,
            max_fires=req.max_fires,
            correlation_id=req.correlation_id,
            group_key=req.group_key,
        )
        await session.commit()
        return _serialize_row(row)


@router.get("/{event_id}")
async def get_event(event_id: UUID):
    """Get a scheduled event by ID."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        row = await repo.get_event_by_id(session, event_id)
        if not row:
            raise HTTPException(404, f"Event {event_id} not found")
        return _serialize_row(row)


@router.get("")
async def list_events(
    caller_service: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    group_key: Optional[str] = Query(None),
    event_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List scheduled events with optional filters."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        rows = await repo.list_events(
            session,
            caller_service=caller_service,
            status=status,
            group_key=group_key,
            event_name=event_name,
            limit=limit,
            offset=offset,
        )
        total = await repo.count_events(
            session,
            caller_service=caller_service,
            status=status,
            group_key=group_key,
        )
        return {
            "events": [_serialize_row(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/due/poll")
async def poll_due_events(
    now: datetime = Query(..., description="Current UTC time"),
    limit: int = Query(50, ge=1, le=200),
):
    """Poll for events that are due to fire."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        rows = await repo.get_due_events(session, now=now, limit=limit)
        return {"events": [_serialize_row(r) for r in rows], "count": len(rows)}


@router.put("/{event_id}")
async def update_event(event_id: UUID, req: UpdateEventRequest):
    """Update a scheduled event."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    sm = get_postgres_session_maker()
    async with sm() as session:
        row = await repo.update_event(session, event_id, updates)
        if not row:
            raise HTTPException(404, f"Event {event_id} not found")
        await session.commit()
        return _serialize_row(row)


@router.post("/{event_id}/fired")
async def mark_event_fired(event_id: UUID, req: MarkFiredRequest):
    """Mark an event as fired (called by cron scheduler after dispatching)."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        count = await repo.mark_fired(
            session,
            event_id=event_id,
            fired_at=req.fired_at,
            next_fire_at=req.next_fire_at,
            new_status=req.new_status,
        )
        if count == 0:
            raise HTTPException(404, f"Event {event_id} not found")
        await session.commit()
        return {"updated": count}


@router.patch("/{event_id}/status")
async def update_event_status(event_id: UUID, status: str = Query(...)):
    """Update only the status of a scheduled event."""
    valid = {"active", "paused", "completed", "cancelled", "failed"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")

    sm = get_postgres_session_maker()
    async with sm() as session:
        count = await repo.update_status(session, event_id, status)
        if count == 0:
            raise HTTPException(404, f"Event {event_id} not found")
        await session.commit()
        return {"updated": count}


@router.delete("/{event_id}")
async def delete_event(event_id: UUID):
    """Delete a scheduled event."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        count = await repo.delete_event(session, event_id)
        if count == 0:
            raise HTTPException(404, f"Event {event_id} not found")
        await session.commit()
        return {"deleted": count}


@router.delete("/by-group/{group_key}")
async def delete_by_group(group_key: str):
    """Delete all scheduled events for a group key."""
    sm = get_postgres_session_maker()
    async with sm() as session:
        count = await repo.delete_by_group_key(session, group_key)
        await session.commit()
        return {"deleted": count}
