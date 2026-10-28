from pydantic import ValidationError
import pytest

from mop.config import Settings


def test_default_settings_are_safe_for_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in (
        "MOP_ENVIRONMENT",
        "MOP_API_PREFIX",
        "MOP_DEBUG",
        "MOP_DATABASE_URL",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.debug is False
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_settings_read_mop_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOP_ENVIRONMENT", "test")
    monkeypatch.setenv("MOP_API_PREFIX", "/api/v2/")
    monkeypatch.setenv("MOP_DEBUG", "true")
    monkeypatch.setenv("MOP_DATABASE_URL", "postgresql+psycopg://test:test@db:5432/test")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.api_prefix == "/api/v2"
    assert settings.debug is True
    assert settings.database_url == "postgresql+psycopg://test:test@db:5432/test"


def test_invalid_api_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(api_prefix="api/v1", _env_file=None)
