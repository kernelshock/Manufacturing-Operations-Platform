"""Application configuration boundary."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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

    model_config = SettingsConfigDict(
        env_prefix="MOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
