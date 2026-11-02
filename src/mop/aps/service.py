"""Application service for G4.1 APS scenario/run foundation."""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.capacity_models import CapacityCandidate, ResourceAvailabilityInterval
from mop.aps.schedule_models import ScheduledOperation, ScheduledOperationSegment
from mop.aps.lifecycle_models import SchedulePublication, PublishedScheduledOperation, PublishedScheduledOperationSegment
from mop.aps.schemas import SchedulingRunCreate, SchedulingScenarioCreate, SchedulingScenarioHorizonUpdate, SchedulingScenarioStatusUpdate
from mop.aps.lifecycle_schemas import ReplanCreate
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
        published = self.session.scalar(
            select(SchedulePublication.id).where(SchedulePublication.run_id == run.id).limit(1)
        )
        if published is not None:
            raise APSRuleError("published scheduling run cannot be cancelled")
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


    @staticmethod
    def _normalize_rate_per_hour(nominal_rate: Decimal | None, rate_uom: str | None) -> tuple[Decimal, str]:
        if nominal_rate is None or rate_uom is None:
            raise APSRuleError("schedulable operation requires nominal_rate and rate_uom")
        token = (
            rate_uom.strip()
            .upper()
            .replace(" ", "_")
            .replace("-", "_")
        )
        hourly = {
            "UNIT/H",
            "UNITS/H",
            "UNIT/HOUR",
            "UNITS/HOUR",
            "UNIT_PER_HOUR",
            "UNITS_PER_HOUR",
            "EA/H",
            "EA/HOUR",
        }
        per_minute = {
            "UNIT/MIN",
            "UNITS/MIN",
            "UNIT/MINUTE",
            "UNITS/MINUTE",
            "UNIT_PER_MINUTE",
            "UNITS_PER_MINUTE",
            "EA/MIN",
            "EA/MINUTE",
        }
        if token in hourly:
            return nominal_rate, "UNITS_PER_HOUR"
        if token in per_minute:
            return nominal_rate * Decimal("60"), "UNITS_PER_HOUR"
        raise APSRuleError(
            f"unsupported temporal rate_uom for finite-capacity scheduling: {rate_uom}"
        )

    @staticmethod
    def _subtract_occupied(
        start_at: datetime,
        end_at: datetime,
        occupied: list[tuple[datetime, datetime]],
    ) -> list[tuple[datetime, datetime]]:
        free = [(start_at, end_at)]
        for busy_start, busy_end in sorted(occupied):
            next_free: list[tuple[datetime, datetime]] = []
            for left, right in free:
                if busy_end <= left or busy_start >= right:
                    next_free.append((left, right))
                    continue
                if left < busy_start:
                    next_free.append((left, min(busy_start, right)))
                if busy_end < right:
                    next_free.append((max(busy_end, left), right))
            free = [(left, right) for left, right in next_free if right > left]
        return free

    def _candidate_schedule(
        self,
        *,
        run: SchedulingRun,
        operation: PlanningOperation,
        candidate: CapacityCandidate,
        earliest_start: datetime,
        occupied_by_resource: dict[UUID, list[tuple[datetime, datetime]]],
    ) -> tuple[datetime, datetime, Decimal, str, list[dict]]:
        rate_per_hour, normalized_rate_uom = self._normalize_rate_per_hour(
            operation.nominal_rate,
            operation.rate_uom,
        )
        intervals = self.session.scalars(
            select(ResourceAvailabilityInterval)
            .where(
                ResourceAvailabilityInterval.run_id == run.id,
                ResourceAvailabilityInterval.resource_id == candidate.resource_id,
                ResourceAvailabilityInterval.end_at > earliest_start,
            )
            .order_by(ResourceAvailabilityInterval.start_at, ResourceAvailabilityInterval.id)
        ).all()
        if not intervals:
            raise APSRuleError("candidate resource has no projected availability after precedence release")

        remaining = operation.requested_quantity
        segments: list[dict] = []
        occupied = occupied_by_resource.get(candidate.resource_id, [])
        processing_seconds = Decimal("0")

        for interval in intervals:
            interval_start = max(interval.start_at, earliest_start)
            if interval.end_at <= interval_start:
                continue
            free_ranges = self._subtract_occupied(interval_start, interval.end_at, occupied)
            effective_rate = (
                rate_per_hour
                * candidate.assignment_capacity_factor
                * interval.calendar_capacity_factor
            )
            if effective_rate <= 0:
                continue

            for free_start, free_end in free_ranges:
                free_seconds = Decimal(str((free_end - free_start).total_seconds()))
                if free_seconds <= 0:
                    continue
                possible_quantity = effective_rate * free_seconds / Decimal("3600")
                if possible_quantity <= 0:
                    continue

                if possible_quantity >= remaining:
                    needed_seconds = remaining * Decimal("3600") / effective_rate
                    end_at = free_start + timedelta(seconds=float(needed_seconds))
                    segments.append(
                        {
                            "availability_interval_id": interval.id,
                            "start_at": free_start,
                            "end_at": end_at,
                            "effective_rate_per_hour": effective_rate,
                            "produced_quantity": remaining,
                        }
                    )
                    processing_seconds += needed_seconds
                    remaining = Decimal("0")
                    break

                segments.append(
                    {
                        "availability_interval_id": interval.id,
                        "start_at": free_start,
                        "end_at": free_end,
                        "effective_rate_per_hour": effective_rate,
                        "produced_quantity": possible_quantity,
                    }
                )
                processing_seconds += free_seconds
                remaining -= possible_quantity

            if remaining <= Decimal("0"):
                break

        if remaining > Decimal("0"):
            raise APSRuleError("insufficient finite capacity inside planning horizon")

        return (
            segments[0]["start_at"],
            segments[-1]["end_at"],
            processing_seconds,
            normalized_rate_uom,
            segments,
        )

    def solve_finite_capacity(self, run_id: UUID) -> tuple[SchedulingRun, int, int, datetime, datetime, bool]:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("scheduling run not found")
        if run.status == "CANCELLED":
            raise APSRuleError("cancelled scheduling run cannot be solved")
        existing = self.session.scalars(
            select(ScheduledOperation)
            .where(ScheduledOperation.run_id == run.id)
            .order_by(ScheduledOperation.sequence_no)
        ).all()
        if run.status == "SCHEDULED":
            if not existing:
                raise APSRuleError("scheduled run has no scheduled operations")
            segment_count = self.session.scalar(
                select(func.count())
                .select_from(ScheduledOperationSegment)
                .join(
                    ScheduledOperation,
                    ScheduledOperation.id == ScheduledOperationSegment.scheduled_operation_id,
                )
                .where(ScheduledOperation.run_id == run.id)
            ) or 0
            return (
                run,
                len(existing),
                segment_count,
                min(item.planned_start for item in existing),
                max(item.planned_finish for item in existing),
                True,
            )
        if run.status != "CAPACITY_PROJECTED":
            raise APSRuleError("finite-capacity solve requires a CAPACITY_PROJECTED scheduling run")

        operations = self.session.scalars(
            select(PlanningOperation)
            .where(
                PlanningOperation.run_id == run.id,
                PlanningOperation.schedulable.is_(True),
            )
        ).all()
        if not operations:
            raise APSRuleError("capacity-projected run contains no schedulable operations")

        taquillas = {
            item.id: item
            for item in self.session.scalars(
                select(Taquilla).where(
                    Taquilla.id.in_({operation.taquilla_id for operation in operations})
                )
            ).all()
        }
        operations = sorted(
            operations,
            key=lambda item: (
                taquillas[item.taquilla_id].sequence_no,
                item.product_sequence_no,
                item.routing_sequence_no,
                str(item.id),
            ),
        )

        candidates_by_operation: dict[UUID, list[CapacityCandidate]] = {}
        for candidate in self.session.scalars(
            select(CapacityCandidate)
            .where(CapacityCandidate.run_id == run.id)
        ).all():
            candidates_by_operation.setdefault(candidate.planning_operation_id, []).append(candidate)

        resources = {
            resource.id: resource
            for resource in self.session.scalars(
                select(Resource).where(
                    Resource.id.in_(
                        {
                            candidate.resource_id
                            for candidates in candidates_by_operation.values()
                            for candidate in candidates
                        }
                    )
                )
            ).all()
        }

        scenario = self.get_scenario(run.scenario_id)
        predecessor_finish: dict[UUID, datetime] = {}
        occupied_by_resource: dict[UUID, list[tuple[datetime, datetime]]] = {}
        scheduled_rows: list[ScheduledOperation] = []
        segment_payloads: list[tuple[ScheduledOperation, list[dict]]] = []

        for sequence_no, operation in enumerate(operations, start=1):
            candidates = candidates_by_operation.get(operation.id, [])
            if not candidates:
                raise APSRuleError("schedulable operation has no capacity candidates")

            earliest_start = predecessor_finish.get(
                operation.product_line_id,
                scenario.horizon_start,
            )
            alternatives = []
            blocker_messages = []
            for candidate in candidates:
                resource = resources.get(candidate.resource_id)
                if resource is None:
                    raise APSNotFoundError("capacity candidate resource not found")
                try:
                    start_at, finish_at, processing_seconds, normalized_rate_uom, segments = (
                        self._candidate_schedule(
                            run=run,
                            operation=operation,
                            candidate=candidate,
                            earliest_start=earliest_start,
                            occupied_by_resource=occupied_by_resource,
                        )
                    )
                    alternatives.append(
                        (
                            finish_at,
                            start_at,
                            resource.code,
                            str(resource.id),
                            candidate,
                            processing_seconds,
                            normalized_rate_uom,
                            segments,
                        )
                    )
                except APSRuleError as exc:
                    blocker_messages.append(f"{resource.code}: {exc}")

            if not alternatives:
                detail = "; ".join(blocker_messages) or "no feasible candidate resource"
                raise APSRuleError(
                    f"operation {operation.source_operation_code} cannot be scheduled: {detail}"
                )

            alternatives.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
            (
                finish_at,
                start_at,
                _resource_code,
                _resource_id,
                selected,
                processing_seconds,
                normalized_rate_uom,
                segments,
            ) = alternatives[0]

            scheduled = ScheduledOperation(
                run_id=run.id,
                planning_operation_id=operation.id,
                resource_id=selected.resource_id,
                sequence_no=sequence_no,
                planned_start=start_at,
                planned_finish=finish_at,
                processing_seconds=processing_seconds,
                requested_quantity=operation.requested_quantity,
                nominal_rate=operation.nominal_rate,
                normalized_rate_uom=normalized_rate_uom,
                algorithm_key=run.algorithm_key,
                algorithm_version=run.algorithm_version,
            )
            scheduled_rows.append(scheduled)
            segment_payloads.append((scheduled, segments))
            predecessor_finish[operation.product_line_id] = finish_at
            occupied_by_resource.setdefault(selected.resource_id, []).extend(
                (segment["start_at"], segment["end_at"])
                for segment in segments
            )

        try:
            self.session.add_all(scheduled_rows)
            self.session.flush()
            segment_rows: list[ScheduledOperationSegment] = []
            for scheduled, segments in segment_payloads:
                for segment_no, segment in enumerate(segments, start=1):
                    segment_rows.append(
                        ScheduledOperationSegment(
                            scheduled_operation_id=scheduled.id,
                            resource_id=scheduled.resource_id,
                            availability_interval_id=segment["availability_interval_id"],
                            segment_no=segment_no,
                            start_at=segment["start_at"],
                            end_at=segment["end_at"],
                            effective_rate_per_hour=segment["effective_rate_per_hour"],
                            produced_quantity=segment["produced_quantity"],
                        )
                    )
            self.session.add_all(segment_rows)
            run.status = "SCHEDULED"
            self.session.add(run)
            self.session.commit()
            self.session.refresh(run)
        except IntegrityError as exc:
            self.session.rollback()
            raise APSConflictError("finite-capacity schedule conflicts with existing result") from exc

        return (
            run,
            len(scheduled_rows),
            len(segment_rows),
            min(item.planned_start for item in scheduled_rows),
            max(item.planned_finish for item in scheduled_rows),
            False,
        )

    def list_scheduled_operations(self, run_id: UUID) -> Sequence[ScheduledOperation]:
        return self.session.scalars(
            select(ScheduledOperation)
            .where(ScheduledOperation.run_id == run_id)
            .order_by(ScheduledOperation.sequence_no)
        ).all()

    def list_schedule_segments(self, scheduled_operation_id: UUID) -> Sequence[ScheduledOperationSegment]:
        if self.session.get(ScheduledOperation, scheduled_operation_id) is None:
            raise APSNotFoundError("scheduled operation not found")
        return self.session.scalars(
            select(ScheduledOperationSegment)
            .where(ScheduledOperationSegment.scheduled_operation_id == scheduled_operation_id)
            .order_by(ScheduledOperationSegment.segment_no)
        ).all()


    def create_replan(self, source_run_id: UUID, data: ReplanCreate, actor_id: UUID | None) -> SchedulingRun:
        source = self.session.get(SchedulingRun, source_run_id)
        if source is None:
            raise APSNotFoundError("source scheduling run not found")
        if source.status != "SCHEDULED":
            raise APSRuleError("replan requires a SCHEDULED source run")
        reason = data.reason.strip()
        if not reason:
            raise APSRuleError("replan reason is required")

        scenario = self.get_scenario(source.scenario_id)
        if scenario.status != "READY":
            raise APSRuleError("replan requires a READY scheduling scenario")

        current_publication = self.session.scalar(
            select(SchedulePublication).where(
                SchedulePublication.scenario_id == source.scenario_id,
                SchedulePublication.status == "CURRENT",
            )
        )
        if current_publication is None or current_publication.run_id != source.id:
            raise APSRuleError("replan must start from the currently published schedule")

        run_number = (
            self.session.scalar(
                select(func.max(SchedulingRun.run_number)).where(
                    SchedulingRun.scenario_id == source.scenario_id
                )
            )
            or 0
        ) + 1

        replanned = SchedulingRun(
            scenario_id=source.scenario_id,
            run_number=run_number,
            algorithm_key=(data.algorithm_key or source.algorithm_key).strip(),
            algorithm_version=(data.algorithm_version or source.algorithm_version).strip(),
            status="CREATED",
            replan_from_run_id=source.id,
            replan_reason=reason,
            created_by=actor_id,
        )
        return self._commit(replanned)

    def _schedule_fingerprint(
        self,
        operations: Sequence[ScheduledOperation],
        segments: dict[UUID, Sequence[ScheduledOperationSegment]],
    ) -> str:
        parts: list[str] = []
        for operation in sorted(operations, key=lambda item: (item.sequence_no, str(item.id))):
            parts.append(
                "|".join(
                    [
                        str(operation.id),
                        str(operation.planning_operation_id),
                        str(operation.resource_id),
                        str(operation.sequence_no),
                        operation.planned_start.isoformat(),
                        operation.planned_finish.isoformat(),
                        str(operation.processing_seconds),
                        str(operation.requested_quantity),
                        str(operation.nominal_rate),
                        operation.normalized_rate_uom,
                        operation.algorithm_key,
                        operation.algorithm_version,
                    ]
                )
            )
            for segment in sorted(
                segments.get(operation.id, []),
                key=lambda item: (item.segment_no, str(item.id)),
            ):
                parts.append(
                    "|".join(
                        [
                            str(segment.id),
                            str(segment.resource_id),
                            str(segment.segment_no),
                            segment.start_at.isoformat(),
                            segment.end_at.isoformat(),
                            str(segment.effective_rate_per_hour),
                            str(segment.produced_quantity),
                        ]
                    )
                )
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def publish_schedule(
        self,
        run_id: UUID,
        publish_reason: str | None,
        actor_id: UUID | None,
    ) -> tuple[SchedulePublication, UUID | None, bool]:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("scheduling run not found")
        if run.status != "SCHEDULED":
            raise APSRuleError("only SCHEDULED runs can be published")

        existing = self.session.scalar(
            select(SchedulePublication).where(SchedulePublication.run_id == run.id)
        )
        if existing is not None:
            return existing, existing.supersedes_publication_id, True

        scenario = self.get_scenario(run.scenario_id)
        if scenario.status != "READY":
            raise APSRuleError("publishing requires a READY scheduling scenario")

        operations = self.session.scalars(
            select(ScheduledOperation)
            .where(ScheduledOperation.run_id == run.id)
            .order_by(ScheduledOperation.sequence_no, ScheduledOperation.id)
        ).all()
        if not operations:
            raise APSRuleError("scheduled run has no operations to publish")

        segment_map: dict[UUID, Sequence[ScheduledOperationSegment]] = {}
        for operation in operations:
            segment_map[operation.id] = self.session.scalars(
                select(ScheduledOperationSegment)
                .where(ScheduledOperationSegment.scheduled_operation_id == operation.id)
                .order_by(ScheduledOperationSegment.segment_no, ScheduledOperationSegment.id)
            ).all()
            if not segment_map[operation.id]:
                raise APSRuleError("scheduled operation has no productive segments to publish")

        fingerprint = self._schedule_fingerprint(operations, segment_map)
        current = self.session.scalar(
            select(SchedulePublication).where(
                SchedulePublication.scenario_id == run.scenario_id,
                SchedulePublication.status == "CURRENT",
            )
        )

        if current is not None:
            if run.replan_from_run_id is None:
                raise APSRuleError("publishing over an existing schedule requires a controlled replan")
            if current.run_id != run.replan_from_run_id:
                raise APSRuleError("replan source is not the currently published schedule")
        elif run.replan_from_run_id is not None:
            raise APSRuleError("replan source publication is missing")

        version_no = (
            self.session.scalar(
                select(func.max(SchedulePublication.version_no)).where(
                    SchedulePublication.scenario_id == run.scenario_id
                )
            )
            or 0
        ) + 1

        publication = SchedulePublication(
            scenario_id=run.scenario_id,
            run_id=run.id,
            version_no=version_no,
            status="CURRENT",
            supersedes_publication_id=current.id if current else None,
            publish_reason=publish_reason.strip() if publish_reason and publish_reason.strip() else None,
            schedule_fingerprint=fingerprint,
            published_by=actor_id,
        )

        try:
            if current is not None:
                current.status = "SUPERSEDED"
                self.session.add(current)
                self.session.flush()

            self.session.add(publication)
            self.session.flush()

            for operation in operations:
                published_operation = PublishedScheduledOperation(
                    publication_id=publication.id,
                    source_scheduled_operation_id=operation.id,
                    planning_operation_id=operation.planning_operation_id,
                    resource_id=operation.resource_id,
                    sequence_no=operation.sequence_no,
                    planned_start=operation.planned_start,
                    planned_finish=operation.planned_finish,
                    processing_seconds=operation.processing_seconds,
                    requested_quantity=operation.requested_quantity,
                    nominal_rate=operation.nominal_rate,
                    normalized_rate_uom=operation.normalized_rate_uom,
                    algorithm_key=operation.algorithm_key,
                    algorithm_version=operation.algorithm_version,
                )
                self.session.add(published_operation)
                self.session.flush()
                for segment in segment_map.get(operation.id, []):
                    self.session.add(
                        PublishedScheduledOperationSegment(
                            published_operation_id=published_operation.id,
                            source_segment_id=segment.id,
                            resource_id=segment.resource_id,
                            segment_no=segment.segment_no,
                            start_at=segment.start_at,
                            end_at=segment.end_at,
                            effective_rate_per_hour=segment.effective_rate_per_hour,
                            produced_quantity=segment.produced_quantity,
                        )
                    )

            self.session.commit()
            self.session.refresh(publication)
        except IntegrityError as exc:
            self.session.rollback()
            raise APSConflictError("schedule publication conflicts with existing lifecycle state") from exc

        return publication, current.id if current else None, False

    def list_publications(self, scenario_id: UUID) -> Sequence[SchedulePublication]:
        self.get_scenario(scenario_id)
        return self.session.scalars(
            select(SchedulePublication)
            .where(SchedulePublication.scenario_id == scenario_id)
            .order_by(SchedulePublication.version_no)
        ).all()

    def get_publication(self, publication_id: UUID) -> SchedulePublication:
        publication = self.session.get(SchedulePublication, publication_id)
        if publication is None:
            raise APSNotFoundError("schedule publication not found")
        return publication


    def list_published_operations(self, publication_id: UUID) -> Sequence[PublishedScheduledOperation]:
        self.get_publication(publication_id)
        return self.session.scalars(
            select(PublishedScheduledOperation)
            .where(PublishedScheduledOperation.publication_id == publication_id)
            .order_by(PublishedScheduledOperation.sequence_no)
        ).all()


    def compare_replan_to_published(self, run_id: UUID) -> dict:
        run = self.session.get(SchedulingRun, run_id)
        if run is None:
            raise APSNotFoundError("candidate scheduling run not found")
        if run.status != "SCHEDULED":
            raise APSRuleError("schedule comparison requires a SCHEDULED candidate run")
        if run.replan_from_run_id is None:
            raise APSRuleError("schedule comparison requires a controlled replan")

        source_publication = self.session.scalar(
            select(SchedulePublication).where(
                SchedulePublication.run_id == run.replan_from_run_id
            )
        )
        if source_publication is None:
            raise APSRuleError("source run has no published schedule")

        baseline_rows = self.session.scalars(
            select(PublishedScheduledOperation)
            .where(PublishedScheduledOperation.publication_id == source_publication.id)
            .order_by(PublishedScheduledOperation.sequence_no)
        ).all()
        candidate_rows = self.session.scalars(
            select(ScheduledOperation)
            .where(ScheduledOperation.run_id == run.id)
            .order_by(ScheduledOperation.sequence_no)
        ).all()
        if not baseline_rows or not candidate_rows:
            raise APSRuleError("schedule comparison requires non-empty baseline and candidate schedules")

        def provenance_key(planning_operation_id: UUID) -> tuple[UUID, UUID]:
            planning = self.session.get(PlanningOperation, planning_operation_id)
            if planning is None:
                raise APSNotFoundError("planning operation provenance not found")
            return planning.product_line_id, planning.routing_operation_id

        baseline = {provenance_key(item.planning_operation_id): item for item in baseline_rows}
        candidate = {provenance_key(item.planning_operation_id): item for item in candidate_rows}
        baseline_keys = set(baseline)
        candidate_keys = set(candidate)
        common = baseline_keys & candidate_keys

        timing_changed = 0
        resource_changed = 0
        for key in common:
            before = baseline[key]
            after = candidate[key]
            if before.planned_start != after.planned_start or before.planned_finish != after.planned_finish:
                timing_changed += 1
            if before.resource_id != after.resource_id:
                resource_changed += 1

        baseline_start = min(item.planned_start for item in baseline_rows)
        baseline_finish = max(item.planned_finish for item in baseline_rows)
        candidate_start = min(item.planned_start for item in candidate_rows)
        candidate_finish = max(item.planned_finish for item in candidate_rows)

        baseline_makespan = Decimal(str((baseline_finish - baseline_start).total_seconds()))
        candidate_makespan = Decimal(str((candidate_finish - candidate_start).total_seconds()))

        return {
            "source_publication_id": source_publication.id,
            "source_run_id": run.replan_from_run_id,
            "candidate_run_id": run.id,
            "baseline_operation_count": len(baseline_rows),
            "candidate_operation_count": len(candidate_rows),
            "added_operation_count": len(candidate_keys - baseline_keys),
            "removed_operation_count": len(baseline_keys - candidate_keys),
            "timing_changed_count": timing_changed,
            "resource_changed_count": resource_changed,
            "baseline_start": baseline_start,
            "baseline_finish": baseline_finish,
            "candidate_start": candidate_start,
            "candidate_finish": candidate_finish,
            "makespan_delta_seconds": candidate_makespan - baseline_makespan,
        }
