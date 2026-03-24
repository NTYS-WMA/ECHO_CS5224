"""
Configuration settings for the AI Generation Service.

Loads configuration from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """AI Generation Service configuration."""

    # Service identity
    SERVICE_NAME: str = "ai-generation-service"
    SERVICE_VERSION: str = "2.1.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8003

    # Primary AI provider (Amazon Bedrock / Claude)
    PRIMARY_PROVIDER: str = "bedrock"
    BEDROCK_REGION: str = "ap-southeast-1"
    BEDROCK_MODEL_ID: str = "anthropic.claude-sonnet-4-20250514"
    BEDROCK_MAX_RETRIES: int = 2
    BEDROCK_TIMEOUT_SECONDS: int = 30

    # Fallback AI provider (optional, e.g., OpenAI-compatible endpoint)
    FALLBACK_PROVIDER: Optional[str] = None
    FALLBACK_API_BASE_URL: Optional[str] = None
    FALLBACK_API_KEY: Optional[str] = None
    FALLBACK_MODEL_ID: Optional[str] = None

    # Default generation parameters (service-level fallbacks)
    # These are used only when neither the caller nor the template provides values.
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_MAX_TOKENS: int = 512
    SUMMARY_TEMPERATURE: float = 0.3
    SUMMARY_MAX_TOKENS: int = 300
    PROACTIVE_TEMPERATURE: float = 0.8
    PROACTIVE_MAX_TOKENS: int = 150

    # Prompt template management
    # Templates directory path is auto-resolved relative to the package,
    # but can be overridden for custom deployments.
    TEMPLATES_DIR_OVERRIDE: Optional[str] = None

    # Event broker configuration
    # TO BE UPDATED: Actual broker implementation details (e.g., Redis Streams, RabbitMQ, or local queue)
    EVENT_BROKER_URL: str = "redis://localhost:6379/0"
    EVENT_PUBLISH_ENABLED: bool = True

    # Conversation Persistence Store
    # TO BE UPDATED: Actual endpoint once Conversation Persistence Store is deployed
    CONVERSATION_STORE_BASE_URL: str = "http://localhost:8010"

    # Retry and fallback policy
    MAX_RETRY_ATTEMPTS: int = 2
    RETRY_BACKOFF_BASE_SECONDS: float = 0.5
    FALLBACK_ON_TIMEOUT: bool = True
    FALLBACK_ON_PROVIDER_ERROR: bool = True

    # Observability
    LOG_LEVEL: str = "INFO"
    ENABLE_TELEMETRY_EVENTS: bool = True

    class Config:
        env_prefix = "AI_GEN_"
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
