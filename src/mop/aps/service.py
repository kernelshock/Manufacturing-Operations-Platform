"""Application service for G4.1 APS scenario/run foundation."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.schemas import SchedulingRunCreate, SchedulingScenarioCreate, SchedulingScenarioHorizonUpdate, SchedulingScenarioStatusUpdate
from mop.demand.models import ProductionPlan


class APSConflictError(ValueError):
    pass


class APSRuleError(ValueError):
    pass


class APSNotFoundError(LookupError):
    pass


_SCENARIO_TRANSITIONS = {
    "DRAFT": {"READY", "ARCHIVED"},
    "READY": {"DRAFT", "ARCHIVED"},
    "ARCHIVED": set(),
}


class APSService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit(self, entity):
        try:
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.session.rollback()
            raise APSConflictError("APS identity already exists") from exc

    def _get_plan(self, plan_id: UUID) -> ProductionPlan:
        plan = self.session.get(ProductionPlan, plan_id)
        if plan is None:
            raise APSNotFoundError("production plan not found")
        return plan

    def create_scenario(self, data: SchedulingScenarioCreate, actor_id: UUID | None) -> SchedulingScenario:
        plan = self._get_plan(data.plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise APSRuleError("cannot create a scheduling scenario for a terminal production plan")
        return self._commit(SchedulingScenario(
            plan_id=plan.id,
            scenario_code=data.scenario_code,
            name=data.name,
            description=data.description,
            horizon_start=data.horizon_start,
            horizon_end=data.horizon_end,
            planning_timezone=data.planning_timezone,
            status="DRAFT",
            created_by=actor_id,
        ))

    def list_scenarios(self, plan_id: UUID | None = None, status: str | None = None) -> Sequence[SchedulingScenario]:
        query = select(SchedulingScenario)
        if plan_id is not None:
            query = query.where(SchedulingScenario.plan_id == plan_id)
        if status is not None:
            query = query.where(SchedulingScenario.status == status)
        return self.session.scalars(query.order_by(SchedulingScenario.created_at.desc(), SchedulingScenario.scenario_code)).all()

    def get_scenario(self, scenario_id: UUID) -> SchedulingScenario:
        scenario = self.session.get(SchedulingScenario, scenario_id)
        if scenario is None:
            raise APSNotFoundError("scheduling scenario not found")
        return scenario

    def _has_runs(self, scenario_id: UUID) -> bool:
        return self.session.scalar(select(SchedulingRun.id).where(SchedulingRun.scenario_id == scenario_id).limit(1)) is not None

    def update_horizon(self, scenario_id: UUID, data: SchedulingScenarioHorizonUpdate) -> SchedulingScenario:
        scenario = self.get_scenario(scenario_id)
        if scenario.status != "DRAFT":
            raise APSRuleError("planning horizon can only be changed while scenario is DRAFT")
        if self._has_runs(scenario.id):
            raise APSRuleError("planning horizon is frozen once a run exists")
        scenario.horizon_start = data.horizon_start
        scenario.horizon_end = data.horizon_end
        scenario.planning_timezone = data.planning_timezone
        return self._commit(scenario)

    def transition_scenario(self, scenario_id: UUID, data: SchedulingScenarioStatusUpdate) -> SchedulingScenario:
        scenario = self.get_scenario(scenario_id)
        if data.status == scenario.status:
            return scenario
        if data.status not in _SCENARIO_TRANSITIONS[scenario.status]:
            raise APSRuleError(f"scheduling scenario transition {scenario.status} -> {data.status} is not allowed")
        if scenario.status == "READY" and data.status == "DRAFT" and self._has_runs(scenario.id):
            raise APSRuleError("scenario with planning runs cannot return to DRAFT")
        if data.status == "READY":
            plan = self._get_plan(scenario.plan_id)
            if plan.status in {"COMPLETED", "CANCELLED"}:
                raise APSRuleError("terminal production plan cannot be readied for scheduling")
        scenario.status = data.status
        return self._commit(scenario)

    def create_run(self, scenario_id: UUID, data: SchedulingRunCreate, actor_id: UUID | None) -> SchedulingRun:
        scenario = self.get_scenario(scenario_id)
        if scenario.status != "READY":
            raise APSRuleError("planning runs can only be created for READY scenarios")
        run_number = (self.session.scalar(select(func.max(SchedulingRun.run_number)).where(SchedulingRun.scenario_id == scenario.id)) or 0) + 1
        return self._commit(SchedulingRun(
            scenario_id=scenario.id,
            run_number=run_number,
            algorithm_key=data.algorithm_key,
            algorithm_version=data.algorithm_version,
            status="CREATED",
            created_by=actor_id,
        ))

    def list_runs(self, scenario_id: UUID) -> Sequence[SchedulingRun]:
        self.get_scenario(scenario_id)
        return self.session.scalars(select(SchedulingRun).where(SchedulingRun.scenario_id == scenario_id).order_by(SchedulingRun.run_number)).all()

    def cancel_run(self, run_id: UUID) -> SchedulingRun:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("scheduling run not found")
        if run.status == "CANCELLED":
            return run
        run.status = "CANCELLED"
        return self._commit(run)
