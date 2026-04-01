"""
Configuration settings for the Cron Service v4.0.

All settings can be overridden via environment variables with the
CRON_ prefix.
"""

import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ScheduleEntryConfig(BaseSettings):
    """A single built-in schedule entry loaded from configuration."""

    name: str = Field(..., description="Unique schedule name.")
    cron_expression: Optional[str] = Field(
        None, description="5-field cron expression."
    )
    interval_seconds: Optional[int] = Field(None, ge=60)
    topic: str = Field(..., description="Event topic to publish.")
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = Field(default=True)


# Default built-in schedules (registered into DB on first startup)
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
    SERVICE_NAME: str = Field(default="cron-service")
    SERVICE_VERSION: str = Field(default="4.0.0")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8005)
    LOG_LEVEL: str = Field(default="INFO")

    # DB Manager — the cron service talks to db-manager for persistence
    DB_MANAGER_URL: str = Field(
        default="http://localhost:18087",
        description="Base URL of the DB Manager service.",
    )
    DB_MANAGER_TIMEOUT: int = Field(
        default=10,
        description="HTTP timeout for DB Manager calls (seconds).",
    )
    DB_MANAGER_API_KEY: str = Field(
        default="",
        description="API key for DB Manager (if AUTH_ENABLED).",
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
        default=2, ge=0, le=5,
        description="Retries for failed event publish attempts.",
    )

    # Scheduler tick interval
    TICK_INTERVAL_SECONDS: int = Field(
        default=30, ge=5,
        description="Seconds between scheduler tick cycles.",
    )

    # Built-in schedules — JSON string or loaded from default
    SCHEDULES_JSON: str = Field(
        default="",
        description="JSON array of built-in schedule entries.",
    )

    # Whether to auto-register built-in schedules into DB on startup
    AUTO_REGISTER_DEFAULTS: bool = Field(
        default=True,
        description="Auto-register default schedules into DB on startup.",
    )

    class Config:
        env_prefix = "CRON_"
        env_file = ".env"
        case_sensitive = True

    def get_schedules(self) -> List[ScheduleEntryConfig]:
        """Parse and return built-in schedule entries from config."""
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
