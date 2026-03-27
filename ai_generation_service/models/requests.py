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
        examples=[{"user_prompt": "Based on the following context, compose a short check-in message.\n\nRelationship tier: close_friend\nDays inactive: 3"}],
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
# Embedding Request
# ------------------------------------------------------------------ #


class EmbeddingRequest(BaseModel):
    """
    Request body for POST /api/v1/generation/embeddings.

    Generates a vector embedding for the given input text. Used by
    business services for semantic search, similarity matching, and
    retrieval-augmented generation (RAG).

    Source: Any business service (Memory Service, Search Service, etc.)
    """

    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    input: str = Field(
        ...,
        min_length=1,
        description="The text to generate an embedding for.",
        examples=["User enjoys evening workouts and friendly check-ins."],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
        examples=["evt-emb-001"],
    )


