from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RelationshipRepository:
    """PostgreSQL repository for users/messages/relationship score/history."""

    async def get_user_by_id(self, session: AsyncSession, user_id: str) -> dict[str, Any] | None:
        query = text(
            """
            SELECT id, telegram_id, first_name, onboarding_complete, last_active_at
            FROM users
            WHERE id = :user_id
            """
        )
        result = await session.execute(query, {"user_id": user_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_user(
        self,
        session: AsyncSession,
        user_id: str,
        telegram_id: int | None,
        first_name: str | None,
        onboarding_complete: bool,
        last_active_at: Any | None,
    ) -> None:
        query = text(
            """
            INSERT INTO users (id, telegram_id, first_name, onboarding_complete, last_active_at)
            VALUES (:user_id, :telegram_id, :first_name, :onboarding_complete, :last_active_at)
            ON CONFLICT (id)
            DO UPDATE SET
                telegram_id = EXCLUDED.telegram_id,
                first_name = EXCLUDED.first_name,
                onboarding_complete = EXCLUDED.onboarding_complete,
                last_active_at = EXCLUDED.last_active_at
            """
        )
        await session.execute(
            query,
            {
                "user_id": user_id,
                "telegram_id": telegram_id,
                "first_name": first_name,
                "onboarding_complete": onboarding_complete,
                "last_active_at": last_active_at,
            },
        )

    async def get_users_with_ended_sessions(
        self, session: AsyncSession, inactive_minutes: int = 30
    ) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT
                u.id,
                u.telegram_id,
                u.first_name,
                u.onboarding_complete,
                u.last_active_at,
                rs.score,
                rs.total_interactions,
                rs.positive_interactions,
                rs.negative_interactions,
                rs.last_updated,
                rs.last_scored_at,
                rs.last_decay_at
            FROM users u
            JOIN relationship_scores rs ON rs.user_id = u.id
            WHERE u.onboarding_complete = TRUE
              AND u.last_active_at < NOW() - (:inactive_minutes * INTERVAL '1 minute')
              AND (rs.last_scored_at IS NULL OR rs.last_scored_at < u.last_active_at)
            ORDER BY u.last_active_at ASC
            """
        )
        result = await session.execute(query, {"inactive_minutes": inactive_minutes})
        return [dict(row) for row in result.mappings()]

    async def get_inactive_users(self, session: AsyncSession, inactive_hours: int) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT id, telegram_id, first_name, onboarding_complete, last_active_at
            FROM users
            WHERE onboarding_complete = TRUE
              AND last_active_at < NOW() - (:inactive_hours * INTERVAL '1 hour')
            ORDER BY last_active_at ASC
            """
        )
        result = await session.execute(query, {"inactive_hours": inactive_hours})
        return [dict(row) for row in result.mappings()]

    async def insert_message(
        self,
        session: AsyncSession,
        user_id: str,
        role: str | None,
        content: str | None,
        is_proactive: bool,
        created_at: Any | None,
    ) -> dict[str, Any]:
        query = text(
            """
            INSERT INTO messages (user_id, role, content, is_proactive, created_at)
            VALUES (:user_id, :role, :content, :is_proactive, COALESCE(:created_at, NOW()))
            RETURNING id, user_id, role, content, is_proactive, created_at
            """
        )
        result = await session.execute(
            query,
            {
                "user_id": user_id,
                "role": role,
                "content": content,
                "is_proactive": is_proactive,
                "created_at": created_at,
            },
        )
        row = result.mappings().first()
        return dict(row) if row else {}

    async def get_messages_since(
        self,
        session: AsyncSession,
        user_id: str,
        since: Any | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        base_sql = """
            SELECT id, user_id, role, content, is_proactive, created_at
            FROM messages
            WHERE user_id = :user_id
        """
        params: dict[str, Any] = {"user_id": user_id, "limit": limit}
        if since is not None:
            base_sql += " AND created_at > :since"
            params["since"] = since
        base_sql += " ORDER BY created_at ASC LIMIT :limit"
        result = await session.execute(text(base_sql), params)
        return [dict(row) for row in result.mappings()]

    async def get_score_context(self, session: AsyncSession, user_id: str) -> dict[str, Any] | None:
        query = text(
            """
            SELECT user_id, score, total_interactions, positive_interactions,
                   negative_interactions, last_scored_at, last_decay_at, last_updated
            FROM relationship_scores
            WHERE user_id = :user_id
            """
        )
        result = await session.execute(query, {"user_id": user_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_score(
        self,
        session: AsyncSession,
        user_id: str,
        score: float,
        total_interactions: int,
        positive_interactions: int,
        negative_interactions: int,
        last_scored_at: Any | None = None,
        last_decay_at: Any | None = None,
    ) -> None:
        query = text(
            """
            INSERT INTO relationship_scores (
                user_id, score, total_interactions, positive_interactions, negative_interactions,
                last_scored_at, last_decay_at
            )
            VALUES (
                :user_id, :score, :total_interactions, :positive_interactions, :negative_interactions,
                :last_scored_at, :last_decay_at
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
                score = EXCLUDED.score,
                total_interactions = EXCLUDED.total_interactions,
                positive_interactions = EXCLUDED.positive_interactions,
                negative_interactions = EXCLUDED.negative_interactions,
                last_scored_at = COALESCE(EXCLUDED.last_scored_at, relationship_scores.last_scored_at),
                last_decay_at = COALESCE(EXCLUDED.last_decay_at, relationship_scores.last_decay_at),
                last_updated = NOW()
            """
        )
        await session.execute(
            query,
            {
                "user_id": user_id,
                "score": score,
                "total_interactions": total_interactions,
                "positive_interactions": positive_interactions,
                "negative_interactions": negative_interactions,
                "last_scored_at": last_scored_at,
                "last_decay_at": last_decay_at,
            },
        )

    async def append_score_history(
        self,
        session: AsyncSession,
        user_id: str,
        delta: float,
        new_score: float,
        sentiment: str | None,
        intensity: str | None,
        reason: str,
        reasoning: str | None,
        scored_at: Any | None = None,
    ) -> dict[str, Any]:
        query = text(
            """
            INSERT INTO score_history (
                user_id, delta, new_score, sentiment, intensity, reason, reasoning, scored_at
            )
            VALUES (
                :user_id, :delta, :new_score, :sentiment, :intensity, :reason, :reasoning,
                COALESCE(:scored_at, NOW())
            )
            RETURNING id, user_id, delta, new_score, sentiment, intensity, reason, reasoning, scored_at
            """
        )
        result = await session.execute(
            query,
            {
                "user_id": user_id,
                "delta": delta,
                "new_score": new_score,
                "sentiment": sentiment,
                "intensity": intensity,
                "reason": reason,
                "reasoning": reasoning,
                "scored_at": scored_at,
            },
        )
        row = result.mappings().first()
        return dict(row) if row else {}

    async def get_score_history(
        self, session: AsyncSession, user_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT id, user_id, delta, new_score, sentiment, intensity, reason, reasoning, scored_at
            FROM score_history
            WHERE user_id = :user_id
            ORDER BY scored_at DESC
            LIMIT :limit
            """
        )
        result = await session.execute(query, {"user_id": user_id, "limit": limit})
        return [dict(row) for row in result.mappings()]
