from mop.config import Settings
from mop.iam.security import hash_password, verify_password


def test_passwords_use_argon2_and_verify() -> None:
    encoded = hash_password("Correct-Horse-Battery-Staple-2026!")

    assert encoded.startswith("$argon2")
    assert "Correct-Horse-Battery-Staple-2026!" not in encoded
    assert verify_password("Correct-Horse-Battery-Staple-2026!", encoded) is True
    assert verify_password("wrong-password", encoded) is False


def test_production_forces_secure_session_cookie() -> None:
    settings = Settings(
        environment="production",
        session_cookie_secure=False,
        _env_file=None,
    )

    assert settings.session_cookie_secure is True
