"""
DB Manager — async SQLAlchemy operations for the Relationship Service.

Only includes the queries this service needs. All writes are scoped to
the relationship_scores table. User and Message rows are read-only.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings
from models.schema import Message, RelationshipScore, ScoreHistory, User

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ─── Users (read-only) ────────────────────────────────────────────────────────


async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_users_with_ended_sessions(
    session: AsyncSession,
    inactive_minutes: int = 30,
) -> list[tuple[User, RelationshipScore]]:
    """
    Return (User, RelationshipScore) pairs whose session has ended and not yet scored.

    Eligibility:
      1. last_active_at < now - inactive_minutes  — session ended
      2. last_scored_at IS NULL OR last_scored_at < last_active_at — unscored messages exist
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=inactive_minutes)
    result = await session.execute(
        select(User, RelationshipScore)
        .join(RelationshipScore, RelationshipScore.user_id == User.id)
        .where(
            User.onboarding_complete == True,
            User.last_active_at < cutoff,
            or_(
                RelationshipScore.last_scored_at.is_(None),
                RelationshipScore.last_scored_at < User.last_active_at,
            ),
        )
    )
    return result.all()


async def get_inactive_users(session: AsyncSession, inactive_hours: int) -> list[User]:
    """Return onboarded users inactive for more than `inactive_hours`."""
    threshold = datetime.now(timezone.utc) - timedelta(hours=inactive_hours)
    result = await session.execute(
        select(User).where(
            User.last_active_at < threshold,
            User.onboarding_complete == True,
        )
    )
    return result.scalars().all()


# ─── Messages (read-only) ─────────────────────────────────────────────────────


async def get_messages_since_datetime(
    session: AsyncSession,
    user_id: str,
    since: Optional[datetime],
) -> list[Message]:
    """Return all messages for a user after `since`, in chronological order."""
    query = (
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.asc())
    )
    if since is not None:
        query = query.where(Message.created_at > since)
    result = await session.execute(query)
    return result.scalars().all()


# ─── Relationship Score (read/write) ─────────────────────────────────────────


async def get_relationship_score(session: AsyncSession, user_id: str) -> Optional[RelationshipScore]:
    result = await session.execute(
        select(RelationshipScore).where(RelationshipScore.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_relationship_score(
    session: AsyncSession,
    user_id: str,
    delta: float,
    is_positive: bool,
    is_decay: bool = False,
) -> float:
    """
    Adjust score by `delta` and return the new score.

    Interaction counters are only incremented for real session scores, not decay.
    """
    rel = await get_relationship_score(session, user_id)
    if not rel:
        rel = RelationshipScore(user_id=user_id)
        session.add(rel)

    rel.score = max(0.0, min(1.0, rel.score + delta))

    if not is_decay:
        rel.total_interactions += 1
        if is_positive:
            rel.positive_interactions += 1
        else:
            rel.negative_interactions += 1

    now = datetime.now(timezone.utc)
    rel.last_updated = now
    if is_decay:
        rel.last_decay_at = now

    await session.commit()
    return rel.score


async def insert_score_history(
    session: AsyncSession,
    user_id: str,
    delta: float,
    new_score: float,
    reason: str,
    sentiment: Optional[str] = None,
    intensity: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> None:
    session.add(ScoreHistory(
        user_id=user_id,
        delta=delta,
        new_score=new_score,
        sentiment=sentiment,
        intensity=intensity,
        reasoning=reasoning,
        reason=reason,
    ))
    await session.commit()


async def stamp_last_scored_at(session: AsyncSession, user_id: str) -> None:
    """Mark a session as scored so it is not re-evaluated on the next cron run."""
    await session.execute(
        update(RelationshipScore)
        .where(RelationshipScore.user_id == user_id)
        .values(last_scored_at=datetime.now(timezone.utc))
    )
    await session.commit()
