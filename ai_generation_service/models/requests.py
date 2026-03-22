"""
Request models for AI Generation Service endpoints.

These Pydantic models define the contract for all inbound API requests.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class MessageItem(BaseModel):
    """A single message in a conversation turn sequence."""

    role: str = Field(
        ...,
        description="Message role: 'system', 'user', or 'assistant'.",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="Text content of the message.",
        examples=["Hello ECHO"],
    )


class GenerationConfig(BaseModel):
    """Optional generation hyperparameters supplied by the caller."""

    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Higher values produce more creative output.",
    )
    max_tokens: Optional[int] = Field(
        None,
        ge=1,
        le=4096,
        description="Maximum number of tokens to generate.",
    )
    top_p: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter.",
    )
    stop_sequences: Optional[List[str]] = Field(
        None,
        description="Sequences that will cause the model to stop generating.",
    )


class ChatCompletionRequest(BaseModel):
    """
    Request body for POST /api/v1/generation/chat-completions.

    Source: Conversation Orchestrator Service
    """

    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    conversation_id: str = Field(
        ...,
        description="Conversation identifier for context tracking.",
        examples=["telegram-chat-123456789"],
    )
    messages: List[MessageItem] = Field(
        ...,
        min_length=1,
        description="Ordered list of conversation messages including system prompt.",
    )
    generation_config: Optional[GenerationConfig] = Field(
        None,
        description="Optional generation hyperparameters. Defaults are applied if omitted.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
        examples=["evt-001"],
    )


class MessagesWindow(BaseModel):
    """Defines the range of messages to summarize."""

    from_message_id: str = Field(
        ...,
        description="Starting message ID of the window (inclusive).",
        examples=["msg-601"],
    )
    to_message_id: str = Field(
        ...,
        description="Ending message ID of the window (inclusive).",
        examples=["msg-645"],
    )


class SummaryGenerationRequest(BaseModel):
    """
    Request body for POST /api/v1/generation/summaries.

    Source: Memory Service
    """

    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    conversation_id: str = Field(
        ...,
        description="Conversation identifier.",
        examples=["telegram-chat-123456789"],
    )
    messages_window: MessagesWindow = Field(
        ...,
        description="Range of messages to summarize.",
    )
    summary_type: str = Field(
        ...,
        description="Type of summary to generate.",
        examples=["memory_compaction"],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
        examples=["evt-022"],
    )


class RelationshipContext(BaseModel):
    """Relationship state provided for proactive message generation."""

    tier: str = Field(
        ...,
        description="Relationship tier: acquaintance, friend, close_friend, or best_friend.",
        examples=["close_friend"],
    )
    affinity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Affinity score on a 0-1 scale.",
        examples=[0.74],
    )
    days_inactive: int = Field(
        ...,
        ge=0,
        description="Number of days since last user interaction.",
        examples=[3],
    )


class ProactiveContext(BaseModel):
    """Contextual information for proactive message personalization."""

    recent_summary: Optional[str] = Field(
        None,
        description="Recent memory summary for the user.",
        examples=["User enjoys evening workouts and friendly check-ins"],
    )
    timezone: Optional[str] = Field(
        None,
        description="User timezone for time-aware message generation.",
        examples=["Asia/Singapore"],
    )


class ProactiveConstraints(BaseModel):
    """Constraints for proactive message generation."""

    max_tokens: Optional[int] = Field(
        120,
        ge=1,
        le=500,
        description="Maximum tokens for the generated message.",
    )
    tone: Optional[str] = Field(
        "friendly",
        description="Desired tone of the proactive message.",
        examples=["friendly", "warm", "casual"],
    )


class ProactiveMessageRequest(BaseModel):
    """
    Request body for POST /api/v1/generation/proactive-messages.

    Source: Proactive Engagement Service
    """

    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    relationship: RelationshipContext = Field(
        ...,
        description="Current relationship state with the user.",
    )
    context: Optional[ProactiveContext] = Field(
        None,
        description="Contextual information for personalization.",
    )
    constraints: Optional[ProactiveConstraints] = Field(
        None,
        description="Generation constraints for the proactive message.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
        examples=["evt-6001"],
    )
