"""
Health check routes for the AI Generation Service.
"""

from fastapi import APIRouter

from ..config.settings import get_settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Service health check",
    description="Returns the health status of the AI Generation Service.",
)
async def health_check():
    """Basic liveness check."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "ai-generation-service",
        "version": settings.SERVICE_VERSION,
    }


@router.get(
    "/ready",
    summary="Service readiness check",
    description="Returns whether the service is ready to accept requests.",
)
async def readiness_check():
    """
    Readiness check verifying that the primary AI provider is reachable.

    TO BE UPDATED: Add actual provider health check once deployed.
    """
    return {"status": "ready", "service": "ai-generation-service"}
