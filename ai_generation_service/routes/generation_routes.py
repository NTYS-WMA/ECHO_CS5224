"""
API routes for the AI Generation Service.

Exposes three generation endpoints:
1. POST /api/v1/generation/chat-completions  — Chat completion
2. POST /api/v1/generation/summaries         — Summary generation
3. POST /api/v1/generation/proactive-messages — Proactive message generation
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..models.requests import (
    ChatCompletionRequest,
    ProactiveMessageRequest,
    SummaryGenerationRequest,
)
from ..models.responses import (
    ChatCompletionResponse,
    ErrorResponse,
    ProactiveMessageResponse,
    SummaryGenerationResponse,
)
from ..services.generation_service import GenerationError, GenerationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/generation", tags=["Generation"])


def get_generation_service() -> GenerationService:
    """
    Dependency injection placeholder for the GenerationService.

    The actual instance is set during application startup via
    `app.state.generation_service`.

    TO BE UPDATED: Replace with proper DI container if adopted.
    """
    from ..app import get_app_generation_service

    return get_app_generation_service()


# ------------------------------------------------------------------ #
# 1. Chat Completion
# ------------------------------------------------------------------ #


@router.post(
    "/chat-completions",
    response_model=ChatCompletionResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Generation failed after all retries"},
    },
    summary="Generate a chat completion",
    description=(
        "Accepts a conversation message list (including system prompt) and returns "
        "an AI-generated reply. Called by the Conversation Orchestrator Service."
    ),
)
async def chat_completion(
    request: ChatCompletionRequest,
    service: GenerationService = Depends(get_generation_service),
) -> ChatCompletionResponse:
    """Handle chat completion requests from the Conversation Orchestrator."""
    try:
        return await service.chat_completion(request)
    except GenerationError as e:
        logger.error(
            "Chat completion failed for user %s: [%s] %s",
            request.user_id,
            e.error_code,
            str(e),
        )
        raise HTTPException(
            status_code=503 if e.retryable else 500,
            detail=ErrorResponse(
                error_code=e.error_code,
                message=str(e),
                retryable=e.retryable,
                correlation_id=request.correlation_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Unexpected error in chat completion: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                retryable=False,
                correlation_id=request.correlation_id,
            ).model_dump(),
        )


# ------------------------------------------------------------------ #
# 2. Summary Generation
# ------------------------------------------------------------------ #


@router.post(
    "/summaries",
    response_model=SummaryGenerationResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Generation failed after all retries"},
    },
    summary="Generate a conversation summary",
    description=(
        "Accepts a message window reference and generates a compact summary "
        "for memory compaction. Called by the Memory Service."
    ),
)
async def generate_summary(
    request: SummaryGenerationRequest,
    service: GenerationService = Depends(get_generation_service),
) -> SummaryGenerationResponse:
    """Handle summary generation requests from the Memory Service."""
    try:
        return await service.generate_summary(request)
    except GenerationError as e:
        logger.error(
            "Summary generation failed for user %s: [%s] %s",
            request.user_id,
            e.error_code,
            str(e),
        )
        raise HTTPException(
            status_code=503 if e.retryable else 500,
            detail=ErrorResponse(
                error_code=e.error_code,
                message=str(e),
                retryable=e.retryable,
                correlation_id=request.correlation_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Unexpected error in summary generation: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                retryable=False,
                correlation_id=request.correlation_id,
            ).model_dump(),
        )


# ------------------------------------------------------------------ #
# 3. Proactive Message Generation
# ------------------------------------------------------------------ #


@router.post(
    "/proactive-messages",
    response_model=ProactiveMessageResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Generation failed after all retries"},
    },
    summary="Generate a proactive outreach message",
    description=(
        "Accepts relationship context and user preferences, then generates "
        "a personalized check-in message. Called by the Proactive Engagement Service."
    ),
)
async def generate_proactive_message(
    request: ProactiveMessageRequest,
    service: GenerationService = Depends(get_generation_service),
) -> ProactiveMessageResponse:
    """Handle proactive message generation requests from the Proactive Engagement Service."""
    try:
        return await service.generate_proactive_message(request)
    except GenerationError as e:
        logger.error(
            "Proactive message generation failed for user %s: [%s] %s",
            request.user_id,
            e.error_code,
            str(e),
        )
        raise HTTPException(
            status_code=503 if e.retryable else 500,
            detail=ErrorResponse(
                error_code=e.error_code,
                message=str(e),
                retryable=e.retryable,
                correlation_id=request.correlation_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Unexpected error in proactive message generation: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                retryable=False,
                correlation_id=request.correlation_id,
            ).model_dump(),
        )
