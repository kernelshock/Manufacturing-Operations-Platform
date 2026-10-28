from pydantic import ValidationError
import pytest

from mop.config import Settings


def test_default_settings_are_safe_for_development() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.debug is False


def test_settings_read_mop_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOP_ENVIRONMENT", "test")
    monkeypatch.setenv("MOP_API_PREFIX", "/api/v2/")
    monkeypatch.setenv("MOP_DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.api_prefix == "/api/v2"
    assert settings.debug is True


def test_invalid_api_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(api_prefix="api/v1", _env_file=None)
