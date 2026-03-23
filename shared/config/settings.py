"""
Central configuration loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application-wide settings. Values come from env vars or .env file."""

    #Telegram
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token")

    #Service URLs
    memory_service_url: str = Field(default="http://localhost:18088")
    user_profile_service_url: str = Field(default="http://localhost:8001")
    relationship_service_url: str = Field(default="http://localhost:8002")
    ai_generation_service_url: str = Field(default="http://localhost:8003")
    conversation_store_url: str = Field(default="http://localhost:8004")

    #App
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    mock_services: bool = Field(default=True, description="Use mock clients when True")

    #Orchestrator Tuning
    short_term_message_limit: int = Field(default=12)
    long_term_memory_limit: int = Field(default=5)
    summarization_threshold: int = Field(default=50)

    #AI Generation
    ai_temperature: float = Field(default=0.7)
    ai_max_tokens: int = Field(default=200)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton — import this everywhere
settings = Settings()
