"""Configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── AI Generation Service ─────────────────────────────────────────────────
    ai_generation_service_url: str = "http://ai-generation-service:8003"

    # ── PostgreSQL (shared DB) ────────────────────────────────────────────────
    database_url: str        # asyncpg — e.g. postgresql+asyncpg://user:pass@host/db
    database_sync_url: str = ""  # psycopg2 for Alembic (optional)

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    port: int = 18089

    # ── Relationship scoring (0–1 scale) ──────────────────────────────────────
    rel_score_acquaintance_max: float = 0.30
    rel_score_friend_max: float = 0.60
    rel_score_close_friend_max: float = 0.80


@lru_cache
def get_settings() -> Settings:
    return Settings()
