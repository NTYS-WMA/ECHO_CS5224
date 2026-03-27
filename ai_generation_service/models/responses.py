"""
Response models for AI Generation Service endpoints.

These Pydantic models define the contract for all outbound API responses.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class OutputItem(BaseModel):
    """A single output segment in the generation response."""

    type: str = Field(
        ...,
        description="Output type, currently always 'text'.",
        examples=["text"],
    )
    content: str = Field(
        ...,
        description="Generated text content.",
        examples=["Hey Alice, nice to hear from you."],
    )


class UsageInfo(BaseModel):
    """Token usage statistics for the generation request."""

    input_tokens: int = Field(
        ...,
        ge=0,
        description="Number of input tokens consumed.",
        examples=[812],
    )
    output_tokens: int = Field(
        ...,
        ge=0,
        description="Number of output tokens generated.",
        examples=[39],
    )


# ------------------------------------------------------------------ #
# Unified Generation Response (for /execute endpoint)
# ------------------------------------------------------------------ #


class GenerationResponse(BaseModel):
    """
    Response body for POST /api/v1/generation/execute.

    This is the primary response model for the unified generation endpoint.
    """

    response_id: str = Field(
        ...,
        description="Unique identifier for this generation response.",
        examples=["gen-445"],
    )
    template_id: str = Field(
        ...,
        description="The template ID that was used for generation.",
        examples=["tpl_chat_completion"],
    )
    output: List[OutputItem] = Field(
        ...,
        description="List of generated output segments.",
    )
    model: str = Field(
        ...,
        description="Model identifier used for generation.",
        examples=["claude-sonnet"],
    )
    usage: UsageInfo = Field(
        ...,
        description="Token usage statistics.",
    )


# ------------------------------------------------------------------ #
# Embedding Response
# ------------------------------------------------------------------ #


class EmbeddingResponse(BaseModel):
    """
    Response body for POST /api/v1/generation/embeddings.

    Returns the embedding vector and usage metadata.
    """

    response_id: str = Field(
        ...,
        description="Unique identifier for this embedding response.",
        examples=["gen-emb-445"],
    )
    embedding: List[float] = Field(
        ...,
        description="The embedding vector.",
    )
    dimension: int = Field(
        ...,
        ge=1,
        description="Dimensionality of the embedding vector.",
        examples=[1024],
    )
    model: str = Field(
        ...,
        description="Model identifier used for embedding.",
        examples=["amazon.titan-embed-text-v2:0"],
    )
    usage: UsageInfo = Field(
        ...,
        description="Token usage statistics.",
    )


# ------------------------------------------------------------------ #
# Legacy Response Models (kept for backward compatibility)
# ------------------------------------------------------------------ #


class ChatCompletionResponse(BaseModel):
    """
    Response body for POST /api/v1/generation/chat-completions.

    Returned to: Conversation Orchestrator Service
    """

    response_id: str = Field(
        ...,
        description="Unique identifier for this generation response.",
        examples=["gen-445"],
    )
    output: List[OutputItem] = Field(
        ...,
        description="List of generated output segments.",
    )
    model: str = Field(
        ...,
        description="Model identifier used for generation.",
        examples=["claude-sonnet"],
    )
    usage: UsageInfo = Field(
        ...,
        description="Token usage statistics.",
    )


class SummaryGenerationResponse(BaseModel):
    """
    Response body for POST /api/v1/generation/summaries.

    Returned to: Memory Service
    """

    content: str = Field(
        ...,
        description="Generated summary text.",
        examples=["User values supportive check-ins and tends to exercise in the evening."],
    )
    model: str = Field(
        ...,
        description="Model identifier used for generation.",
        examples=["claude-sonnet"],
    )
    usage: UsageInfo = Field(
        ...,
        description="Token usage statistics.",
    )


class ProactiveMessageResponse(BaseModel):
    """
    Response body for POST /api/v1/generation/proactive-messages.

    Returned to: Cron Service
    """

    response_id: str = Field(
        ...,
        description="Unique identifier for this generation response.",
        examples=["gen-980"],
    )
    output: List[OutputItem] = Field(
        ...,
        description="List of generated output segments.",
    )
    model: str = Field(
        ...,
        description="Model identifier used for generation.",
        examples=["claude-sonnet"],
    )
    usage: Optional[UsageInfo] = Field(
        None,
        description="Token usage statistics (may be omitted in some responses).",
    )


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error_code: str = Field(
        ...,
        description="Machine-readable error code.",
        examples=["PROVIDER_TIMEOUT"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description.",
        examples=["AI provider did not respond within the configured timeout."],
    )
    retryable: bool = Field(
        ...,
        description="Whether the caller should retry this request.",
        examples=[True],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID from the original request.",
    )
