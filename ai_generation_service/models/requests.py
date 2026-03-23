"""
Request models for AI Generation Service endpoints.

These Pydantic models define the contract for all inbound API requests.

The service supports two invocation patterns:
1. **Template-based (recommended)**: Caller specifies a template_id and provides
   variables. The AI service renders the prompt from the template.
2. **Direct messages (chat-only)**: Caller provides a full message list including
   system prompt. Used for multi-turn chat where the business layer has already
   assembled the conversation.

Both patterns go through the same AI execution engine (retry, fallback, telemetry).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Shared Sub-Models
# ------------------------------------------------------------------ #


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
    """
    Optional generation hyperparameters supplied by the caller.

    If omitted, the template's defaults are used. If the template has no
    defaults, the service-level defaults apply.
    """

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


# ------------------------------------------------------------------ #
# Unified Template-Based Generation Request
# ------------------------------------------------------------------ #


class TemplateGenerationRequest(BaseModel):
    """
    Request body for POST /api/v1/generation/execute.

    This is the **primary** generation interface. Business callers specify
    a template_id and provide variable values. The AI service renders the
    prompt from the template and executes it.

    Source: Any business service (Conversation Orchestrator, Memory Service,
    Proactive Engagement Service, etc.)
    """

    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation identifier for context tracking (optional).",
        examples=["telegram-chat-123456789"],
    )
    template_id: str = Field(
        ...,
        description="The prompt template ID to use for generation.",
        examples=["tpl_chat_completion", "tpl_proactive_outreach"],
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Variable values to substitute into the template. "
            "Must satisfy the template's variable schema."
        ),
        examples=[{"context_block": "Relationship tier: close_friend\nDays inactive: 3"}],
    )
    messages: Optional[List[MessageItem]] = Field(
        None,
        description=(
            "Optional conversation message list for multi-turn chat templates. "
            "When provided, the template's system prompt is merged with the "
            "message list instead of using the user_prompt_template."
        ),
    )
    generation_config: Optional[GenerationConfig] = Field(
        None,
        description=(
            "Optional generation hyperparameters. Overrides the template's "
            "defaults if provided."
        ),
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
        examples=["evt-001"],
    )


# ------------------------------------------------------------------ #
# Legacy Endpoint Models (kept for backward compatibility)
# ------------------------------------------------------------------ #


class ChatCompletionRequest(BaseModel):
    """
    Request body for POST /api/v1/generation/chat-completions.

    Source: Conversation Orchestrator Service

    NOTE: This is a legacy endpoint. New callers should use
    POST /api/v1/generation/execute with template_id instead.
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
    template_id: Optional[str] = Field(
        None,
        description=(
            "Optional template ID. If provided, the template's system prompt "
            "is merged with the caller's messages. If omitted, the default "
            "chat_completion template is used."
        ),
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

    NOTE: This is a legacy endpoint. New callers should use
    POST /api/v1/generation/execute with template_id instead.
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
    template_id: Optional[str] = Field(
        None,
        description=(
            "Optional template ID. If omitted, the default "
            "memory_compaction template is used."
        ),
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

    NOTE: This is a legacy endpoint. New callers should use
    POST /api/v1/generation/execute with template_id instead.
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
    template_id: Optional[str] = Field(
        None,
        description=(
            "Optional template ID. If omitted, the default "
            "proactive_outreach template is used."
        ),
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
        examples=["evt-6001"],
    )
