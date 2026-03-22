"""
Domain models for internal business logic in the Proactive Engagement Service.

These models represent intermediate data structures used during the
candidate evaluation and dispatch pipeline.
"""

from typing import Optional

from pydantic import BaseModel, Field


class UserQuietHours(BaseModel):
    """User's quiet hours preferences."""

    start: str = Field(
        ...,
        description="Quiet hours start time (HH:MM format).",
        examples=["22:00"],
    )
    end: str = Field(
        ...,
        description="Quiet hours end time (HH:MM format).",
        examples=["07:00"],
    )


class UserProfileConsent(BaseModel):
    """Subset of user profile relevant to proactive engagement eligibility."""

    user_id: str = Field(..., description="Internal user identifier.")
    proactive_messaging_consent: bool = Field(
        ...,
        description="Whether the user has consented to proactive messaging.",
    )
    quiet_hours: Optional[UserQuietHours] = Field(
        None,
        description="User's quiet hours preferences.",
    )
    timezone: Optional[str] = Field(
        None,
        description="User timezone (IANA format).",
    )


class EligibilityCheckResult(BaseModel):
    """Result of the eligibility check for a single candidate."""

    user_id: str = Field(..., description="Internal user identifier.")
    eligible: bool = Field(
        ...,
        description="Whether the user is eligible for proactive messaging.",
    )
    skip_reason: Optional[str] = Field(
        None,
        description="Reason for ineligibility, if applicable.",
        examples=["consent_denied", "quiet_hours", "profile_unavailable"],
    )


class ProactiveCandidate(BaseModel):
    """
    Enriched candidate with all data needed for proactive message generation.

    Combines candidate info from Relationship Service with profile/consent
    data from User Profile Service.
    """

    user_id: str = Field(..., description="Internal user identifier.")
    days_inactive: int = Field(..., description="Days since last interaction.")
    affinity_score: float = Field(..., description="Current affinity score.")
    tier: str = Field(
        ...,
        description="Relationship tier derived from affinity score.",
    )
    timezone: Optional[str] = Field(None, description="User timezone.")
    recent_summary: Optional[str] = Field(
        None,
        description="Recent memory summary for personalization.",
    )
    channel: Optional[str] = Field(
        None,
        description="User's primary channel.",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="User's conversation ID for outbound delivery.",
    )
