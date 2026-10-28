"""Read models for immutable audit records."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_username: str | None
    action: str
    object_type: str
    object_id: str | None
    scope_type: str | None
    scope_id: UUID | None
    outcome: str
    request_id: str | None
    source_ip: str | None
    details: dict
