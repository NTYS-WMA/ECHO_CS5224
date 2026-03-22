"""
Response models for the Proactive Engagement Service.

Includes responses from dependent services and the service's own API responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class CandidateItem(BaseModel):
    """A single proactive engagement candidate returned by the Relationship Service."""

    user_id: str = Field(
        ...,
        description="Internal user identifier.",
        examples=["usr_9f2a7c41"],
    )
    days_inactive: int = Field(
        ...,
        ge=0,
        description="Number of days since last interaction.",
        examples=[3],
    )
    affinity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Current affinity score.",
        examples=[0.74],
    )


class CandidateSearchResponse(BaseModel):
    """
    Response from POST /api/v1/relationships/proactive-candidates/search.

    Received from: Relationship Service
    """

    candidates: List[CandidateItem] = Field(
        ...,
        description="List of eligible proactive engagement candidates.",
    )


class DispatchResult(BaseModel):
    """Result of a single proactive message dispatch attempt."""

    user_id: str = Field(..., description="Internal user identifier.")
    dispatched: bool = Field(
        ...,
        description="Whether the message was successfully dispatched.",
    )
    skip_reason: Optional[str] = Field(
        None,
        description="Reason for skipping if not dispatched.",
        examples=["consent_denied", "quiet_hours", "generation_failed"],
    )


class ScanStatusResponse(BaseModel):
    """
    Response body for proactive scan status and manual trigger results.
    """

    scan_id: str = Field(
        ...,
        description="Unique scan identifier.",
        examples=["scan-abc123"],
    )
    status: str = Field(
        ...,
        description="Scan status: 'running', 'completed', or 'failed'.",
        examples=["completed"],
    )
    candidates_scanned: int = Field(
        ...,
        ge=0,
        description="Total number of candidates evaluated.",
    )
    messages_dispatched: int = Field(
        ...,
        ge=0,
        description="Number of proactive messages successfully dispatched.",
    )
    messages_skipped: int = Field(
        ...,
        ge=0,
        description="Number of candidates skipped due to policy checks.",
    )
    results: Optional[List[DispatchResult]] = Field(
        None,
        description="Per-candidate dispatch results (included in detailed mode).",
    )
