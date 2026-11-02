"""G4.4 finite-capacity sequencing endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.aps.schedule_schemas import ScheduleSolveResult, ScheduledOperationRead, ScheduledOperationSegmentRead
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


@router.post("/runs/{run_id}/solve", response_model=ScheduleSolveResult)
def solve_run(
    run_id: UUID,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    run, operation_count, segment_count, makespan_start, makespan_finish, replay = translate(
        lambda: app.solve_finite_capacity(run_id)
    )
    AuditService(session).record(
        action="aps.run.solve",
        object_type="scheduling_run",
        object_id=str(run.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={
            "scheduled_operation_count": operation_count,
            "segment_count": segment_count,
            "makespan_start": makespan_start.isoformat(),
            "makespan_finish": makespan_finish.isoformat(),
            "idempotent_replay": replay,
        },
        **request_audit_context(request),
    )
    return ScheduleSolveResult(
        run=run,
        scheduled_operation_count=operation_count,
        segment_count=segment_count,
        makespan_start=makespan_start,
        makespan_finish=makespan_finish,
        idempotent_replay=replay,
    )


@router.get("/runs/{run_id}/schedule", response_model=list[ScheduledOperationRead])
def list_schedule(
    run_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_scheduled_operations(run_id))


@router.get("/scheduled-operations/{scheduled_operation_id}/segments", response_model=list[ScheduledOperationSegmentRead])
def list_segments(
    scheduled_operation_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_schedule_segments(scheduled_operation_id))
