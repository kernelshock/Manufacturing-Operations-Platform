"""G4 APS API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.aps.schemas import SchedulingRunCreate, SchedulingRunRead, SchedulingScenarioCreate, SchedulingScenarioHorizonUpdate, SchedulingScenarioRead, SchedulingScenarioStatusUpdate
from mop.aps.service import APSConflictError, APSNotFoundError, APSRuleError, APSService
from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/aps", tags=["aps"])


def service(session: Session = Depends(get_session)) -> APSService:
    return APSService(session)


def _translate(operation):
    try:
        return operation()
    except APSNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except APSConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except APSRuleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def _audit(*, session: Session, request: Request, actor: User, action: str, object_type: str, object_id: UUID, details: dict | None = None) -> None:
    AuditService(session).record(action=action, object_type=object_type, object_id=str(object_id), outcome="success", actor_user_id=actor.id, actor_username=actor.username, details=details, **request_audit_context(request))


@router.post("/scenarios", response_model=SchedulingScenarioRead, status_code=status.HTTP_201_CREATED)
def create_scenario(payload: SchedulingScenarioCreate, request: Request, app: APSService = Depends(service), actor: User = Depends(require_global_permission("aps.edit")), session: Session = Depends(get_session)):
    created = _translate(lambda: app.create_scenario(payload, actor.id))
    _audit(session=session, request=request, actor=actor, action="aps.scenario.create", object_type="scheduling_scenario", object_id=created.id, details={"plan_id": str(created.plan_id), "scenario_code": created.scenario_code})
    return created


@router.get("/scenarios", response_model=list[SchedulingScenarioRead])
def list_scenarios(plan_id: UUID | None = None, scenario_status: str | None = None, app: APSService = Depends(service), _: User = Depends(require_global_permission("aps.read"))):
    return app.list_scenarios(plan_id, scenario_status)


@router.get("/scenarios/{scenario_id}", response_model=SchedulingScenarioRead)
def get_scenario(scenario_id: UUID, app: APSService = Depends(service), _: User = Depends(require_global_permission("aps.read"))):
    return _translate(lambda: app.get_scenario(scenario_id))


@router.patch("/scenarios/{scenario_id}/horizon", response_model=SchedulingScenarioRead)
def update_horizon(scenario_id: UUID, payload: SchedulingScenarioHorizonUpdate, request: Request, app: APSService = Depends(service), actor: User = Depends(require_global_permission("aps.edit")), session: Session = Depends(get_session)):
    before = _translate(lambda: app.get_scenario(scenario_id))
    previous = {"horizon_start": before.horizon_start.isoformat(), "horizon_end": before.horizon_end.isoformat(), "planning_timezone": before.planning_timezone}
    updated = _translate(lambda: app.update_horizon(scenario_id, payload))
    _audit(session=session, request=request, actor=actor, action="aps.scenario.horizon.update", object_type="scheduling_scenario", object_id=updated.id, details={"previous": previous, "horizon_start": updated.horizon_start.isoformat(), "horizon_end": updated.horizon_end.isoformat(), "planning_timezone": updated.planning_timezone})
    return updated


@router.post("/scenarios/{scenario_id}/status", response_model=SchedulingScenarioRead)
def transition_scenario(scenario_id: UUID, payload: SchedulingScenarioStatusUpdate, request: Request, app: APSService = Depends(service), actor: User = Depends(require_global_permission("aps.edit")), session: Session = Depends(get_session)):
    previous = _translate(lambda: app.get_scenario(scenario_id)).status
    updated = _translate(lambda: app.transition_scenario(scenario_id, payload))
    if previous != updated.status:
        _audit(session=session, request=request, actor=actor, action="aps.scenario.status.transition", object_type="scheduling_scenario", object_id=updated.id, details={"previous_status": previous, "status": updated.status})
    return updated


@router.post("/scenarios/{scenario_id}/runs", response_model=SchedulingRunRead, status_code=status.HTTP_201_CREATED)
def create_run(scenario_id: UUID, payload: SchedulingRunCreate, request: Request, app: APSService = Depends(service), actor: User = Depends(require_global_permission("aps.edit")), session: Session = Depends(get_session)):
    created = _translate(lambda: app.create_run(scenario_id, payload, actor.id))
    _audit(session=session, request=request, actor=actor, action="aps.run.create", object_type="scheduling_run", object_id=created.id, details={"scenario_id": str(created.scenario_id), "run_number": created.run_number, "algorithm_key": created.algorithm_key, "algorithm_version": created.algorithm_version})
    return created


@router.get("/scenarios/{scenario_id}/runs", response_model=list[SchedulingRunRead])
def list_runs(scenario_id: UUID, app: APSService = Depends(service), _: User = Depends(require_global_permission("aps.read"))):
    return _translate(lambda: app.list_runs(scenario_id))


@router.post("/runs/{run_id}/cancel", response_model=SchedulingRunRead)
def cancel_run(run_id: UUID, request: Request, app: APSService = Depends(service), actor: User = Depends(require_global_permission("aps.edit")), session: Session = Depends(get_session)):
    updated = _translate(lambda: app.cancel_run(run_id))
    _audit(session=session, request=request, actor=actor, action="aps.run.cancel", object_type="scheduling_run", object_id=updated.id, details={"status": updated.status})
    return updated
