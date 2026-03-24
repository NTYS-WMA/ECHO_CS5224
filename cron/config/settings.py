"""
Configuration settings for the Cron Service v3.0.

All settings can be overridden via environment variables with the
CRON_ prefix.
"""

import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ScheduleEntryConfig(BaseSettings):
    """A single schedule entry loaded from configuration."""

    name: str = Field(..., description="Unique schedule name.")
    cron_expression: Optional[str] = Field(
        None,
        description="5-field cron expression (e.g. '0 3 * * *').",
    )
    interval_seconds: Optional[int] = Field(
        None,
        ge=60,
        description="Fixed interval in seconds (min 60).",
    )
    topic: str = Field(
        ...,
        description="Event topic to publish when schedule fires.",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Static payload to include in the published event.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this schedule is active.",
    )


# Default schedules reflecting the ECHO platform's periodic needs.
DEFAULT_SCHEDULES: List[Dict[str, Any]] = [
    {
        "name": "relationship-decay",
        "cron_expression": "0 3 * * *",
        "topic": "relationship.decay.requested",
        "payload": {},
        "enabled": True,
    },
    {
        "name": "memory-compaction",
        "cron_expression": "0 4 * * 0",
        "topic": "memory.compaction.requested",
        "payload": {},
        "enabled": True,
    },
]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service identity
    SERVICE_NAME: str = Field(
        default="cron-service",
        description="Service name for logging and registration.",
    )
    SERVICE_VERSION: str = Field(
        default="3.0.0",
        description="Service version.",
    )
    HOST: str = Field(
        default="0.0.0.0",
        description="Bind host.",
    )
    PORT: int = Field(
        default=8005,
        description="HTTP port for the service.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level.",
    )

    # Event Publishing (Internal Messaging Layer)
    EVENT_BROKER_URL: str = Field(
        default="http://localhost:9092",
        description="Base URL of the HTTP event broker.",
    )
    EVENT_PUBLISH_TIMEOUT: int = Field(
        default=5,
        description="HTTP timeout for event publish calls (seconds).",
    )
    EVENT_PUBLISH_RETRIES: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Number of retries for failed event publish attempts.",
    )

    # Scheduler tick interval — how often the scheduler checks for due jobs
    TICK_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=5,
        description="Seconds between scheduler tick cycles.",
    )

    # Schedules — JSON string or loaded from default
    SCHEDULES_JSON: str = Field(
        default="",
        description=(
            "JSON array of schedule entries.  "
            "If empty, built-in defaults are used."
        ),
    )

    class Config:
        env_prefix = "CRON_"
        env_file = ".env"
        case_sensitive = True

    def get_schedules(self) -> List[ScheduleEntryConfig]:
        """Parse and return schedule entries from config."""
        raw: List[Dict[str, Any]]
        if self.SCHEDULES_JSON.strip():
            raw = json.loads(self.SCHEDULES_JSON)
        else:
            raw = DEFAULT_SCHEDULES
        return [ScheduleEntryConfig(**entry) for entry in raw]


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
