"""
Configuration settings for the Proactive Engagement Service.

Loads configuration from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Proactive Engagement Service configuration."""

    # Service identity
    SERVICE_NAME: str = "proactive-engagement-service"
    SERVICE_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8006

    # Dependent service URLs
    # Relationship Service
    RELATIONSHIP_SERVICE_BASE_URL: str = "http://localhost:8004"
    # User Profile Service
    USER_PROFILE_SERVICE_BASE_URL: str = "http://localhost:8002"
    # AI Generation Service
    AI_GENERATION_SERVICE_BASE_URL: str = "http://localhost:8003"
    # Memory Service (for retrieving recent summaries)
    # TO BE UPDATED: Confirm Memory Service URL and endpoint for summary retrieval
    MEMORY_SERVICE_BASE_URL: str = "http://localhost:18088"

    # Event broker configuration
    # TO BE UPDATED: Actual broker implementation details
    EVENT_BROKER_URL: str = "redis://localhost:6379/0"
    EVENT_PUBLISH_ENABLED: bool = True
    EVENT_CONSUME_ENABLED: bool = True

    # Proactive engagement policy defaults
    DEFAULT_MIN_DAYS_INACTIVE: int = 3
    DEFAULT_MIN_AFFINITY_SCORE: float = 0.5
    DEFAULT_MAX_BATCH_SIZE: int = 500
    DEFAULT_QUIET_HOURS_START: str = "22:00"
    DEFAULT_QUIET_HOURS_END: str = "07:00"

    # Proactive message generation defaults
    DEFAULT_PROACTIVE_MAX_TOKENS: int = 120
    DEFAULT_PROACTIVE_TONE: str = "friendly"

    # Concurrency and rate limiting
    MAX_CONCURRENT_DISPATCHES: int = 10
    DISPATCH_RATE_LIMIT_PER_SECOND: float = 5.0

    # HTTP client settings
    HTTP_TIMEOUT_SECONDS: int = 15

    # Observability
    LOG_LEVEL: str = "INFO"
    ENABLE_TELEMETRY_EVENTS: bool = True

    class Config:
        env_prefix = "PROACTIVE_"
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
