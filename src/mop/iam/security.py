"""Password and opaque-session token cryptography."""

from hashlib import sha256

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash(
    "mop-authentication-timing-equalizer-never-a-valid-password"
)


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return _password_hash.verify(password, encoded_hash)


def verify_password_or_dummy(password: str, encoded_hash: str | None) -> bool:
    """Perform one Argon2 verification even when the username does not exist."""

    return _password_hash.verify(
        password,
        encoded_hash if encoded_hash is not None else _dummy_password_hash,
    )


def hash_session_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
