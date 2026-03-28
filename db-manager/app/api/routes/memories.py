from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.postgres import get_pg_session
from app.repositories.memory_repository import MemoryRepository

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class MemoryWriteRequest(BaseModel):
    messages: List[Message]
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MemoryItem(BaseModel):
    id: str
    memory: str
    hash: str
    created_at: str
    updated_at: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    actor_id: Optional[str] = None
    role: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MemoryWriteResponse(BaseModel):
    results: List[Dict[str, Any]]


class MemoryUpdateRequest(BaseModel):
    memory: str


class SearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = 5
    threshold: Optional[float] = None


class SearchResult(BaseModel):
    id: str
    memory: str
    score: float
    hash: str
    created_at: str
    updated_at: str
    user_id: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]


class HistoryItem(BaseModel):
    id: str
    memory_id: str
    old_memory: Optional[str] = None
    new_memory: Optional[str] = None
    event: str
    created_at: str
    updated_at: str
    is_deleted: bool
    actor_id: Optional[str] = None
    role: Optional[str] = None


memory_repo = MemoryRepository()
EMBEDDING_DIMS = 1536


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_memories(messages: List[Message]) -> List[str]:
    user_contents = [m.content.strip() for m in messages if m.role.lower() == "user" and m.content and m.content.strip()]
    if user_contents:
        return user_contents
    return [m.content.strip() for m in messages if m.content and m.content.strip()]


def _memory_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_unit_vector(text: str, dims: int = EMBEDDING_DIMS) -> list[float]:
    # Deterministic embedding fallback to keep API functional without external embedding service.
    vec = [0.0] * dims
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        mag = 1.0 + (digest[5] / 255.0)
        vec[idx] += sign * mag

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec[0] = 1.0
        norm = 1.0
    return [v / norm for v in vec]


def _vector_literal(text: str) -> str:
    vector = _to_unit_vector(text)
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


def _payload_to_memory_item(memory_id: UUID | str, payload: dict[str, Any]) -> MemoryItem:
    return MemoryItem(
        id=str(memory_id),
        memory=payload.get("memory", ""),
        hash=payload.get("hash", ""),
        created_at=payload.get("created_at", ""),
        updated_at=payload.get("updated_at", ""),
        user_id=payload.get("user_id"),
        agent_id=payload.get("agent_id"),
        run_id=payload.get("run_id"),
        actor_id=payload.get("actor_id"),
        role=payload.get("role"),
        metadata=payload.get("metadata"),
    )


@router.post("/memories", response_model=MemoryWriteResponse)
async def create_memories(request: MemoryWriteRequest):
    if not any([request.user_id, request.agent_id, request.run_id]):
        raise HTTPException(status_code=400, detail="At least one of user_id, agent_id, or run_id must be provided")

    memory_texts = _extract_memories(request.messages)
    if not memory_texts:
        raise HTTPException(status_code=400, detail="No usable message content found")

    results: list[dict[str, Any]] = []
    async with get_pg_session() as session:
        for text in memory_texts:
            memory_id = uuid4()
            now = _now_iso()
            payload: dict[str, Any] = {
                "memory": text,
                "hash": _memory_hash(text),
                "created_at": now,
                "updated_at": now,
                "user_id": request.user_id,
                "agent_id": request.agent_id,
                "run_id": request.run_id,
                "metadata": request.metadata or {},
            }
            await memory_repo.upsert_memory(
                session=session,
                memory_id=memory_id,
                vector_literal=_vector_literal(text),
                payload=payload,
            )
            await memory_repo.append_history(
                session=session,
                history_id=uuid4(),
                memory_id=memory_id,
                event="ADD",
                old_memory=None,
                new_memory=text,
                actor_id=request.user_id or request.agent_id,
                role="user",
            )
            results.append({"id": str(memory_id), "memory": text, "event": "ADD"})
        await session.commit()

    return MemoryWriteResponse(results=results)


@router.get("/memories", response_model=Dict[str, List[MemoryItem]])
async def get_memories(
    user_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    if not any([user_id, agent_id, run_id]):
        raise HTTPException(status_code=400, detail="At least one of user_id, agent_id, or run_id must be provided")

    async with get_pg_session() as session:
        rows = await memory_repo.get_memories_by_scope(
            session=session,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
        )

    items = [_payload_to_memory_item(row["id"], row.get("payload") or {}) for row in rows]
    return {"results": items}


@router.get("/memories/{memory_id}", response_model=MemoryItem)
async def get_memory(memory_id: str):
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")

    async with get_pg_session() as session:
        result = await memory_repo.get_memory_by_id(session, uuid)
        if not result:
            raise HTTPException(status_code=404, detail="Memory not found")

    payload = result.get("payload") or {}
    return _payload_to_memory_item(result["id"], payload)


@router.put("/memories/{memory_id}")
async def update_memory(memory_id: str, request: MemoryUpdateRequest):
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")

    async with get_pg_session() as session:
        existing = await memory_repo.get_memory_by_id(session, uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Memory not found")

        payload = existing.get("payload") or {}
        old_memory = payload.get("memory")
        payload["memory"] = request.memory
        payload["hash"] = _memory_hash(request.memory)
        payload["updated_at"] = _now_iso()

        await memory_repo.upsert_memory(
            session=session,
            memory_id=uuid,
            vector_literal=_vector_literal(request.memory),
            payload=payload,
        )
        await memory_repo.append_history(
            session=session,
            history_id=uuid4(),
            memory_id=uuid,
            event="UPDATE",
            old_memory=old_memory,
            new_memory=request.memory,
            actor_id=payload.get("user_id") or payload.get("agent_id"),
            role=payload.get("role"),
        )
        await session.commit()

    return {"message": "Memory updated successfully"}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")

    async with get_pg_session() as session:
        existing = await memory_repo.get_memory_by_id(session, uuid)
        if not existing:
            raise HTTPException(status_code=404, detail="Memory not found")

        payload = existing.get("payload") or {}
        await memory_repo.append_history(
            session=session,
            history_id=uuid4(),
            memory_id=uuid,
            event="DELETE",
            old_memory=payload.get("memory"),
            new_memory=None,
            actor_id=payload.get("user_id") or payload.get("agent_id"),
            role=payload.get("role"),
        )
        await memory_repo.delete_memory(session, uuid)
        await session.commit()

    return {"message": "Memory deleted successfully"}


@router.delete("/memories")
async def delete_all_memories(
    user_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    if not any([user_id, agent_id, run_id]):
        raise HTTPException(status_code=400, detail="At least one of user_id, agent_id, or run_id must be provided")

    async with get_pg_session() as session:
        rows = await memory_repo.get_memories_by_scope(
            session=session,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
        )
        for row in rows:
            payload = row.get("payload") or {}
            await memory_repo.append_history(
                session=session,
                history_id=uuid4(),
                memory_id=row["id"],
                event="DELETE",
                old_memory=payload.get("memory"),
                new_memory=None,
                actor_id=payload.get("user_id") or payload.get("agent_id"),
                role=payload.get("role"),
            )

        await memory_repo.delete_memories_by_scope(
            session=session,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
        )
        await session.commit()

    return {"message": "All relevant memories deleted"}


@router.post("/search", response_model=SearchResponse)
async def search_memories(request: SearchRequest):
    if not any([request.user_id, request.agent_id, request.run_id]):
        raise HTTPException(status_code=400, detail="At least one of user_id, agent_id, or run_id must be provided")

    async with get_pg_session() as session:
        rows = await memory_repo.search_memories(
            session=session,
            query_vector=_vector_literal(request.query),
            user_id=request.user_id,
            agent_id=request.agent_id,
            run_id=request.run_id,
            filters=request.filters,
            limit=request.limit,
            threshold=request.threshold,
        )

    results = []
    for row in rows:
        payload = row.get("payload") or {}
        results.append(
            SearchResult(
                id=str(row["id"]),
                memory=payload.get("memory", ""),
                score=float(row.get("similarity", 0.0)),
                hash=payload.get("hash", ""),
                created_at=payload.get("created_at", ""),
                updated_at=payload.get("updated_at", ""),
                user_id=payload.get("user_id"),
            )
        )

    return SearchResponse(results=results)


@router.get("/memories/{memory_id}/history", response_model=List[HistoryItem])
async def get_memory_history(memory_id: str):
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")

    async with get_pg_session() as session:
        rows = await memory_repo.get_memory_history(session, uuid)

    return [
        HistoryItem(
            id=str(row["id"]),
            memory_id=str(row["memory_id"]),
            old_memory=row.get("old_memory"),
            new_memory=row.get("new_memory"),
            event=row["event"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
            is_deleted=row["is_deleted"],
            actor_id=row.get("actor_id"),
            role=row.get("role"),
        )
        for row in rows
    ]
