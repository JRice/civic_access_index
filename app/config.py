from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Civic Access Index"
    app_env: str = "local"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://civic:civic@localhost:5432/civic_access"
    async_database_url: str = "postgresql+asyncpg://civic:civic@localhost:5432/civic_access"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    opensearch_url: str = "http://localhost:9200"

    raw_snapshot_bucket: str = "local-civic-access-raw"
    raw_snapshot_root: str = "local-data/raw-snapshots"
    admin_token: str = Field(default="change-me", repr=False)
    enable_opensearch: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

