from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.db.postgres import get_postgres_session_maker
from app.repositories.relationship_repository import RelationshipRepository

router = APIRouter(prefix="/relationship-db", tags=["relationship-db"])
relationship_repo = RelationshipRepository()


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            output[key] = value.isoformat()
        else:
            output[key] = value
    return output


class UserUpsertRequest(BaseModel):
    telegram_id: Optional[int] = None
    first_name: Optional[str] = None
    onboarding_complete: bool = False
    last_active_at: Optional[datetime] = None


class UserResponse(BaseModel):
    id: str
    telegram_id: Optional[int] = None
    first_name: Optional[str] = None
    onboarding_complete: bool
    last_active_at: Optional[str] = None


class MessageCreateRequest(BaseModel):
    user_id: str
    role: Optional[str] = None
    content: Optional[str] = None
    is_proactive: bool = False
    created_at: Optional[datetime] = None


class MessageUpdateRequest(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    is_proactive: Optional[bool] = None


class MessageItem(BaseModel):
    id: int
    user_id: str
    role: Optional[str] = None
    content: Optional[str] = None
    is_proactive: bool
    created_at: str


class ScoreUpsertRequest(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    total_interactions: int = Field(default=0, ge=0)
    positive_interactions: int = Field(default=0, ge=0)
    negative_interactions: int = Field(default=0, ge=0)
    last_scored_at: Optional[datetime] = None
    last_decay_at: Optional[datetime] = None


class ScoreResponse(BaseModel):
    user_id: str
    score: float
    total_interactions: int
    positive_interactions: int
    negative_interactions: int
    last_scored_at: Optional[str] = None
    last_decay_at: Optional[str] = None
    last_updated: Optional[str] = None


class ScoreHistoryCreateRequest(BaseModel):
    delta: float
    new_score: float = Field(ge=0.0, le=1.0)
    sentiment: Optional[str] = None
    intensity: Optional[str] = None
    reason: str
    reasoning: Optional[str] = None
    scored_at: Optional[datetime] = None


class ScoreHistoryItem(BaseModel):
    id: int
    user_id: str
    delta: float
    new_score: float
    sentiment: Optional[str] = None
    intensity: Optional[str] = None
    reason: str
    reasoning: Optional[str] = None
    scored_at: str


@router.get("/users/ended-sessions")
async def get_users_with_ended_sessions(
    inactive_minutes: int = Query(30, ge=1, le=24 * 60),
) -> dict[str, List[dict[str, Any]]]:
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        rows = await relationship_repo.get_users_with_ended_sessions(session, inactive_minutes=inactive_minutes)
        return {"results": [_serialize_row(row) for row in rows]}


@router.get("/users/inactive")
async def get_inactive_users(
    inactive_hours: int = Query(24, ge=1, le=24 * 365),
) -> dict[str, List[UserResponse]]:
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        rows = await relationship_repo.get_inactive_users(session, inactive_hours=inactive_hours)
        results = [
            UserResponse(
                id=row["id"],
                telegram_id=row.get("telegram_id"),
                first_name=row.get("first_name"),
                onboarding_complete=row.get("onboarding_complete", False),
                last_active_at=row["last_active_at"].isoformat() if row.get("last_active_at") else None,
            )
            for row in rows
        ]
        return {"results": results}


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        row = await relationship_repo.get_user_by_id(session, user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            id=row["id"],
            telegram_id=row.get("telegram_id"),
            first_name=row.get("first_name"),
            onboarding_complete=row.get("onboarding_complete", False),
            last_active_at=row["last_active_at"].isoformat() if row.get("last_active_at") else None,
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def upsert_user(user_id: str, request: UserUpsertRequest):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        await relationship_repo.upsert_user(
            session,
            user_id=user_id,
            telegram_id=request.telegram_id,
            first_name=request.first_name,
            onboarding_complete=request.onboarding_complete,
            last_active_at=request.last_active_at,
        )
        await session.commit()
        row = await relationship_repo.get_user_by_id(session, user_id)
        if not row:
            raise HTTPException(status_code=500, detail="Upsert user failed")
        return UserResponse(
            id=row["id"],
            telegram_id=row.get("telegram_id"),
            first_name=row.get("first_name"),
            onboarding_complete=row.get("onboarding_complete", False),
            last_active_at=row["last_active_at"].isoformat() if row.get("last_active_at") else None,
        )


@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        deleted = await relationship_repo.delete_user(session, user_id)
        await session.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "user_id": user_id}


@router.post("/messages", response_model=MessageItem)
async def create_message(request: MessageCreateRequest):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        try:
            row = await relationship_repo.insert_message(
                session,
                user_id=request.user_id,
                role=request.role,
                content=request.content,
                is_proactive=request.is_proactive,
                created_at=request.created_at,
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Invalid user_id or message payload")

        if not row:
            raise HTTPException(status_code=500, detail="Create message failed")
        return MessageItem(
            id=row["id"],
            user_id=row["user_id"],
            role=row.get("role"),
            content=row.get("content"),
            is_proactive=row.get("is_proactive", False),
            created_at=row["created_at"].isoformat(),
        )


@router.get("/messages", response_model=dict[str, List[MessageItem]])
async def get_messages(
    user_id: str = Query(...),
    since: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=2000),
):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        rows = await relationship_repo.get_messages_since(session, user_id=user_id, since=since, limit=limit)
        results = [
            MessageItem(
                id=row["id"],
                user_id=row["user_id"],
                role=row.get("role"),
                content=row.get("content"),
                is_proactive=row.get("is_proactive", False),
                created_at=row["created_at"].isoformat(),
            )
            for row in rows
        ]
        return {"results": results}


@router.get("/messages/{message_id}", response_model=MessageItem)
async def get_message(message_id: int):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        row = await relationship_repo.get_message_by_id(session, message_id)
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        return MessageItem(
            id=row["id"],
            user_id=row["user_id"],
            role=row.get("role"),
            content=row.get("content"),
            is_proactive=row.get("is_proactive", False),
            created_at=row["created_at"].isoformat(),
        )


@router.put("/messages/{message_id}", response_model=MessageItem)
async def update_message(message_id: int, request: MessageUpdateRequest):
    if request.role is None and request.content is None and request.is_proactive is None:
        raise HTTPException(status_code=400, detail="No message fields provided for update")

    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        row = await relationship_repo.update_message(
            session,
            message_id=message_id,
            role=request.role,
            content=request.content,
            is_proactive=request.is_proactive,
        )
        await session.commit()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")

        return MessageItem(
            id=row["id"],
            user_id=row["user_id"],
            role=row.get("role"),
            content=row.get("content"),
            is_proactive=row.get("is_proactive", False),
            created_at=row["created_at"].isoformat(),
        )


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        deleted = await relationship_repo.delete_message(session, message_id)
        await session.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True, "message_id": message_id}


@router.get("/scores/{user_id}", response_model=ScoreResponse)
async def get_score(user_id: str):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        row = await relationship_repo.get_score_context(session, user_id)
        if not row:
            raise HTTPException(status_code=404, detail="Relationship score not found")
        return ScoreResponse(
            user_id=row["user_id"],
            score=float(row["score"]),
            total_interactions=row["total_interactions"],
            positive_interactions=row["positive_interactions"],
            negative_interactions=row["negative_interactions"],
            last_scored_at=row["last_scored_at"].isoformat() if row.get("last_scored_at") else None,
            last_decay_at=row["last_decay_at"].isoformat() if row.get("last_decay_at") else None,
            last_updated=row["last_updated"].isoformat() if row.get("last_updated") else None,
        )


@router.put("/scores/{user_id}", response_model=ScoreResponse)
async def upsert_score(user_id: str, request: ScoreUpsertRequest):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        try:
            await relationship_repo.upsert_score(
                session,
                user_id=user_id,
                score=request.score,
                total_interactions=request.total_interactions,
                positive_interactions=request.positive_interactions,
                negative_interactions=request.negative_interactions,
                last_scored_at=request.last_scored_at,
                last_decay_at=request.last_decay_at,
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Invalid user_id for relationship score")

        row = await relationship_repo.get_score_context(session, user_id)
        if not row:
            raise HTTPException(status_code=500, detail="Upsert score failed")
        return ScoreResponse(
            user_id=row["user_id"],
            score=float(row["score"]),
            total_interactions=row["total_interactions"],
            positive_interactions=row["positive_interactions"],
            negative_interactions=row["negative_interactions"],
            last_scored_at=row["last_scored_at"].isoformat() if row.get("last_scored_at") else None,
            last_decay_at=row["last_decay_at"].isoformat() if row.get("last_decay_at") else None,
            last_updated=row["last_updated"].isoformat() if row.get("last_updated") else None,
        )


@router.delete("/scores/{user_id}")
async def delete_score(user_id: str):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        deleted = await relationship_repo.delete_score(session, user_id)
        await session.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Relationship score not found")
    return {"success": True, "user_id": user_id}


@router.post("/scores/{user_id}/history", response_model=ScoreHistoryItem)
async def create_score_history(user_id: str, request: ScoreHistoryCreateRequest):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        try:
            row = await relationship_repo.append_score_history(
                session,
                user_id=user_id,
                delta=request.delta,
                new_score=request.new_score,
                sentiment=request.sentiment,
                intensity=request.intensity,
                reason=request.reason,
                reasoning=request.reasoning,
                scored_at=request.scored_at,
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Invalid user_id for score history")

        if not row:
            raise HTTPException(status_code=500, detail="Create score history failed")
        return ScoreHistoryItem(
            id=row["id"],
            user_id=row["user_id"],
            delta=float(row["delta"]),
            new_score=float(row["new_score"]),
            sentiment=row.get("sentiment"),
            intensity=row.get("intensity"),
            reason=row["reason"],
            reasoning=row.get("reasoning"),
            scored_at=row["scored_at"].isoformat(),
        )


@router.get("/scores/{user_id}/history", response_model=dict[str, List[ScoreHistoryItem]])
async def get_score_history(
    user_id: str,
    limit: int = Query(100, ge=1, le=2000),
):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        rows = await relationship_repo.get_score_history(session, user_id=user_id, limit=limit)
        results = [
            ScoreHistoryItem(
                id=row["id"],
                user_id=row["user_id"],
                delta=float(row["delta"]),
                new_score=float(row["new_score"]),
                sentiment=row.get("sentiment"),
                intensity=row.get("intensity"),
                reason=row["reason"],
                reasoning=row.get("reasoning"),
                scored_at=row["scored_at"].isoformat(),
            )
            for row in rows
        ]
        return {"results": results}


@router.delete("/scores/{user_id}/history/{history_id}")
async def delete_score_history_item(user_id: str, history_id: int):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        deleted = await relationship_repo.delete_score_history_item(session, user_id=user_id, history_id=history_id)
        await session.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Score history item not found")
    return {"success": True, "user_id": user_id, "history_id": history_id}


@router.delete("/scores/{user_id}/history")
async def delete_score_history(user_id: str):
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        deleted = await relationship_repo.delete_score_history(session, user_id=user_id)
        await session.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Score history not found")
    return {"success": True, "user_id": user_id, "deleted_count": deleted}
