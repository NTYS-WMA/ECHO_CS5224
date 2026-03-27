"""
Request models for the Cron Service v3.0.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ManualTriggerRequest(BaseModel):
    """Request body for POST /api/v1/scheduler/trigger/{schedule_name}."""

    payload_override: Optional[Dict[str, Any]] = Field(
        None,
        description="Override the schedule's default payload for this trigger.",
    )
