"""Centralized, environment-based configuration for KESHAV.

Secrets are loaded from environment variables / ``.env`` and are excluded from
any serialized representation so that they can never leak through the API,
logging or system-info endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "KESHAV"
API_VERSION = "1.0.0"
DATA_PIPELINE_VERSION = "0.1.0"

# Field names whose values must never be exposed in any serialized config,
# logs or API response.
PROTECTED_FIELD_NAMES = frozenset(
    {
        "WEATHER_API_KEY",
        "AIR_QUALITY_API_KEY",
        "database_url",
        "DATABASE_URL",
        "secret_key",
        "SECRET_KEY",
    }
)

REDACTED = "[REDACTED]"


class Settings(BaseSettings):
    """Application settings backed by environment variables / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = APP_NAME
    app_env: str = Field(default="development")
    api_version: str = API_VERSION
    log_level: str = Field(default="INFO")

    database_url: str = Field(default="sqlite:///./keshav.db")

    mock_mode: bool = Field(default=True)
    mock_seed: int = Field(default=2026)
    mock_scenario: str = Field(default="NORMAL_DAY")

    # Provider API keys. Empty until real integrations exist.
    weather_api_key: str | None = Field(default=None)
    air_quality_api_key: str | None = Field(default=None)

    # Provider selection (Step 2). Options: "mock" | "openmeteo".
    weather_provider: str = Field(default="mock")
    forecast_provider: str = Field(default="mock")
    air_quality_provider: str = Field(default="mock")
    open_meteo_base_url: str = Field(default="https://api.open-meteo.com/v1")

    # Provider resilience (Step 2): cache TTLs, bounded HTTP timeouts/retries
    # and the default display timezone (IZA; tzdata must be installed).
    provider_cache_ttl_seconds: int = Field(default=1800)  # weather/AQ cache
    forecast_cache_ttl_seconds: int = Field(default=7200)
    provider_timeout_seconds: float = Field(default=10.0)
    provider_max_attempts: int = Field(default=3)
    provider_base_backoff_seconds: float = Field(default=0.5)

    default_timezone: str = Field(default="Asia/Kolkata")

    # Comma-separated list of allowed CORS origins.
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:8000"]
    )

    data_pipeline_version: str = Field(default=DATA_PIPELINE_VERSION)
    model_version: str | None = Field(default=None)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard(cls, origins: List[str]) -> List[str]:
        # allow_credentials is always True; "*" + credentials is invalid CORS
        # and would silently allow any site to read responses.
        if "*" in origins:
            raise ValueError("cors_origins must not contain '*' when credentials are allowed")
        return origins

    @property
    def env(self) -> str:
        return self.app_env

    def safe_dict(self) -> dict:
        """Serializable representation with all secrets redacted.

        Used by ``/api/v1/system/info`` and logging. Never include credentials.
        """
        data: dict = {}
        for name, value in self.model_dump().items():
            if name.upper() in PROTECTED_FIELD_NAMES or "key" in name.lower():
                data[name] = REDACTED if value else ""
            else:
                data[name] = value
        return data

    def redact(self, payload: dict) -> dict:
        """Return a copy of ``payload`` with secrets redacted."""
        out: dict = {}
        for key, value in payload.items():
            if key.upper() in PROTECTED_FIELD_NAMES or "key" in key.lower():
                out[key] = REDACTED if value else ""
            elif isinstance(value, dict):
                out[key] = self.redact(value)
            else:
                out[key] = value
        return out


settings = Settings()