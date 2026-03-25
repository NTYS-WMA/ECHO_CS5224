"""
Relationship API — REST endpoints exposed by the Relationship Service.

  GET   /api/v1/relationships/{user_id}/context   ← orchestrator
  PATCH /api/v1/relationships/{user_id}/score     ← admin
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

import managers.relationship_manager as relationship_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/relationships", tags=["relationships"])


# ─── Response / Request models ────────────────────────────────────────────────


class DecayState(BaseModel):
    last_decay_at: Optional[str]
    days_inactive: int


class RelationshipContextResponse(BaseModel):
    user_id: str
    affinity_score: float
    tier: str
    interaction_count: int
    last_interaction_at: Optional[str]
    decay_state: DecayState
    updated_at: Optional[str]


class ScoreUpdateRequest(BaseModel):
    score: float

    @field_validator("score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
        return v


class ScoreUpdateResponse(BaseModel):
    user_id: str
    previous_score: float
    new_score: float
    previous_tier: str
    new_tier: str


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/{user_id}/context", response_model=RelationshipContextResponse)
async def get_relationship_context(user_id: str):
    """
    Return relationship context for a user.
    Called by the orchestrator to personalise the system prompt.
    Returns 404 if the user has no relationship record.
    """
    context = await relationship_manager.get_relationship_context(user_id)
    if context is None:
        raise HTTPException(status_code=404, detail=f"No relationship record for user {user_id}")
    return context


@router.patch("/{user_id}/score", response_model=ScoreUpdateResponse)
async def update_relationship_score(user_id: str, body: ScoreUpdateRequest):
    """
    Directly set the affinity score for a user.
    Admin / testing use only. Score must be 0.0–1.0.
    Returns 404 if the user has no relationship record.
    """
    result = await relationship_manager.set_relationship_score(user_id, body.score)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No relationship record for user {user_id}")
    return result
