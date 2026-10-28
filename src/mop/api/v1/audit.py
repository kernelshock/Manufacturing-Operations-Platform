"""Read-only audit API."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mop.audit.schemas import AuditEntryRead
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/events",
    response_model=list[AuditEntryRead],
    dependencies=[Depends(require_global_permission("audit.read"))],
)
def list_audit_events(
    action: str | None = None,
    actor_user_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
):
    return AuditService(session).list_entries(
        action=action,
        actor_user_id=actor_user_id,
        limit=limit,
    )
