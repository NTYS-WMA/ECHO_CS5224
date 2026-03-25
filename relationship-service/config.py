"""Configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── AI Generation Service ─────────────────────────────────────────────────
    ai_generation_service_url: str = "http://localhost:8003"

    # ── DB Manager Service ────────────────────────────────────────────────────
    db_manager_url: str = "http://localhost:18087"

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
