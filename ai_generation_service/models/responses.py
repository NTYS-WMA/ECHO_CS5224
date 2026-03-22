"""
Response models for AI Generation Service endpoints.

These Pydantic models define the contract for all outbound API responses.
"""

from typing import List, Optional

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

    Returned to: Proactive Engagement Service
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
