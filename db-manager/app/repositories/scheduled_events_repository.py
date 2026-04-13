"""Repository for scheduled_events table operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ScheduledEventsRepository:
    """PostgreSQL repository for scheduled events CRUD."""

    async def create_event(
        self,
        session: AsyncSession,
        event_name: str,
        event_type: str,
        caller_service: str,
        callback_url: str | None,
        topic: str | None,
        cron_expression: str | None,
        interval_seconds: int | None,
        scheduled_at: datetime | None,
        payload: dict[str, Any],
        next_fire_at: datetime | None,
        max_fires: int | None,
        correlation_id: str | None,
        group_key: str | None,
    ) -> dict[str, Any]:
        query = text(
            """
            INSERT INTO scheduled_events (
                event_name, event_type, caller_service,
                callback_url, topic,
                cron_expression, interval_seconds, scheduled_at,
                payload, next_fire_at, max_fires,
                correlation_id, group_key, status
                )
                VALUES (
                    :event_name, :event_type, :caller_service,
                    :callback_url, :topic,
                    :cron_expression, :interval_seconds, :scheduled_at,
                    CAST(:payload AS jsonb), :next_fire_at, :max_fires,
                    :correlation_id, :group_key, 'active'
                )
            RETURNING *
            """
        )
        import json

        result = await session.execute(
            query,
            {
                "event_name": event_name,
                "event_type": event_type,
                "caller_service": caller_service,
                "callback_url": callback_url,
                "topic": topic,
                "cron_expression": cron_expression,
                "interval_seconds": interval_seconds,
                "scheduled_at": scheduled_at,
                "payload": json.dumps(payload),
                "next_fire_at": next_fire_at,
                "max_fires": max_fires,
                "correlation_id": correlation_id,
                "group_key": group_key,
            },
        )
        row = result.mappings().first()
        return dict(row) if row else {}

    async def get_event_by_id(
        self, session: AsyncSession, event_id: UUID
    ) -> dict[str, Any] | None:
        query = text("SELECT * FROM scheduled_events WHERE id = :event_id")
        result = await session.execute(query, {"event_id": str(event_id)})
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_events(
        self,
        session: AsyncSession,
        caller_service: str | None = None,
        status: str | None = None,
        group_key: str | None = None,
        event_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if caller_service:
            conditions.append("caller_service = :caller_service")
            params["caller_service"] = caller_service
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if group_key:
            conditions.append("group_key = :group_key")
            params["group_key"] = group_key
        if event_name:
            conditions.append("event_name = :event_name")
            params["event_name"] = event_name

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        query = text(
            f"""
            SELECT * FROM scheduled_events
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        result = await session.execute(query, params)
        return [dict(row) for row in result.mappings().all()]

    async def get_due_events(
        self, session: AsyncSession, now: datetime, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch events that are due to fire (next_fire_at <= now and status = 'active')."""
        query = text(
            """
            SELECT * FROM scheduled_events
            WHERE status = 'active'
              AND next_fire_at IS NOT NULL
              AND next_fire_at <= :now
            ORDER BY next_fire_at ASC
            LIMIT :limit
            """
        )
        result = await session.execute(query, {"now": now, "limit": limit})
        return [dict(row) for row in result.mappings().all()]

    async def mark_fired(
        self,
        session: AsyncSession,
        event_id: UUID,
        fired_at: datetime,
        next_fire_at: datetime | None,
        new_status: str,
    ) -> int:
        """Update event after firing: increment fire_count, set times, update status."""
        query = text(
            """
            UPDATE scheduled_events
            SET fire_count = fire_count + 1,
                last_fired_at = :fired_at,
                next_fire_at = :next_fire_at,
                status = :new_status
            WHERE id = :event_id
            RETURNING id
            """
        )
        result = await session.execute(
            query,
            {
                "event_id": str(event_id),
                "fired_at": fired_at,
                "next_fire_at": next_fire_at,
                "new_status": new_status,
            },
        )
        return result.rowcount or 0

    async def update_status(
        self, session: AsyncSession, event_id: UUID, status: str
    ) -> int:
        query = text(
            """
            UPDATE scheduled_events
            SET status = :status
            WHERE id = :event_id
            RETURNING id
            """
        )
        result = await session.execute(
            query, {"event_id": str(event_id), "status": status}
        )
        return result.rowcount or 0

    async def update_event(
        self,
        session: AsyncSession,
        event_id: UUID,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update arbitrary fields on a scheduled event."""
        if not updates:
            return await self.get_event_by_id(session, event_id)

        import json

        set_clauses = []
        params: dict[str, Any] = {"event_id": str(event_id)}
        for key, value in updates.items():
            if key == "payload":
                set_clauses.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value)
            else:
                set_clauses.append(f"{key} = :{key}")
                params[key] = value

        query = text(
            f"""
            UPDATE scheduled_events
            SET {', '.join(set_clauses)}
            WHERE id = :event_id
            RETURNING *
            """
        )
        result = await session.execute(query, params)
        row = result.mappings().first()
        return dict(row) if row else None

    async def delete_event(self, session: AsyncSession, event_id: UUID) -> int:
        query = text("DELETE FROM scheduled_events WHERE id = :event_id")
        result = await session.execute(query, {"event_id": str(event_id)})
        return result.rowcount or 0

    async def delete_by_group_key(
        self, session: AsyncSession, group_key: str
    ) -> int:
        query = text(
            "DELETE FROM scheduled_events WHERE group_key = :group_key"
        )
        result = await session.execute(query, {"group_key": group_key})
        return result.rowcount or 0

    async def count_events(
        self,
        session: AsyncSession,
        caller_service: str | None = None,
        status: str | None = None,
        group_key: str | None = None,
    ) -> int:
        conditions = []
        params: dict[str, Any] = {}
        if caller_service:
            conditions.append("caller_service = :caller_service")
            params["caller_service"] = caller_service
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if group_key:
            conditions.append("group_key = :group_key")
            params["group_key"] = group_key

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        query = text(
            f"SELECT COUNT(*) AS cnt FROM scheduled_events WHERE {where_clause}"
        )
        result = await session.execute(query, params)
        row = result.mappings().first()
        return row["cnt"] if row else 0
