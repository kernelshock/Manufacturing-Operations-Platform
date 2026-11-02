"""Application service for G4.1 APS scenario/run foundation."""

from collections.abc import Sequence
from datetime import datetime, timezone
import hashlib
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.schemas import SchedulingRunCreate, SchedulingScenarioCreate, SchedulingScenarioHorizonUpdate, SchedulingScenarioStatusUpdate
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import RoutingOperation, RoutingRevision


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


    def expand_run(self, run_id: UUID) -> tuple[SchedulingRun, int, int, int, bool]:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("scheduling run not found")
        if run.status == "CANCELLED":
            raise APSRuleError("cancelled scheduling run cannot be expanded")
        existing = self.session.scalars(
            select(PlanningOperation).where(PlanningOperation.run_id == run.id)
        ).all()
        if run.status == "EXPANDED":
            return (
                run,
                len(existing),
                len({item.product_line_id for item in existing}),
                len({item.routing_revision_id for item in existing}),
                True,
            )

        scenario = self.get_scenario(run.scenario_id)
        lines = self.session.scalars(
            select(TaquillaProductLine)
            .join(Taquilla, Taquilla.id == TaquillaProductLine.taquilla_id)
            .where(
                Taquilla.plan_id == scenario.plan_id,
                Taquilla.status != "CANCELLED",
            )
            .order_by(Taquilla.sequence_no, TaquillaProductLine.sequence_no, TaquillaProductLine.id)
        ).all()
        if not lines:
            raise APSRuleError("scheduling run cannot expand without active demand lines")

        snapshots = []
        fingerprint_parts = []
        routing_ids = set()
        for line in lines:
            if line.routing_revision_id is None:
                raise APSRuleError("every active demand line requires a routing binding before APS expansion")
            routing = self.session.get(RoutingRevision, line.routing_revision_id)
            if routing is None:
                raise APSNotFoundError("bound routing revision not found")
            if routing.status not in {"ACTIVE", "SUPERSEDED"}:
                raise APSRuleError("bound routing revision is not eligible for APS expansion")
            operations = self.session.scalars(
                select(RoutingOperation)
                .where(
                    RoutingOperation.routing_revision_id == routing.id,
                    RoutingOperation.active.is_(True),
                )
                .order_by(RoutingOperation.sequence_no, RoutingOperation.id)
            ).all()
            if not operations:
                raise APSRuleError("bound routing revision has no active operations")
            routing_ids.add(routing.id)
            taquilla = self.session.get(Taquilla, line.taquilla_id)
            if taquilla is None:
                raise APSNotFoundError("taquilla not found during APS expansion")
            for operation in operations:
                fingerprint_parts.append(
                    "|".join(
                        [
                            str(line.id),
                            str(line.requested_quantity),
                            str(routing.id),
                            routing.source_fingerprint,
                            str(operation.id),
                            str(operation.sequence_no),
                            str(operation.active),
                        ]
                    )
                )
                snapshots.append(
                    PlanningOperation(
                        run_id=run.id,
                        plan_id=scenario.plan_id,
                        taquilla_id=taquilla.id,
                        product_line_id=line.id,
                        article_id=line.article_id,
                        routing_revision_id=routing.id,
                        routing_operation_id=operation.id,
                        requested_quantity=line.requested_quantity,
                        deck_position=line.deck_position,
                        product_sequence_no=line.sequence_no,
                        routing_sequence_no=operation.sequence_no,
                        source_operation_code=operation.source_operation_code,
                        source_description=operation.source_description,
                        operation_kind=operation.operation_kind,
                        schedulable=operation.schedulable,
                        completion_marker=operation.completion_marker,
                        area_id=operation.area_id,
                        work_center_id=operation.work_center_id,
                        nominal_rate=operation.nominal_rate,
                        rate_uom=operation.rate_uom,
                        routing_source_fingerprint=routing.source_fingerprint,
                    )
                )

        fingerprint = hashlib.sha256("\n".join(fingerprint_parts).encode("utf-8")).hexdigest()
        try:
            self.session.add_all(snapshots)
            run.input_fingerprint = fingerprint
            run.expanded_at = datetime.now(timezone.utc)
            run.operation_count = len(snapshots)
            run.status = "EXPANDED"
            self.session.add(run)
            self.session.commit()
            self.session.refresh(run)
        except IntegrityError as exc:
            self.session.rollback()
            raise APSConflictError("planning operation expansion conflicts with existing snapshot") from exc

        return run, len(snapshots), len(lines), len(routing_ids), False

    def list_planning_operations(self, run_id: UUID) -> Sequence[PlanningOperation]:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("scheduling run not found")
        return self.session.scalars(
            select(PlanningOperation)
            .where(PlanningOperation.run_id == run_id)
            .order_by(
                PlanningOperation.taquilla_id,
                PlanningOperation.product_sequence_no,
                PlanningOperation.routing_sequence_no,
                PlanningOperation.id,
            )
        ).all()
