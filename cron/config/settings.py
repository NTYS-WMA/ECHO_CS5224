"""
Configuration settings for the Cron Service v2.0.

All settings can be overridden via environment variables with the
CRON_ prefix.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service identity
    SERVICE_NAME: str = Field(
        default="cron-service",
        description="Service name for logging and registration.",
    )
    SERVICE_VERSION: str = Field(
        default="2.0.0",
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

    # Database Service (external)
    DATABASE_SERVICE_URL: str = Field(
        default="http://localhost:8010",
        description="Base URL of the Database Service module.",
    )
    DATABASE_SERVICE_TIMEOUT: int = Field(
        default=10,
        description="HTTP timeout for Database Service calls (seconds).",
    )

    # Message Dispatch Hub (external)
    DISPATCH_HUB_URL: str = Field(
        default="http://localhost:8020",
        description="Base URL of the Message Dispatch Hub.",
    )
    DISPATCH_HUB_TIMEOUT: int = Field(
        default=15,
        description="HTTP timeout for Message Dispatch Hub calls (seconds).",
    )

    # Polling Scheduler
    POLL_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=5,
        description="Seconds between polling cycles.",
    )
    MAX_TASKS_PER_POLL: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum tasks to process per poll cycle.",
    )
    SCHEDULER_ENABLED: bool = Field(
        default=True,
        description="Whether to start the background polling scheduler on boot.",
    )

    # Event Publishing (Internal Messaging Layer)
    EVENT_BROKER_URL: str = Field(
        default="http://localhost:9092",
        description="Base URL of the HTTP event broker.",
    )
    EVENT_PUBLISH_ENABLED: bool = Field(
        default=True,
        description="Whether to publish lifecycle events.",
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

    # HTTP client settings
    HTTP_TIMEOUT_SECONDS: int = Field(
        default=15,
        description="Default HTTP client timeout.",
    )

    class Config:
        env_prefix = "CRON_"
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
