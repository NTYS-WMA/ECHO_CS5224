"""
Request models for the Proactive Engagement Service.

Includes event payloads consumed from the messaging layer and request
bodies for internal API calls to dependent services.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProactiveScanTriggerEvent(BaseModel):
    """
    Event consumed from topic: proactive.scan.requested

    Published by the platform scheduler to trigger a proactive engagement scan.
    """

    event_id: str = Field(
        ...,
        description="Unique event identifier.",
        examples=["evt-7001"],
    )
    event_type: str = Field(
        default="proactive.scan.requested",
        description="Event type discriminator.",
    )
    schema_version: str = Field(
        default="1.0",
        description="Schema version for forward compatibility.",
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of the trigger.",
    )
    window: Optional[dict] = Field(
        None,
        description="Time window context for the scan.",
        examples=[{"timezone": "Asia/Singapore", "hour": 9}],
    )
    mode: str = Field(
        default="scheduled",
        description="Trigger mode: 'scheduled' or 'manual'.",
        examples=["scheduled"],
    )


class CandidateSearchFilters(BaseModel):
    """Filters for proactive candidate selection."""

    min_days_inactive: int = Field(
        default=3,
        ge=1,
        description="Minimum days of inactivity to qualify as a candidate.",
    )
    min_affinity_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum affinity score to qualify as a candidate.",
    )
    max_batch_size: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum number of candidates to return.",
    )


class TimeContext(BaseModel):
    """Time context for candidate selection."""

    timezone: str = Field(
        ...,
        description="Target timezone for the scan (IANA format).",
        examples=["Asia/Singapore"],
    )
    current_time: str = Field(
        ...,
        description="Current time in ISO 8601 format with timezone offset.",
        examples=["2026-03-12T09:00:00+08:00"],
    )


class CandidateSearchRequest(BaseModel):
    """
    Request body for POST /api/v1/relationships/proactive-candidates/search.

    Sent to: Relationship Service
    """

    filters: CandidateSearchFilters = Field(
        ...,
        description="Candidate selection filters.",
    )
    time_context: TimeContext = Field(
        ...,
        description="Time context for the scan.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
    )


class ManualTriggerRequest(BaseModel):
    """
    Request body for POST /api/v1/proactive/trigger.

    Allows manual triggering of a proactive engagement scan via the API.
    """

    timezone: str = Field(
        default="Asia/Singapore",
        description="Target timezone for the scan.",
    )
    filters: Optional[CandidateSearchFilters] = Field(
        None,
        description="Optional custom filters. Defaults are used if omitted.",
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing.",
    )
