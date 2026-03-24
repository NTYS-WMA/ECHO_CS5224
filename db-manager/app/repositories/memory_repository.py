import json
from typing import Any, List
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

    async def get_memories_by_scope(
        self, 
        session: AsyncSession, 
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None
    ) -> List[dict[str, Any]]:
        """Get all memories for given scope(s)"""
        conditions = []
        params = {}
        
        if user_id:
            conditions.append("payload->>'user_id' = :user_id")
            params["user_id"] = user_id
        if agent_id:
            conditions.append("payload->>'agent_id' = :agent_id")
            params["agent_id"] = agent_id
        if run_id:
            conditions.append("payload->>'run_id' = :run_id")
            params["run_id"] = run_id
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = text(f"""
            SELECT id, payload
            FROM memories
            WHERE {where_clause}
            ORDER BY payload->>'created_at' DESC
        """)
        
        result = await session.execute(query, params)
        return [dict(row) for row in result.mappings()]

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

    async def update_memory_payload(
        self,
        session: AsyncSession,
        memory_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        """Update only the payload of a memory"""
        query = text(
            """
            UPDATE memories
            SET payload = CAST(:payload AS jsonb)
            WHERE id = :memory_id
            """
        )
        await session.execute(
            query,
            {
                "memory_id": memory_id,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        )

    async def delete_memory(self, session: AsyncSession, memory_id: UUID) -> None:
        """Delete a memory by ID"""
        query = text("DELETE FROM memories WHERE id = :memory_id")
        await session.execute(query, {"memory_id": memory_id})

    async def delete_memories_by_scope(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None
    ) -> None:
        """Delete all memories for given scope(s)"""
        conditions = []
        params = {}
        
        if user_id:
            conditions.append("payload->>'user_id' = :user_id")
            params["user_id"] = user_id
        if agent_id:
            conditions.append("payload->>'agent_id' = :agent_id")
            params["agent_id"] = agent_id
        if run_id:
            conditions.append("payload->>'run_id' = :run_id")
            params["run_id"] = run_id
        
        if not conditions:
            return  # Don't delete everything
        
        where_clause = " AND ".join(conditions)
        query = text(f"DELETE FROM memories WHERE {where_clause}")
        await session.execute(query, params)

    async def search_memories(
        self,
        session: AsyncSession,
        query_vector: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 5,
        threshold: float | None = None
    ) -> List[dict[str, Any]]:
        """Vector similarity search for memories"""
        conditions = []
        params = {"query_vector": query_vector, "limit": limit}
        
        if user_id:
            conditions.append("payload->>'user_id' = :user_id")
            params["user_id"] = user_id
        if agent_id:
            conditions.append("payload->>'agent_id' = :agent_id")
            params["agent_id"] = agent_id
        if run_id:
            conditions.append("payload->>'run_id' = :run_id")
            params["run_id"] = run_id
        
        # Add metadata filters
        if filters:
            for key, value in filters.items():
                conditions.append(f"payload->'metadata'->>'{key}' = :filter_{key}")
                params[f"filter_{key}"] = value
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        similarity_condition = ""
        if threshold is not None:
            similarity_condition = f"WHERE similarity >= {threshold}"
            params["threshold"] = threshold
        
        query = text(f"""
            SELECT id, payload, 
                   1 - (vector <=> CAST(:query_vector AS vector)) as similarity
            FROM memories
            WHERE {where_clause}
            ORDER BY vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
        """)
        
        result = await session.execute(query, params)
        rows = [dict(row) for row in result.mappings()]
        
        # Apply threshold filter if specified
        if threshold is not None:
            rows = [row for row in rows if row["similarity"] >= threshold]
        
        return rows

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

    async def get_memory_history(self, session: AsyncSession, memory_id: UUID) -> List[dict[str, Any]]:
        """Get change history for a memory"""
        query = text(
            """
            SELECT id, memory_id, old_memory, new_memory, event, created_at, updated_at, 
                   is_deleted, actor_id, role
            FROM memory_history
            WHERE memory_id = :memory_id
            ORDER BY created_at DESC
            """
        )
        result = await session.execute(query, {"memory_id": memory_id})
        return [dict(row) for row in result.mappings()]
