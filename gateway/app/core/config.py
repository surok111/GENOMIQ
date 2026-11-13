from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "GenomIQ API Gateway"
    API_V1_STR: str = "/api"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Временно используем SQLite для локальной разработки (без Docker/Postgres)
    DATABASE_URL: SecretStr = SecretStr("sqlite+aiosqlite:///./genomiq.db")

    # Redis все еще нужен для очередей (пока оставляем как есть)
    REDIS_URL: SecretStr = SecretStr("redis://localhost:6379/0")

    USE_MOCK_AI: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (usable as a FastAPI dependency)."""
    return Settings()


settings: Settings = get_settings()