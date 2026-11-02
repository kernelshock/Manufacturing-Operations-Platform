"""G4.3 capacity projection endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from mop.aps.capacity_schemas import CapacityCandidateRead, CapacityProjectionResult, ResourceAvailabilityIntervalRead
from mop.aps.service import APSConflictError, APSNotFoundError, APSRuleError, APSService
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


@router.post("/runs/{run_id}/project-capacity", response_model=CapacityProjectionResult)
def project_capacity(
    run_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.edit")),
):
    run, candidate_count, interval_count, replay = translate(
        lambda: app.project_capacity(run_id)
    )
    return CapacityProjectionResult(
        run=run,
        candidate_count=candidate_count,
        interval_count=interval_count,
        idempotent_replay=replay,
    )


@router.get("/runs/{run_id}/capacity-candidates", response_model=list[CapacityCandidateRead])
def list_capacity_candidates(
    run_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_capacity_candidates(run_id))


@router.get("/runs/{run_id}/availability", response_model=list[ResourceAvailabilityIntervalRead])
def list_resource_availability(
    run_id: UUID,
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return translate(lambda: app.list_resource_availability(run_id))
