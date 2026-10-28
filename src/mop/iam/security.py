"""Password and opaque-session token cryptography."""

from hashlib import sha256

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return _password_hash.verify(password, encoded_hash)


def hash_session_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
