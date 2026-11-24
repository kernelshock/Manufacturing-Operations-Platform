"""Plant-scoped access to existing G7.6 exception cases."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.iam.authorization import AuthorizationService
from mop.iam.dependencies import get_current_user
from mop.iam.models import User
from mop.materials.service import MaterialsNotFound, MaterialsRule
from mop.persistence.dependencies import get_session
from mop.planning.governance import (
    DecisionKind, ExceptionCase, GovernanceProjection, GovernanceRole, ProductionRiskEvidence, Severity,
)
from mop.planning.governance_evidence import resolve_material_stoppage, verify_movement_references
from mop.planning.governance_models import GovernanceCaseRecord
from mop.planning.governance_service import GovernanceConflict, GovernanceService
from mop.planning.policy_contracts import EvidenceState, PolicyError, RecommendationState

router = APIRouter(prefix="/planning/governance", tags=["planning governance"])
SessionDependency = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
READ_PERMISSION = "planning.governance.read"


class ReviewAction(StrEnum):
    ACKNOWLEDGE = "ACKNOWLEDGE"
    REJECT = "REJECT"
    CLOSE = "CLOSE"


_ROLE_PERMISSIONS = {
    GovernanceRole.PLANNER: "planning.governance.planner",
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



class StoppageCaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plant_id: UUID
    interruption_id: UUID
    article_id: UUID
    location_id: UUID
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


@router.post("/cases", status_code=201, response_model=GovernanceProjection)
def submit_stoppage_case(
    command: StoppageCaseCommand, request: Request,
    session: SessionDependency, actor: CurrentUser,
):
    authorization = AuthorizationService(session)
    if not authorization.allowed(actor.id, READ_PERMISSION, "plant", command.plant_id):
        raise HTTPException(status_code=403, detail="plant governance permission required")
    role = next((
        role for role in (GovernanceRole.PLANNER, GovernanceRole.PURCHASING, GovernanceRole.PRODUCTION_MANAGER)
        if authorization.allowed(actor.id, _ROLE_PERMISSIONS[role], "plant", command.plant_id)
    ), None)
    if role is None:
        raise HTTPException(status_code=403, detail="governance submission permission required")

    service = GovernanceService(session)
    case_id = uuid5(NAMESPACE_URL, f"faic-mop/g7/mes-interruption/{command.interruption_id}")
    scenario_key = f"MES:{command.interruption_id}:{command.article_id}:{command.location_id}"
    context = request_audit_context(request)
    request_id = context["request_id"]
    if request_id is not None and len(request_id) > 64:
        raise HTTPException(status_code=422, detail="request identifier exceeds 64 characters")
    try:
        record = session.get(GovernanceCaseRecord, case_id)
        if record is not None:
            if record.plant_id != command.plant_id or record.creator_id != actor.id:
                raise GovernanceConflict("case identifier is already in use")
            case = service.get(case_id).case
            if case.scenario_key != scenario_key:
                raise GovernanceConflict("case identifier is already in use")
        else:
            observed_at = datetime.now(timezone.utc)
            coverage = resolve_material_stoppage(
                session, plant_id=command.plant_id, article_id=command.article_id,
                location_id=command.location_id, interruption_id=command.interruption_id,
                observed_at=observed_at,
            )
            refs = (
                f"MES:INTERRUPTION:{command.interruption_id}",
                f"G6:COVERAGE:{coverage.taquilla_id}:{command.location_id}",
            )
            case = ExceptionCase(
                case_id=case_id, plant_id=command.plant_id, article_id=command.article_id,
                uom_id=coverage.uom_id, scenario_key=scenario_key,
                scenario_state=RecommendationState.BLOCKED, severity=Severity.STOPPAGE,
                reason_code="MATERIAL_SHORTAGE", creator_id=actor.id, created_at=observed_at,
                source_references=refs,
                impact=ProductionRiskEvidence(EvidenceState.VERIFIED, True, True, True, refs),
            )
        projection = service.submit(
            case, actor=actor, role=role, reason="MES material stoppage corroborated by G6 coverage",
            idempotency_key=command.idempotency_key, **context,
        )
        session.commit()
        return projection
    except GovernanceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PolicyError, MaterialsNotFound, MaterialsRule) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
