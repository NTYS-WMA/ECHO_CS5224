from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="db-manager", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=18087, alias="APP_PORT")
    auto_init_db: bool = Field(default=True, alias="AUTO_INIT_DB")

    database_url: str = Field(alias="DATABASE_URL")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_database: str = Field(alias="MONGODB_DATABASE")
    mongo_profile_collection: str = Field(default="user_additional_profile", alias="MONGO_PROFILE_COLLECTION")


@lru_cache
def get_settings() -> Settings:
    return Settings()

