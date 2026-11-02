"""G4.2 APS expansion endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.aps.operation_schemas import ExpansionResult, PlanningOperationRead
from mop.aps.service import APSConflictError, APSNotFoundError, APSRuleError, APSService
from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/aps", tags=["aps"])


def service(session: Session = Depends(get_session)) -> APSService:
    return APSService(session)


def translate(operation):
    try:
        return operation()
    except APSNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except APSConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except APSRuleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/runs/{run_id}/operations", response_model=list[PlanningOperationRead])
def list_operations(run_id: UUID, app: APSService = Depends(service), _: User = Depends(require_global_permission("aps.read"))):
    return translate(lambda: app.list_planning_operations(run_id))


@router.post("/runs/{run_id}/materialize", response_model=ExpansionResult)
def materialize_run(run_id: UUID, app: APSService = Depends(service), _: User = Depends(require_global_permission("aps.edit"))):
    result = translate(lambda: app.expand_run(run_id))
    run, operations, lines, routings, replay = result
    return ExpansionResult(run=run, operation_count=operations, product_line_count=lines, routing_revision_count=routings, idempotent_replay=replay)
