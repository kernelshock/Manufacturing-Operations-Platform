"""G5.1 MES execution dispatch API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.mes.schemas import (
    DispatchMaterializationResult,
    ExecutionDispatchCreate,
    ExecutionDispatchRead,
    ExecutionOperationRead,
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
