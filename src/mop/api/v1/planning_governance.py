"""Plant-scoped access to existing G7.6 exception cases."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.iam.authorization import AuthorizationService
from mop.iam.dependencies import get_current_user
from mop.iam.models import User
from mop.persistence.dependencies import get_session
from mop.planning.governance import DecisionKind, GovernanceProjection, GovernanceRole
from mop.planning.governance_evidence import verify_movement_references
from mop.planning.governance_models import GovernanceCaseRecord
from mop.planning.governance_service import GovernanceConflict, GovernanceService
from mop.planning.policy_contracts import PolicyError

router = APIRouter(prefix="/planning/governance", tags=["planning governance"])
SessionDependency = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
READ_PERMISSION = "planning.governance.read"


class ReviewAction(StrEnum):
    ACKNOWLEDGE = "ACKNOWLEDGE"
    REJECT = "REJECT"
    CLOSE = "CLOSE"


_ROLE_PERMISSIONS = {
    GovernanceRole.PURCHASING: "planning.governance.purchasing",
    GovernanceRole.PRODUCTION_MANAGER: "planning.governance.production",
    GovernanceRole.QUALITY: "planning.governance.quality",
    GovernanceRole.DIRECTOR: "planning.governance.direction",
}
_ACTION_ROLES = {
    ReviewAction.ACKNOWLEDGE: (
        GovernanceRole.QUALITY, GovernanceRole.PRODUCTION_MANAGER,
        GovernanceRole.PURCHASING, GovernanceRole.DIRECTOR,
    ),
    ReviewAction.REJECT: (GovernanceRole.DIRECTOR,),
    ReviewAction.CLOSE: (GovernanceRole.PURCHASING, GovernanceRole.DIRECTOR),
}


class ReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReviewAction
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    expected_revision: int = Field(ge=1, strict=True)
    movement_ids: list[UUID] = Field(default_factory=list, max_length=50)


def _readable_case(session: Session, actor: User, case_id: UUID) -> GovernanceCaseRecord:
    record = session.get(GovernanceCaseRecord, case_id)
    if record is None or not AuthorizationService(session).allowed(
        actor.id, READ_PERMISSION, "plant", record.plant_id,
    ):
        raise HTTPException(status_code=404, detail="governance case not found")
    return record


@router.get("/cases", response_model=list[UUID])
def list_case_ids(
    plant_id: UUID, session: SessionDependency, actor: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if not AuthorizationService(session).allowed(actor.id, READ_PERMISSION, "plant", plant_id):
        raise HTTPException(status_code=403, detail="plant governance permission required")
    return list(session.scalars(
        select(GovernanceCaseRecord.id)
        .where(GovernanceCaseRecord.plant_id == plant_id)
        .order_by(GovernanceCaseRecord.created_at.desc(), GovernanceCaseRecord.id)
        .limit(limit).offset(offset)
    ))


@router.get("/cases/{case_id}", response_model=GovernanceProjection)
def get_case(case_id: UUID, session: SessionDependency, actor: CurrentUser):
    _readable_case(session, actor, case_id)
    return GovernanceService(session).get(case_id)


@router.post("/cases/{case_id}/transitions", response_model=GovernanceProjection)
def record_transition(
    case_id: UUID, command: ReviewCommand, request: Request,
    session: SessionDependency, actor: CurrentUser,
):
    record = _readable_case(session, actor, case_id)
    authorization = AuthorizationService(session)
    role = next((
        role for role in _ACTION_ROLES[command.action]
        if authorization.allowed(actor.id, _ROLE_PERMISSIONS[role], "plant", record.plant_id)
    ), None)
    if role is None:
        raise HTTPException(status_code=403, detail="governance action permission required")

    context = request_audit_context(request)
    request_id = context["request_id"]
    if request_id is not None and len(request_id) > 64:
        raise HTTPException(status_code=422, detail="request identifier exceeds 64 characters")
    if command.action == ReviewAction.ACKNOWLEDGE and not command.movement_ids:
        raise HTTPException(status_code=422, detail="review requires ledger evidence")
    try:
        refs = verify_movement_references(session, record, command.movement_ids)
        projection = GovernanceService(session).transition(
            case_id, DecisionKind(command.action), actor=actor, role=role,
            reason=command.reason, expected_revision=command.expected_revision,
            idempotency_key=command.idempotency_key, evidence_refs=refs, **context,
        )
        session.commit()
        return projection
    except GovernanceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
