"""Application configuration boundary."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal[
    "development",
    "test",
    "simulation",
    "shadow",
    "parallel",
    "production",
]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env."""

    app_name: str = "Manufacturing Operations Platform"
    environment: Environment = "development"
    api_prefix: str = "/api/v1"
    debug: bool = False
    database_url: str = (
        "postgresql+psycopg://mop:mop_dev_only@127.0.0.1:5432/mop?connect_timeout=2"
    )
    session_cookie_name: str = "mop_session"
    session_ttl_minutes: int = 480
    session_cookie_secure: bool = False

    model_config = SettingsConfigDict(
        env_prefix="MOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def enforce_secure_cookie_for_production_stages(self) -> "Settings":
        if self.environment in {"shadow", "parallel", "production"}:
            self.session_cookie_secure = True
        return self

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        prefix = value.strip()
        if not prefix.startswith("/"):
            raise ValueError("api_prefix must start with '/'")
        if prefix != "/" and prefix.endswith("/"):
            prefix = prefix.rstrip("/")
        return prefix


@lru_cache
def get_settings() -> Settings:
    """Return process-level cached settings."""

    return Settings()
