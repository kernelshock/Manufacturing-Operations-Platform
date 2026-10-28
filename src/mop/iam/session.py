"""Opaque server-side web session lifecycle."""

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from mop.iam.models import AuthSession, User
from mop.iam.security import hash_session_token


class SessionService:
    def __init__(self, session: Session, ttl_minutes: int) -> None:
        self.session = session
        self.ttl_minutes = ttl_minutes

    def create(self, user: User) -> str:
        raw_token = token_urlsafe(48)
        now = datetime.now(timezone.utc)
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=now + timedelta(minutes=self.ttl_minutes),
            last_seen_at=now,
        )
        self.session.add(auth_session)
        self.session.commit()
        return raw_token

    def resolve(self, raw_token: str) -> User | None:
        now = datetime.now(timezone.utc)
        statement = (
            select(AuthSession)
            .options(joinedload(AuthSession.user))
            .where(
                AuthSession.token_hash == hash_session_token(raw_token),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
        auth_session = self.session.scalar(statement)
        if auth_session is None or not auth_session.user.enabled:
            return None
        auth_session.last_seen_at = now
        self.session.commit()
        return auth_session.user

    def revoke(self, raw_token: str) -> None:
        auth_session = self.session.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw_token))
        )
        if auth_session is None or auth_session.revoked_at is not None:
            return
        auth_session.revoked_at = datetime.now(timezone.utc)
        self.session.commit()
