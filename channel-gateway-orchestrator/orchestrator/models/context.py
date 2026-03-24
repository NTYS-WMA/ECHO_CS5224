"""
Models used internally by the Conversation Orchestrator to hold assembled context.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """Profile + preferences resolved for the current user."""
    user_id: str
    display_name: str = "User"
    language: str = "en"
    timezone: str = "UTC"
    tone: str = "friendly"
    interests: list[str] = Field(default_factory=list)
    onboarding_state: str = "completed"
    consent_personalization: bool = True


class RelationshipContext(BaseModel):
    """Relationship state resolved for the current user."""
    affinity_score: float = 0.5
    tier: str = "friend"
    interaction_count: int = 0
    days_inactive: int = 0


class MemoryContext(BaseModel):
    """Assembled short-term and long-term memory for prompt building."""
    short_term_messages: list[dict[str, Any]] = Field(default_factory=list)
    long_term_memories: list[dict[str, Any]] = Field(default_factory=list)


class OrchestrationContext(BaseModel):
    """
    Full context assembled by the orchestrator before calling AI generation.

    This gets translated into the system prompt + message history for the LLM.
    """
    user: UserContext
    relationship: RelationshipContext
    memory: MemoryContext
    conversation_id: str
    correlation_id: str
    current_message: str
