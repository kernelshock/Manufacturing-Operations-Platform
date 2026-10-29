from pydantic import ValidationError
import pytest
from sqlalchemy.engine import make_url

from mop.config import Settings


def _clear_runtime_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "MOP_ENVIRONMENT",
        "MOP_API_PREFIX",
        "MOP_DEBUG",
        "MOP_DATABASE_URL",
        "MOP_DATABASE_HOST",
        "MOP_DATABASE_PORT",
        "MOP_DATABASE_NAME",
        "MOP_DATABASE_USER",
        "MOP_DATABASE_PASSWORD",
        "MOP_SESSION_TTL_MINUTES",
        "MOP_SESSION_COOKIE_SECURE",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_default_settings_are_safe_for_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_environment(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.debug is False
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_settings_read_mop_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_environment(monkeypatch)
    monkeypatch.setenv("MOP_ENVIRONMENT", "test")
    monkeypatch.setenv("MOP_API_PREFIX", "/api/v2/")
    monkeypatch.setenv("MOP_DEBUG", "true")
    monkeypatch.setenv("MOP_DATABASE_URL", "postgresql+psycopg://test:test@db:5432/test")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.api_prefix == "/api/v2"
    assert settings.debug is True
    assert settings.database_url == "postgresql+psycopg://test:test@db:5432/test"


def test_database_components_build_encoded_psycopg_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_environment(monkeypatch)
    password = "Db@Runtime:2026!"
    monkeypatch.setenv("MOP_DATABASE_HOST", "postgres")
    monkeypatch.setenv("MOP_DATABASE_PORT", "5432")
    monkeypatch.setenv("MOP_DATABASE_NAME", "mop")
    monkeypatch.setenv("MOP_DATABASE_USER", "mop")
    monkeypatch.setenv("MOP_DATABASE_PASSWORD", password)

    settings = Settings(_env_file=None)
    parsed = make_url(settings.database_url)

    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.host == "postgres"
    assert parsed.port == 5432
    assert parsed.database == "mop"
    assert parsed.username == "mop"
    assert parsed.password == password
    assert "Db@Runtime:2026!" not in settings.database_url


def test_incomplete_database_components_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_runtime_environment(monkeypatch)
    monkeypatch.setenv("MOP_DATABASE_HOST", "postgres")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_api_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(api_prefix="api/v1", _env_file=None)
