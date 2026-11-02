"""G4.7 what-if and exception evaluation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.aps.service import APSConflictError, APSNotFoundError, APSRuleError, APSService
from mop.aps.whatif_schemas import (
    WhatIfApplyResult,
    WhatIfComparisonRead,
    WhatIfCreate,
    WhatIfEvaluationResult,
    WhatIfExceptionCreate,
    WhatIfExceptionRead,
    WhatIfScenarioRead,
)
from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/aps/what-if", tags=["aps"])


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


@router.post("", response_model=WhatIfScenarioRead, status_code=status.HTTP_201_CREATED)
def create_whatif(
    payload: WhatIfCreate,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    scenario = translate(lambda: app.create_whatif(payload, actor.id))
    AuditService(session).record(
        action="aps.whatif.create",
        object_type="whatif_scenario",
        object_id=str(scenario.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"baseline_publication_id": str(scenario.baseline_publication_id)},
        **request_audit_context(request),
    )
    return scenario


@router.get("", response_model=list[WhatIfScenarioRead])
def list_whatifs(
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return app.list_whatifs()


@router.post("/{whatif_id}/exceptions", response_model=WhatIfExceptionRead, status_code=status.HTTP_201_CREATED)
def add_exception(
    whatif_id: UUID,
    payload: WhatIfExceptionCreate,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    exception = translate(lambda: app.add_whatif_exception(whatif_id, payload))
    AuditService(session).record(
        action="aps.whatif.exception.add",
        object_type="whatif_exception",
        object_id=str(exception.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={
            "whatif_scenario_id": str(whatif_id),
            "exception_type": exception.exception_type,
            "resource_id": str(exception.resource_id),
        },
        **request_audit_context(request),
    )
    return exception


@router.get("/{whatif_id}/exceptions", response_model=list[WhatIfExceptionRead])
def list_exceptions(
    whatif_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_whatif_exceptions(whatif_id))


@router.post("/{whatif_id}/evaluate", response_model=WhatIfEvaluationResult)
def evaluate(
    whatif_id: UUID,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    scenario, comparison = translate(lambda: app.evaluate_whatif(whatif_id, actor.id))
    AuditService(session).record(
        action="aps.whatif.evaluate",
        object_type="whatif_scenario",
        object_id=str(scenario.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={
            "candidate_run_id": str(scenario.candidate_run_id),
            "timing_changed_count": comparison["timing_changed_count"],
            "resource_changed_count": comparison["resource_changed_count"],
            "makespan_delta_seconds": str(comparison["makespan_delta_seconds"]),
        },
        **request_audit_context(request),
    )
    return WhatIfEvaluationResult(
        scenario=scenario,
        comparison=WhatIfComparisonRead(**comparison),
    )


@router.get("/{whatif_id}/compare", response_model=WhatIfComparisonRead)
def compare(
    whatif_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return WhatIfComparisonRead(**translate(lambda: app.compare_whatif(whatif_id)))


@router.post("/{whatif_id}/apply", response_model=WhatIfApplyResult)
def apply(
    whatif_id: UUID,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    scenario, publication, superseded_id = translate(
        lambda: app.apply_whatif(whatif_id, actor.id)
    )
    AuditService(session).record(
        action="aps.whatif.apply",
        object_type="whatif_scenario",
        object_id=str(scenario.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={
            "publication_id": str(publication.id),
            "superseded_publication_id": str(superseded_id) if superseded_id else None,
        },
        **request_audit_context(request),
    )
    return WhatIfApplyResult(
        scenario=scenario,
        publication_id=publication.id,
        superseded_publication_id=superseded_id,
    )


@router.post("/{whatif_id}/discard", response_model=WhatIfScenarioRead)
def discard(
    whatif_id: UUID,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    scenario = translate(lambda: app.discard_whatif(whatif_id))
    AuditService(session).record(
        action="aps.whatif.discard",
        object_type="whatif_scenario",
        object_id=str(scenario.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"candidate_run_id": str(scenario.candidate_run_id) if scenario.candidate_run_id else None},
        **request_audit_context(request),
    )
    return scenario
