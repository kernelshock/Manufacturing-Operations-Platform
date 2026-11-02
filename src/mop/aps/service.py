"""Application service for G4.1 APS scenario/run foundation."""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
import hashlib
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.capacity_models import CapacityCandidate, ResourceAvailabilityInterval
from mop.aps.schemas import SchedulingRunCreate, SchedulingScenarioCreate, SchedulingScenarioHorizonUpdate, SchedulingScenarioStatusUpdate
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.core.models import Area, Resource, WorkCenter
from mop.master_data.models import CalendarException, CalendarWeeklyWindow, ManufacturingCalendar, ResourceAssignment, RoutingOperation, RoutingRevision
from mop.master_data.service import MasterDataNotFoundError, MasterDataRuleError, MasterDataService


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


    def _capacity_candidates_for_operation(self, operation: PlanningOperation) -> list[tuple[Resource, ResourceAssignment | None, str, Decimal]]:
        assignments = self.session.scalars(
            select(ResourceAssignment).where(
                ResourceAssignment.routing_operation_id == operation.routing_operation_id
            )
        ).all()
        candidates: list[tuple[Resource, ResourceAssignment | None, str, Decimal]] = []
        if assignments:
            for assignment in assignments:
                resource = self.session.get(Resource, assignment.resource_id)
                if resource is None or not resource.active:
                    raise APSRuleError("schedulable operation references an unavailable resource")
                candidates.append(
                    (
                        resource,
                        assignment,
                        "EXPLICIT_ASSIGNMENT",
                        assignment.capacity_factor or Decimal("1"),
                    )
                )
            return candidates

        if operation.work_center_id is None:
            raise APSRuleError("schedulable operation requires a resource assignment or work center")

        resources = self.session.scalars(
            select(Resource)
            .where(
                Resource.work_center_id == operation.work_center_id,
                Resource.active.is_(True),
            )
            .order_by(Resource.code, Resource.id)
        ).all()
        if not resources:
            raise APSRuleError("schedulable work center has no active resources")
        return [
            (resource, None, "WORK_CENTER_POOL", Decimal("1"))
            for resource in resources
        ]

    def _calendar_boundaries(
        self,
        resource: Resource,
        start_at: datetime,
        end_at: datetime,
    ) -> list[datetime]:
        work_center = self.session.get(WorkCenter, resource.work_center_id)
        if work_center is None:
            raise APSNotFoundError("resource work center not found")
        area = self.session.get(Area, work_center.area_id)
        if area is None:
            raise APSNotFoundError("resource area not found")

        hierarchy = [
            ("resource", resource.id),
            ("work_center", work_center.id),
            ("area", area.id),
            ("plant", area.plant_id),
        ]
        calendars = self.session.scalars(
            select(ManufacturingCalendar).where(
                ManufacturingCalendar.status.in_(("ACTIVE", "SUPERSEDED"))
            )
        ).all()

        relevant = []
        for calendar in calendars:
            scope, target_id = MasterDataService._calendar_target(calendar)
            if (scope, target_id) in hierarchy:
                relevant.append(calendar)

        boundaries = {start_at.astimezone(timezone.utc), end_at.astimezone(timezone.utc)}
        for calendar in relevant:
            tz = ZoneInfo(calendar.timezone)
            local_start = start_at.astimezone(tz).date() - timedelta(days=1)
            local_end = end_at.astimezone(tz).date() + timedelta(days=1)

            for marker in (calendar.valid_from, calendar.valid_to):
                if marker is None:
                    continue
                local_marker = datetime.combine(marker, time.min, tzinfo=tz)
                marker_utc = local_marker.astimezone(timezone.utc)
                if start_at < marker_utc < end_at:
                    boundaries.add(marker_utc)

            windows = self.session.scalars(
                select(CalendarWeeklyWindow).where(
                    CalendarWeeklyWindow.calendar_id == calendar.id,
                    CalendarWeeklyWindow.active.is_(True),
                )
            ).all()
            exceptions = self.session.scalars(
                select(CalendarException).where(
                    CalendarException.calendar_id == calendar.id,
                    CalendarException.active.is_(True),
                    CalendarException.local_date >= local_start,
                    CalendarException.local_date <= local_end,
                )
            ).all()
            by_date: dict[date, list[CalendarException]] = {}
            for exc in exceptions:
                by_date.setdefault(exc.local_date, []).append(exc)

            current = local_start
            while current <= local_end:
                midnight = datetime.combine(current, time.min, tzinfo=tz)
                next_midnight = datetime.combine(current + timedelta(days=1), time.min, tzinfo=tz)
                for point in (midnight, next_midnight):
                    point_utc = point.astimezone(timezone.utc)
                    if start_at < point_utc < end_at:
                        boundaries.add(point_utc)

                weekday = current.weekday()
                for window in windows:
                    if window.weekday != weekday:
                        continue
                    start_local = midnight + timedelta(minutes=window.start_minute)
                    if window.spans_midnight:
                        end_local = next_midnight + timedelta(minutes=window.end_minute)
                    else:
                        end_local = midnight + timedelta(minutes=window.end_minute)
                    for point in (start_local, end_local):
                        point_utc = point.astimezone(timezone.utc)
                        if start_at < point_utc < end_at:
                            boundaries.add(point_utc)

                for exc in by_date.get(current, []):
                    start_minute = exc.start_minute if exc.start_minute is not None else 0
                    end_minute = exc.end_minute if exc.end_minute is not None else 1440
                    for minute in (start_minute, end_minute):
                        point = midnight + timedelta(minutes=minute)
                        point_utc = point.astimezone(timezone.utc)
                        if start_at < point_utc < end_at:
                            boundaries.add(point_utc)
                current += timedelta(days=1)

        return sorted(boundaries)

    def _availability_intervals_for_resource(
        self,
        run_id: UUID,
        resource: Resource,
        start_at: datetime,
        end_at: datetime,
    ) -> list[ResourceAvailabilityInterval]:
        boundaries = self._calendar_boundaries(resource, start_at, end_at)
        resolver = MasterDataService(self.session)
        rows: list[ResourceAvailabilityInterval] = []
        for left, right in zip(boundaries, boundaries[1:]):
            if right <= left:
                continue
            midpoint = left + (right - left) / 2
            try:
                resolved = resolver.resolve_calendar_availability(
                    at=midpoint,
                    resource_id=resource.id,
                )
            except (MasterDataNotFoundError, MasterDataRuleError) as exc:
                raise APSRuleError(str(exc)) from exc
            if not resolved.available:
                continue

            if (
                rows
                and rows[-1].end_at == left
                and rows[-1].calendar_id == resolved.calendar_id
                and rows[-1].calendar_capacity_factor == resolved.capacity_factor
                and rows[-1].source == resolved.source
            ):
                rows[-1].end_at = right
                continue

            rows.append(
                ResourceAvailabilityInterval(
                    run_id=run_id,
                    resource_id=resource.id,
                    calendar_id=resolved.calendar_id,
                    calendar_code=resolved.calendar_code,
                    calendar_revision_no=resolved.calendar_revision_no,
                    target_scope=resolved.target_scope,
                    timezone=resolved.timezone,
                    start_at=left,
                    end_at=right,
                    calendar_capacity_factor=resolved.capacity_factor,
                    source=resolved.source,
                )
            )
        if not rows:
            raise APSRuleError("resource has no available capacity inside the planning horizon")
        return rows

    def project_capacity(self, run_id: UUID) -> tuple[SchedulingRun, int, int, bool]:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("scheduling run not found")
        if run.status == "CANCELLED":
            raise APSRuleError("cancelled scheduling run cannot project capacity")
        if run.status == "CAPACITY_PROJECTED":
            candidate_count = self.session.scalar(
                select(func.count()).select_from(CapacityCandidate).where(CapacityCandidate.run_id == run.id)
            ) or 0
            interval_count = self.session.scalar(
                select(func.count()).select_from(ResourceAvailabilityInterval).where(ResourceAvailabilityInterval.run_id == run.id)
            ) or 0
            return run, candidate_count, interval_count, True
        if run.status != "EXPANDED":
            raise APSRuleError("capacity projection requires an EXPANDED scheduling run")

        scenario = self.get_scenario(run.scenario_id)
        operations = self.session.scalars(
            select(PlanningOperation)
            .where(
                PlanningOperation.run_id == run.id,
                PlanningOperation.schedulable.is_(True),
            )
            .order_by(PlanningOperation.routing_sequence_no, PlanningOperation.id)
        ).all()
        if not operations:
            raise APSRuleError("expanded run contains no schedulable planning operations")

        candidates: list[CapacityCandidate] = []
        resources: dict[UUID, Resource] = {}
        for operation in operations:
            resolved = self._capacity_candidates_for_operation(operation)
            for resource, assignment, source_mode, assignment_factor in resolved:
                resources[resource.id] = resource
                candidates.append(
                    CapacityCandidate(
                        run_id=run.id,
                        planning_operation_id=operation.id,
                        routing_operation_id=operation.routing_operation_id,
                        resource_id=resource.id,
                        source_mode=source_mode,
                        resource_assignment_id=assignment.id if assignment else None,
                        assignment_capacity_factor=assignment_factor,
                    )
                )

        intervals: list[ResourceAvailabilityInterval] = []
        for resource in resources.values():
            intervals.extend(
                self._availability_intervals_for_resource(
                    run.id,
                    resource,
                    scenario.horizon_start,
                    scenario.horizon_end,
                )
            )

        try:
            self.session.add_all(candidates)
            self.session.add_all(intervals)
            run.status = "CAPACITY_PROJECTED"
            self.session.add(run)
            self.session.commit()
            self.session.refresh(run)
        except IntegrityError as exc:
            self.session.rollback()
            raise APSConflictError("capacity projection conflicts with existing snapshot") from exc

        return run, len(candidates), len(intervals), False

    def list_capacity_candidates(self, run_id: UUID) -> Sequence[CapacityCandidate]:
        return self.session.scalars(
            select(CapacityCandidate)
            .where(CapacityCandidate.run_id == run_id)
            .order_by(CapacityCandidate.planning_operation_id, CapacityCandidate.resource_id)
        ).all()

    def list_resource_availability(self, run_id: UUID) -> Sequence[ResourceAvailabilityInterval]:
        return self.session.scalars(
            select(ResourceAvailabilityInterval)
            .where(ResourceAvailabilityInterval.run_id == run_id)
            .order_by(ResourceAvailabilityInterval.resource_id, ResourceAvailabilityInterval.start_at)
        ).all()
