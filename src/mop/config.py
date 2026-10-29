"""Application configuration boundary."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

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

    # Direct URL remains available for manual/local development and CI.
    # No password is embedded in source control.
    database_url: str = (
        "postgresql+psycopg://mop@127.0.0.1:5432/mop?connect_timeout=2"
    )

    # Container/runtime deployments may provide discrete components so
    # credentials are encoded safely instead of interpolated into a URI.
    database_host: str | None = None
    database_port: int = 5432
    database_name: str | None = None
    database_user: str | None = None
    database_password: SecretStr | None = None

    session_cookie_name: str = "mop_session"
    session_ttl_minutes: int = 480
    session_cookie_secure: bool = False
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    model_config = SettingsConfigDict(
        env_prefix="MOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def build_database_url_from_components(self) -> "Settings":
        supplied = {
            "database_host": self.database_host,
            "database_name": self.database_name,
            "database_user": self.database_user,
            "database_password": self.database_password,
        }
        if not any(value is not None for value in supplied.values()):
            return self

        missing = [name for name, value in supplied.items() if value is None]
        if missing:
            raise ValueError(
                "database component configuration is incomplete: "
                + ", ".join(sorted(missing))
            )

        assert self.database_host is not None
        assert self.database_name is not None
        assert self.database_user is not None
        assert self.database_password is not None

        self.database_url = URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)
        return self

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

    @field_validator("login_max_failures", "login_lockout_minutes")
    @classmethod
    def validate_positive_security_integer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("security thresholds must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return process-level cached settings."""

    return Settings()
