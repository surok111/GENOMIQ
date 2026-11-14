from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_RATE_LIMIT_KEY = "default"


class RateLimitRule(BaseModel):
    """Token bucket parameters for one tenant plan."""

    model_config = ConfigDict(frozen=True)

    capacity: int = Field(gt=0, description="Bucket size (maximum burst).")
    refill_rate: float = Field(gt=0, description="Tokens added per second.")


def _default_rate_limits() -> dict[str, RateLimitRule]:
    return {
        "api_key_lab_a": RateLimitRule(capacity=100, refill_rate=50.0),
        "api_key_lab_b": RateLimitRule(capacity=20, refill_rate=10.0),
        DEFAULT_RATE_LIMIT_KEY: RateLimitRule(capacity=10, refill_rate=5.0),
    }


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

    # Connection strings usually embed credentials, so they are SecretStr
    # to keep them out of repr()/logs. Use .get_secret_value() to read them.
    DATABASE_URL: SecretStr = SecretStr("sqlite+aiosqlite:///./genomiq.db")
    REDIS_URL: SecretStr = SecretStr("redis://localhost:6379/0")

    USE_MOCK_AI: bool = True

    # Base URL of an OTLP/HTTP collector. Used when ENVIRONMENT is not development.
    # Paths /v1/traces and /v1/metrics are appended when missing.
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"

    # Keys are API keys (X-API-Key header values); "default" applies to everyone else.
    # Can be overridden with a JSON-encoded RATE_LIMITS env var.
    RATE_LIMITS: dict[str, RateLimitRule] = Field(default_factory=_default_rate_limits)

    @field_validator("RATE_LIMITS")
    @classmethod
    def _require_default_rule(
        cls, value: dict[str, RateLimitRule]
    ) -> dict[str, RateLimitRule]:
        if DEFAULT_RATE_LIMIT_KEY not in value:
            raise ValueError(f'RATE_LIMITS must define a "{DEFAULT_RATE_LIMIT_KEY}" entry')
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (usable as a FastAPI dependency)."""
    return Settings()


settings: Settings = get_settings()
