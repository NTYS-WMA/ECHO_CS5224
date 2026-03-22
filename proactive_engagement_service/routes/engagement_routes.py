"""
API routes for the Proactive Engagement Service.

Exposes endpoints for:
1. POST /api/v1/proactive/trigger — Manual scan trigger
2. GET  /api/v1/proactive/status  — Service status and last scan info
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..models.requests import ManualTriggerRequest
from ..models.responses import ScanStatusResponse
from ..services.engagement_service import ProactiveEngagementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/proactive", tags=["Proactive Engagement"])


def get_engagement_service() -> ProactiveEngagementService:
    """
    Dependency injection placeholder for the ProactiveEngagementService.

    The actual instance is set during application startup via
    `app.state.engagement_service`.

    TO BE UPDATED: Replace with proper DI container if adopted.
    """
    from ..app import get_app_engagement_service

    return get_app_engagement_service()


# ------------------------------------------------------------------ #
# 1. Manual Scan Trigger
# ------------------------------------------------------------------ #


@router.post(
    "/trigger",
    response_model=ScanStatusResponse,
    summary="Manually trigger a proactive engagement scan",
    description=(
        "Triggers a proactive engagement scan on demand. This endpoint is "
        "intended for operational use and testing. In production, scans are "
        "triggered by the platform scheduler via the proactive.scan.requested event."
    ),
)
async def trigger_scan(
    request: ManualTriggerRequest,
    service: ProactiveEngagementService = Depends(get_engagement_service),
) -> ScanStatusResponse:
    """Handle manual proactive scan trigger requests."""
    try:
        return await service.handle_manual_trigger(request)
    except Exception as e:
        logger.exception("Unexpected error in manual scan trigger: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": str(e)},
        )


# ------------------------------------------------------------------ #
# 2. Service Status
# ------------------------------------------------------------------ #


@router.get(
    "/status",
    summary="Get proactive engagement service status",
    description="Returns the current status of the Proactive Engagement Service.",
)
async def get_status():
    """Return service status and basic operational info."""
    return {
        "service": "proactive-engagement-service",
        "status": "running",
        "scan_mode": "event-driven + manual",
        "topics_consumed": ["proactive.scan.requested"],
        "topics_published": ["conversation.outbound", "proactive.dispatch.completed"],
    }
