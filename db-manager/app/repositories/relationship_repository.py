import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RelationshipRepository:
    """PostgreSQL repository for relationship score and audit history."""

    async def get_score_context(self, session: AsyncSession, user_id: str) -> dict[str, Any] | None:
        query = text(
            """
            SELECT user_id, score, tier, total_interactions, positive_interactions,
                   negative_interactions, last_interaction_at, last_scored_at,
                   last_decay_at, updated_at
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
        tier: str,
        total_interactions: int,
        positive_interactions: int,
        negative_interactions: int,
    ) -> None:
        query = text(
            """
            INSERT INTO relationship_scores (
                user_id, score, tier, total_interactions, positive_interactions, negative_interactions
            )
            VALUES (
                :user_id, :score, :tier, :total_interactions, :positive_interactions, :negative_interactions
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
                score = EXCLUDED.score,
                tier = EXCLUDED.tier,
                total_interactions = EXCLUDED.total_interactions,
                positive_interactions = EXCLUDED.positive_interactions,
                negative_interactions = EXCLUDED.negative_interactions,
                updated_at = NOW()
            """
        )
        await session.execute(
            query,
            {
                "user_id": user_id,
                "score": score,
                "tier": tier,
                "total_interactions": total_interactions,
                "positive_interactions": positive_interactions,
                "negative_interactions": negative_interactions,
            },
        )

    async def append_score_history(
        self,
        session: AsyncSession,
        user_id: str,
        delta: float,
        old_score: float | None,
        new_score: float,
        sentiment: str | None,
        intensity: float | None,
        reason: str | None,
        reasoning: str | None,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        query = text(
            """
            INSERT INTO score_history (
                user_id, delta, old_score, new_score, sentiment, intensity,
                reason, reasoning, source, metadata
            )
            VALUES (
                :user_id, :delta, :old_score, :new_score, :sentiment, :intensity,
                :reason, :reasoning, :source, CAST(:metadata AS jsonb)
            )
            """
        )
        await session.execute(
            query,
            {
                "user_id": user_id,
                "delta": delta,
                "old_score": old_score,
                "new_score": new_score,
                "sentiment": sentiment,
                "intensity": intensity,
                "reason": reason,
                "reasoning": reasoning,
                "source": source,
                "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            },
        )
