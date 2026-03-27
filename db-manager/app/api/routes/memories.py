from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.repositories.memory_repository import MemoryRepository
from app.db.postgres import get_pg_session

router = APIRouter()

# Pydantic models for request/response
class Message(BaseModel):
    role: str  # "user" | "assistant"
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
    event: str  # "ADD" | "UPDATE" | "DELETE"
    created_at: str
    updated_at: str
    is_deleted: bool
    actor_id: Optional[str] = None
    role: Optional[str] = None

# Repository instance
memory_repo = MemoryRepository()

@router.post("/memories", response_model=MemoryWriteResponse)
async def create_memories(request: MemoryWriteRequest):
    """Write memories - extract facts from conversation messages and store in memory database"""
    # TODO: Implement LLM-based memory extraction
    # For now, return mock response
    return MemoryWriteResponse(results=[
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "memory": "Mock memory from messages",
            "event": "ADD"
        }
    ])

@router.get("/memories", response_model=Dict[str, List[MemoryItem]])
async def get_memories(
    user_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None)
):
    """Get all memories"""
    if not any([user_id, agent_id, run_id]):
        raise HTTPException(status_code=400, detail="At least one of user_id, agent_id, or run_id must be provided")
    
    # TODO: Implement actual retrieval
    return {"results": []}

@router.get("/memories/{memory_id}", response_model=MemoryItem)
async def get_memory(memory_id: str):
    """Get single memory"""
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")
    
    async with get_pg_session() as session:
        result = await memory_repo.get_memory_by_id(session, uuid)
        if not result:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        # Parse payload
        payload = result.get("payload", {})
        return MemoryItem(
            id=str(result["id"]),
            memory=payload.get("memory", ""),
            hash=payload.get("hash", ""),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            user_id=payload.get("user_id"),
            agent_id=payload.get("agent_id"),
            run_id=payload.get("run_id"),
            actor_id=payload.get("actor_id"),
            role=payload.get("role"),
            metadata=payload.get("metadata")
        )

@router.put("/memories/{memory_id}")
async def update_memory(memory_id: str, request: MemoryUpdateRequest):
    """Update memory"""
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")
    
    # TODO: Implement update logic
    return {"message": "Memory updated successfully"}

@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete single memory"""
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")
    
    # TODO: Implement delete logic
    return {"message": "Memory deleted successfully"}

@router.delete("/memories")
async def delete_all_memories(
    user_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None)
):
    """Delete all memories for a user"""
    if not any([user_id, agent_id, run_id]):
        raise HTTPException(status_code=400, detail="At least one of user_id, agent_id, or run_id must be provided")
    
    # TODO: Implement bulk delete
    return {"message": "All relevant memories deleted"}

@router.post("/search", response_model=SearchResponse)
async def search_memories(request: SearchRequest):
    """Semantic search memories"""
    # TODO: Implement vector search
    return SearchResponse(results=[])

@router.get("/memories/{memory_id}/history", response_model=List[HistoryItem])
async def get_memory_history(memory_id: str):
    """Memory change history"""
    try:
        uuid = UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory_id format")
    
    # TODO: Implement history retrieval
    return []