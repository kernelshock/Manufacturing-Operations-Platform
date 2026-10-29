"""Append-only audit write and query service."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        action: str,
        object_type: str,
        outcome: str,
        actor_user_id: UUID | None = None,
        actor_username: str | None = None,
        object_id: str | None = None,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
        request_id: str | None = None,
        source_ip: str | None = None,
        details: dict | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            action=action,
            object_type=object_type,
            object_id=object_id,
            scope_type=scope_type,
            scope_id=scope_id,
            outcome=outcome,
            request_id=request_id,
            source_ip=source_ip,
            details=details or {},
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def list_entries(
        self,
        *,
        action: str | None = None,
        actor_user_id: UUID | None = None,
        limit: int = 100,
    ) -> Sequence[AuditEntry]:
        statement = select(AuditEntry)
        if action is not None:
            statement = statement.where(AuditEntry.action == action)
        if actor_user_id is not None:
            statement = statement.where(AuditEntry.actor_user_id == actor_user_id)
        statement = statement.order_by(AuditEntry.occurred_at.desc(), AuditEntry.id.desc()).limit(limit)
        return self.session.scalars(statement).all()
