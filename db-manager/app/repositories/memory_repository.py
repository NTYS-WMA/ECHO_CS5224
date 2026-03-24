import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRepository:
    """PostgreSQL repository for memory vectors and history."""

    async def get_memory_by_id(self, session: AsyncSession, memory_id: UUID) -> dict[str, Any] | None:
        query = text(
            """
            SELECT id, payload
            FROM memories
            WHERE id = :memory_id
            """
        )
        result = await session.execute(query, {"memory_id": memory_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_memory(
        self,
        session: AsyncSession,
        memory_id: UUID,
        vector_literal: str,
        payload: dict[str, Any],
    ) -> None:
        # vector_literal format example: "[0.1,0.2,...]". This keeps repo generic
        # until AI service embedding contract is finalized.
        query = text(
            """
            INSERT INTO memories (id, vector, payload)
            VALUES (:memory_id, CAST(:vector_literal AS vector), CAST(:payload AS jsonb))
            ON CONFLICT (id)
            DO UPDATE SET
                vector = EXCLUDED.vector,
                payload = EXCLUDED.payload
            """
        )
        await session.execute(
            query,
            {
                "memory_id": memory_id,
                "vector_literal": vector_literal,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )

    async def append_history(
        self,
        session: AsyncSession,
        history_id: UUID,
        memory_id: UUID,
        event: str,
        old_memory: str | None,
        new_memory: str | None,
        actor_id: str | None,
        role: str | None,
    ) -> None:
        query = text(
            """
            INSERT INTO memory_history (
                id, memory_id, old_memory, new_memory, event, actor_id, role
            )
            VALUES (
                :id, :memory_id, :old_memory, :new_memory, :event, :actor_id, :role
            )
            """
        )
        await session.execute(
            query,
            {
                "id": history_id,
                "memory_id": memory_id,
                "old_memory": old_memory,
                "new_memory": new_memory,
                "event": event,
                "actor_id": actor_id,
                "role": role,
            },
        )
