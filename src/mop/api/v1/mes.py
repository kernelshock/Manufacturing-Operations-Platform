"""G5.1 MES execution dispatch API."""

from uuid import UUID
from sqlalchemy import select
from pydantic import BaseModel
from mop.core.models import Resource

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.mes.schemas import (
    DispatchMaterializationResult,
    ExecutionActionResult,
    ExecutionCompleteCreate,
    ExecutionDeviationRead,
    ExecutionDispatchCreate,
    ExecutionDispatchRead,
    ExecutionHandoffRead,
    ExecutionInterruptionRead,
    ExecutionOperationEventRead,
    ExecutionOperationRead,
    ExecutionSetupRead,
    ExecutionStartCreate,
    ExecutionWIPTraceRead,
    HandoffActionResult,
    HandoffReceiveCreate,
    HandoffTransferCreate,
    InterruptionActionResult,
    InterruptionResumeCreate,
    InterruptionStartCreate,
    SetupActionResult,
    SetupFinishCreate,
    SetupStartCreate,
)
from mop.mes.service import MESConflictError, MESNotFoundError, MESRuleError, MESService
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/mes", tags=["mes"])


def service(session: Session = Depends(get_session)) -> MESService:
    return MESService(session)


def _translate(operation):
    try:
        return operation()
    except MESNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MESConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MESRuleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def _audit(
    *,
    session: Session,
    request: Request,
    actor: User,
    action: str,
    object_type: str,
    object_id: UUID,
    details: dict | None = None,
) -> None:
    AuditService(session).record(
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details=details,
        **request_audit_context(request),
    )


@router.post(
    "/dispatches",
    response_model=DispatchMaterializationResult,
    status_code=status.HTTP_201_CREATED,
)
def create_dispatch(
    payload: ExecutionDispatchCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    dispatch, operation_count, replay = _translate(
        lambda: app.create_dispatch(payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.dispatch.create",
        object_type="execution_dispatch",
        object_id=dispatch.id,
        details={
            "publication_id": str(dispatch.publication_id),
            "operation_count": operation_count,
            "idempotent_replay": replay,
        },
    )
    return DispatchMaterializationResult(
        dispatch=dispatch,
        operation_count=operation_count,
        idempotent_replay=replay,
    )


@router.get("/dispatches", response_model=list[ExecutionDispatchRead])
def list_dispatches(
    plan_id: UUID | None = None,
    dispatch_status: str | None = None,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return app.list_dispatches(plan_id=plan_id, status=dispatch_status)


@router.get("/dispatches/{dispatch_id}", response_model=ExecutionDispatchRead)
def get_dispatch(
    dispatch_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.get_dispatch(dispatch_id))


@router.get(
    "/dispatches/{dispatch_id}/operations",
    response_model=list[ExecutionOperationRead],
)
def list_operations(
    dispatch_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.list_operations(dispatch_id))


@router.post(
    "/dispatches/{dispatch_id}/release",
    response_model=ExecutionDispatchRead,
)
def release_dispatch(
    dispatch_id: UUID,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_dispatch(dispatch_id)).status
    dispatch = _translate(lambda: app.release_dispatch(dispatch_id))
    if previous != dispatch.status:
        _audit(
            session=session,
            request=request,
            actor=actor,
            action="mes.dispatch.release",
            object_type="execution_dispatch",
            object_id=dispatch.id,
            details={
                "publication_id": str(dispatch.publication_id),
                "operation_count": dispatch.operation_count,
            },
        )
    return dispatch


@router.post(
    "/dispatches/{dispatch_id}/cancel",
    response_model=ExecutionDispatchRead,
)
def cancel_dispatch(
    dispatch_id: UUID,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_dispatch(dispatch_id)).status
    dispatch = _translate(lambda: app.cancel_dispatch(dispatch_id))
    if previous != dispatch.status:
        _audit(
            session=session,
            request=request,
            actor=actor,
            action="mes.dispatch.cancel",
            object_type="execution_dispatch",
            object_id=dispatch.id,
            details={"publication_id": str(dispatch.publication_id)},
        )
    return dispatch



@router.get(
    "/operations/{operation_id}",
    response_model=ExecutionOperationRead,
)
def get_operation(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.get_operation(operation_id))


@router.get(
    "/operations/{operation_id}/events",
    response_model=list[ExecutionOperationEventRead],
)
def list_operation_events(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.list_operation_events(operation_id))


@router.post(
    "/operations/{operation_id}/start",
    response_model=ExecutionActionResult,
)
def start_operation(
    operation_id: UUID,
    payload: ExecutionStartCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    operation, event, replay = _translate(
        lambda: app.start_operation(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.operation.start",
        object_type="execution_operation",
        object_id=operation.id,
        details={
            "dispatch_id": str(operation.dispatch_id),
            "occurred_at": event.occurred_at.isoformat(),
            "idempotent_replay": replay,
        },
    )
    return ExecutionActionResult(
        operation=operation,
        event=event,
        idempotent_replay=replay,
    )


@router.post(
    "/operations/{operation_id}/complete",
    response_model=ExecutionActionResult,
)
def complete_operation(
    operation_id: UUID,
    payload: ExecutionCompleteCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    operation, event, replay = _translate(
        lambda: app.complete_operation(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.operation.complete",
        object_type="execution_operation",
        object_id=operation.id,
        details={
            "dispatch_id": str(operation.dispatch_id),
            "occurred_at": event.occurred_at.isoformat(),
            "produced_quantity": str(event.produced_quantity),
            "idempotent_replay": replay,
        },
    )
    return ExecutionActionResult(
        operation=operation,
        event=event,
        idempotent_replay=replay,
    )



@router.get(
    "/operations/{operation_id}/setup",
    response_model=ExecutionSetupRead | None,
)
def get_setup(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.get_setup(operation_id))


@router.post(
    "/operations/{operation_id}/setup/start",
    response_model=SetupActionResult,
)
def start_setup(
    operation_id: UUID,
    payload: SetupStartCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    operation, setup, replay = _translate(
        lambda: app.start_setup(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.operation.setup.start",
        object_type="execution_operation",
        object_id=operation.id,
        details={
            "setup_id": str(setup.id),
            "occurred_at": setup.started_at.isoformat(),
            "idempotent_replay": replay,
        },
    )
    return SetupActionResult(
        operation=operation,
        setup=setup,
        idempotent_replay=replay,
    )


@router.post(
    "/operations/{operation_id}/setup/finish",
    response_model=SetupActionResult,
)
def finish_setup(
    operation_id: UUID,
    payload: SetupFinishCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    operation, setup, replay = _translate(
        lambda: app.finish_setup(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.operation.setup.finish",
        object_type="execution_operation",
        object_id=operation.id,
        details={
            "setup_id": str(setup.id),
            "occurred_at": setup.finished_at.isoformat() if setup.finished_at else None,
            "idempotent_replay": replay,
        },
    )
    return SetupActionResult(
        operation=operation,
        setup=setup,
        idempotent_replay=replay,
    )


@router.get(
    "/operations/{operation_id}/interruptions",
    response_model=list[ExecutionInterruptionRead],
)
def list_interruptions(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.list_interruptions(operation_id))


@router.post(
    "/operations/{operation_id}/pause",
    response_model=InterruptionActionResult,
)
def pause_operation(
    operation_id: UUID,
    payload: InterruptionStartCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    operation, interruption, replay = _translate(
        lambda: app.pause_operation(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.operation.pause",
        object_type="execution_operation",
        object_id=operation.id,
        details={
            "interruption_id": str(interruption.id),
            "reason_code": interruption.reason_code,
            "occurred_at": interruption.started_at.isoformat(),
            "idempotent_replay": replay,
        },
    )
    return InterruptionActionResult(
        operation=operation,
        interruption=interruption,
        idempotent_replay=replay,
    )


@router.post(
    "/operations/{operation_id}/resume",
    response_model=InterruptionActionResult,
)
def resume_operation(
    operation_id: UUID,
    payload: InterruptionResumeCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    operation, interruption, replay = _translate(
        lambda: app.resume_operation(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.operation.resume",
        object_type="execution_operation",
        object_id=operation.id,
        details={
            "interruption_id": str(interruption.id),
            "occurred_at": interruption.ended_at.isoformat() if interruption.ended_at else None,
            "idempotent_replay": replay,
        },
    )
    return InterruptionActionResult(
        operation=operation,
        interruption=interruption,
        idempotent_replay=replay,
    )


@router.get(
    "/operations/{operation_id}/deviation",
    response_model=ExecutionDeviationRead,
)
def get_deviation(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.get_deviation(operation_id))



@router.get(
    "/operations/{operation_id}/handoffs",
    response_model=list[ExecutionHandoffRead],
)
def list_handoffs(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.list_handoffs(operation_id))


@router.post(
    "/operations/{operation_id}/handoffs/transfer",
    response_model=HandoffActionResult,
)
def transfer_wip(
    operation_id: UUID,
    payload: HandoffTransferCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    handoff, replay = _translate(
        lambda: app.transfer_wip(operation_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.handoff.transfer",
        object_type="execution_handoff",
        object_id=handoff.id,
        details={
            "from_operation_id": str(handoff.from_execution_operation_id),
            "to_operation_id": str(handoff.to_execution_operation_id),
            "quantity": str(handoff.quantity),
            "sequence_no": handoff.sequence_no,
            "idempotent_replay": replay,
        },
    )
    return HandoffActionResult(handoff=handoff, idempotent_replay=replay)


@router.post(
    "/handoffs/{handoff_id}/receive",
    response_model=HandoffActionResult,
)
def receive_handoff(
    handoff_id: UUID,
    payload: HandoffReceiveCreate,
    request: Request,
    app: MESService = Depends(service),
    actor: User = Depends(require_global_permission("mes.edit")),
    session: Session = Depends(get_session),
):
    handoff, replay = _translate(
        lambda: app.receive_handoff(handoff_id, payload, actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="mes.handoff.receive",
        object_type="execution_handoff",
        object_id=handoff.id,
        details={
            "from_operation_id": str(handoff.from_execution_operation_id),
            "to_operation_id": str(handoff.to_execution_operation_id),
            "quantity": str(handoff.quantity),
            "sequence_no": handoff.sequence_no,
            "idempotent_replay": replay,
        },
    )
    return HandoffActionResult(handoff=handoff, idempotent_replay=replay)


@router.get(
    "/operations/{operation_id}/wip-trace",
    response_model=ExecutionWIPTraceRead,
)
def get_wip_trace(
    operation_id: UUID,
    app: MESService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    return _translate(lambda: app.get_wip_trace(operation_id))


class MESResourceOption(BaseModel):
    id: UUID
    code: str
    name: str
    work_center_id: UUID

@router.get("/resources", response_model=list[MESResourceOption])
def list_mes_resource_options(
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("mes.read")),
):
    """Read-only active resource labels for MES capture without core IAM elevation.

    This does not grant core write access or override MES start validation.
    """
    resources = session.scalars(
        select(Resource).where(Resource.active.is_(True)).order_by(Resource.code, Resource.name)
    ).all()
    return [
        MESResourceOption(
            id=resource.id, code=resource.code, name=resource.name,
            work_center_id=resource.work_center_id,
        )
        for resource in resources
    ]
