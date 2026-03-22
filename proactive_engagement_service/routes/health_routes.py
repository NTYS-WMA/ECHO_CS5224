"""
Health check routes for the Proactive Engagement Service.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Service health check",
    description="Returns the health status of the Proactive Engagement Service.",
)
async def health_check():
    """Basic liveness check."""
    return {"status": "healthy", "service": "proactive-engagement-service"}


@router.get(
    "/ready",
    summary="Service readiness check",
    description="Returns whether the service is ready to accept requests.",
)
async def readiness_check():
    """
    Readiness check verifying that dependent services are reachable.

    TO BE UPDATED: Add actual dependency health checks once deployed.
    """
    return {"status": "ready", "service": "proactive-engagement-service"}
