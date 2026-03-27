"""
API routes for the AI Generation Service.

Exposes two primary endpoints:

1. POST /api/v1/generation/execute     — Template-based text generation
2. POST /api/v1/generation/embeddings  — Text embedding
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..models.requests import (
    EmbeddingRequest,
    TemplateGenerationRequest,
)
from ..models.responses import (
    EmbeddingResponse,
    ErrorResponse,
    GenerationResponse,
)
from ..services.generation_service import GenerationError, GenerationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/generation", tags=["Generation"])


def get_generation_service() -> GenerationService:
    """
    Dependency injection placeholder for the GenerationService.

    The actual instance is set during application startup via
    `app.get_app_generation_service()`.
    """
    from ..app import get_app_generation_service

    return get_app_generation_service()


def _handle_generation_error(e: GenerationError, correlation_id=None):
    """Map a GenerationError to an appropriate HTTP exception."""
    status_code = 503 if e.retryable else 500
    if e.error_code == "TEMPLATE_RENDER_ERROR":
        status_code = 400
    raise HTTPException(
        status_code=status_code,
        detail=ErrorResponse(
            error_code=e.error_code,
            message=str(e),
            retryable=e.retryable,
            correlation_id=correlation_id,
        ).model_dump(),
    )


def _handle_unexpected_error(e: Exception, correlation_id=None):
    """Map an unexpected error to a 500 HTTP exception."""
    logger.exception("Unexpected error: %s", str(e))
    raise HTTPException(
        status_code=500,
        detail=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            retryable=False,
            correlation_id=correlation_id,
        ).model_dump(),
    )


# ------------------------------------------------------------------ #
# 1. Template-Based Generation
# ------------------------------------------------------------------ #


@router.post(
    "/execute",
    response_model=GenerationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Template not found or render error"},
        500: {"model": ErrorResponse, "description": "Generation failed after all retries"},
        503: {"model": ErrorResponse, "description": "Provider timeout (retryable)"},
    },
    summary="Execute a template-based generation",
    description=(
        "Primary generation endpoint. Accepts a template_id and variables "
        "(or messages for multi-turn chat). The AI service renders the prompt "
        "from the template and executes it against the configured AI provider. "
        "Business callers should use this endpoint for all new integrations."
    ),
)
async def execute_generation(
    request: TemplateGenerationRequest,
    service: GenerationService = Depends(get_generation_service),
) -> GenerationResponse:
    """Execute a template-based generation request."""
    try:
        return await service.execute(request)
    except GenerationError as e:
        logger.error(
            "Generation failed for user %s template %s: [%s] %s",
            request.user_id,
            request.template_id,
            e.error_code,
            str(e),
        )
        _handle_generation_error(e, request.correlation_id)
    except Exception as e:
        _handle_unexpected_error(e, request.correlation_id)


# ------------------------------------------------------------------ #
# 2. Embedding
# ------------------------------------------------------------------ #


@router.post(
    "/embeddings",
    response_model=EmbeddingResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Embedding failed after all retries"},
        503: {"model": ErrorResponse, "description": "Provider timeout (retryable)"},
    },
    summary="Generate a text embedding",
    description=(
        "Generate a vector embedding for the given input text. Uses the "
        "configured embedding model (e.g., Amazon Titan Embeddings v2) to "
        "produce a dense vector representation suitable for semantic search, "
        "similarity matching, and retrieval-augmented generation (RAG)."
    ),
)
async def generate_embedding(
    request: EmbeddingRequest,
    service: GenerationService = Depends(get_generation_service),
) -> EmbeddingResponse:
    """Generate a text embedding."""
    try:
        return await service.embed(request)
    except GenerationError as e:
        logger.error(
            "Embedding failed for user %s: [%s] %s",
            request.user_id,
            e.error_code,
            str(e),
        )
        _handle_generation_error(e, request.correlation_id)
    except Exception as e:
        _handle_unexpected_error(e, request.correlation_id)
