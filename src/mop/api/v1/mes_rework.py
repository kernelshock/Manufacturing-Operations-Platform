"""G5.5 governed MES rework API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session
from mop.mes.service import MESConflictError, MESNotFoundError, MESRuleError
from mop.mes.rework_service import ReworkService
from mop.mes.rework_schemas import (
    ReworkActionResult, ReworkCaseCreate, ReworkCaseRead, ReworkComplete,
    ReworkStart, ReworkStepActionResult, ReworkStepCreate, ReworkStepRead,
)

router = APIRouter(prefix="/mes/rework", tags=["mes"])


def service(session: Session = Depends(get_session)) -> ReworkService:
    return ReworkService(session)


def translated(operation):
    try:
        return operation()
    except MESNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MESConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MESRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def audit(session: Session, request: Request, actor: User, action: str, object_id: UUID, details: dict) -> None:
    AuditService(session).record(
        action=action,
        object_type="mes_rework",
        object_id=str(object_id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details=details,
        **request_audit_context(request),
    )


@router.post("/cases", response_model=ReworkActionResult)
def create_case(
    payload: ReworkCaseCreate, request: Request, app: ReworkService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    case, replay = translated(lambda: app.create_case(payload, actor.id))
    audit(session, request, actor, "mes.rework.case.create", case.id, {
        "source_operation_id": str(case.source_execution_operation_id),
        "return_operation_id": str(case.return_execution_operation_id),
        "quantity": str(case.quantity), "reason_code": case.reason_code,
        "idempotent_replay": replay,
    })
    return ReworkActionResult(case=case, idempotent_replay=replay)


@router.get("/dispatches/{dispatch_id}/cases", response_model=list[ReworkCaseRead])
def list_cases(
    dispatch_id: UUID, app: ReworkService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return translated(lambda: app.list_cases(dispatch_id))


@router.get("/cases/{case_id}", response_model=ReworkCaseRead)
def get_case(
    case_id: UUID, app: ReworkService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return translated(lambda: app.get_case(case_id))


@router.get("/cases/{case_id}/steps", response_model=list[ReworkStepRead])
def list_steps(
    case_id: UUID, app: ReworkService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return translated(lambda: app.list_steps(case_id))


@router.post("/cases/{case_id}/steps", response_model=ReworkStepRead)
def add_step(
    case_id: UUID, payload: ReworkStepCreate, request: Request,
    app: ReworkService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    step = translated(lambda: app.add_step(case_id, payload))
    audit(session, request, actor, "mes.rework.step.add", step.id, {
        "case_id": str(case_id), "routing_operation_id": str(step.routing_operation_id),
        "resource_id": str(step.resource_id), "sequence_no": step.sequence_no,
    })
    return step


@router.post("/steps/{step_id}/start", response_model=ReworkStepActionResult)
def start_step(
    step_id: UUID, payload: ReworkStart, request: Request,
    app: ReworkService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    step, replay = translated(lambda: app.start_step(step_id, payload, actor.id))
    audit(session, request, actor, "mes.rework.step.start", step.id, {
        "case_id": str(step.case_id), "timestamp": step.actual_start.isoformat(),
        "idempotent_replay": replay,
    })
    return ReworkStepActionResult(step=step, idempotent_replay=replay)


@router.post("/steps/{step_id}/complete", response_model=ReworkStepActionResult)
def complete_step(
    step_id: UUID, payload: ReworkComplete, request: Request,
    app: ReworkService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    step, replay = translated(lambda: app.complete_step(step_id, payload, actor.id))
    audit(session, request, actor, "mes.rework.step.complete", step.id, {
        "case_id": str(step.case_id), "quantity": str(step.produced_quantity),
        "timestamp": step.actual_finish.isoformat(), "idempotent_replay": replay,
    })
    return ReworkStepActionResult(step=step, idempotent_replay=replay)


@router.post("/cases/{case_id}/return", response_model=ReworkActionResult)
def return_case(
    case_id: UUID, payload: ReworkStart, request: Request,
    app: ReworkService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    case, replay = translated(lambda: app.return_case(case_id, payload.occurred_at, actor.id))
    audit(session, request, actor, "mes.rework.case.return", case.id, {
        "return_operation_id": str(case.return_execution_operation_id),
        "quantity": str(case.quantity), "idempotent_replay": replay,
    })
    return ReworkActionResult(case=case, idempotent_replay=replay)
