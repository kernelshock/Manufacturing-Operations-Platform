"""G4.5 schedule lifecycle, replan and publication endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.aps.lifecycle_schemas import (
    PublishResult,
    PublishScheduleRequest,
    PublishedScheduledOperationRead,
    ReplanCreate,
    ReplanResult,
    SchedulePublicationRead,
    ScheduleComparisonRead,
)
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


@router.post("/runs/{run_id}/replan", response_model=ReplanResult, status_code=status.HTTP_201_CREATED)
def replan(
    run_id: UUID,
    payload: ReplanCreate,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    created = translate(lambda: app.create_replan(run_id, payload, actor.id))
    AuditService(session).record(
        action="aps.run.replan.create",
        object_type="scheduling_run",
        object_id=str(created.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"source_run_id": str(run_id), "reason": created.replan_reason},
        **request_audit_context(request),
    )
    return ReplanResult(source_run_id=run_id, run=created)


@router.post("/runs/{run_id}/publish", response_model=PublishResult)
def publish(
    run_id: UUID,
    payload: PublishScheduleRequest,
    request: Request,
    app: APSService = Depends(service),
    actor: User = Depends(require_global_permission("aps.edit")),
    session: Session = Depends(get_session),
):
    publication, superseded_id, replay = translate(
        lambda: app.publish_schedule(run_id, payload.reason, actor.id)
    )
    AuditService(session).record(
        action="aps.schedule.publish",
        object_type="schedule_publication",
        object_id=str(publication.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={
            "run_id": str(run_id),
            "version_no": publication.version_no,
            "superseded_publication_id": str(superseded_id) if superseded_id else None,
            "idempotent_replay": replay,
        },
        **request_audit_context(request),
    )
    return PublishResult(
        publication=publication,
        superseded_publication_id=superseded_id,
        idempotent_replay=replay,
    )


@router.get("/scenarios/{scenario_id}/publications", response_model=list[SchedulePublicationRead])
def list_publications(
    scenario_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_publications(scenario_id))


@router.get("/publications/{publication_id}", response_model=SchedulePublicationRead)
def get_publication(
    publication_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.get_publication(publication_id))


@router.get("/publications/{publication_id}/operations", response_model=list[PublishedScheduledOperationRead])
def list_published_operations(
    publication_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_published_operations(publication_id))


@router.get("/runs/{run_id}/compare-to-published", response_model=ScheduleComparisonRead)
def compare_to_published(
    run_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return ScheduleComparisonRead(**translate(lambda: app.compare_replan_to_published(run_id)))
