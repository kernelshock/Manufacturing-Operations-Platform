import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.aps.capacity_models import CapacityCandidate, ResourceAvailabilityInterval
from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.service import APSService
from mop.config import Settings
from mop.core.models import Area, Organization, Plant, Resource, WorkCenter
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import Article, ArticleRevision, ManufacturingCalendar, RoutingOperation, RoutingRevision
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_solver_respects_lunch_precedence_and_finite_resource_capacity() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with database.session() as session:
        org = Organization(code=f"G44-ORG-{suffix}", name="G4.4 Org")
        session.add(org)
        session.flush()
        plant = Plant(organization_id=org.id, code=f"P-{suffix}", name="Plant")
        session.add(plant)
        session.flush()
        area = Area(plant_id=plant.id, code=f"A-{suffix}", name="Area")
        session.add(area)
        session.flush()
        wc = WorkCenter(area_id=area.id, code=f"WC-{suffix}", name="WC")
        session.add(wc)
        session.flush()
        resource = Resource(work_center_id=wc.id, code=f"R-{suffix}", name="Resource", resource_type="machine", active=True)
        session.add(resource)
        session.flush()

        calendar = ManufacturingCalendar(
            code=f"CAL-{suffix}",
            name="Shift",
            revision_no=1,
            timezone="America/Argentina/Cordoba",
            plant_id=plant.id,
            valid_from=date(2026, 11, 1),
            status="ACTIVE",
        )
        session.add(calendar)
        session.flush()

        article = Article(
            external_system="TEST",
            external_code=f"ART-{suffix}",
            canonical_description="G4.4 product",
            article_kind="FINISHED_PRODUCT",
            active=True,
        )
        session.add(article)
        session.flush()
        revision = ArticleRevision(
            article_id=article.id,
            source_fingerprint="a" * 64,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="ACTIVE",
        )
        session.add(revision)
        session.flush()
        routing = RoutingRevision(
            article_revision_id=revision.id,
            revision_no=1,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="ACTIVE",
            source_system="TEST",
            source_fingerprint="b" * 64,
        )
        session.add(routing)
        session.flush()
        routing_ops = [
            RoutingOperation(
                routing_revision_id=routing.id,
                source_operation_code=code,
                sequence_no=sequence,
                source_description=code,
                area_id=area.id,
                work_center_id=wc.id,
                operation_kind="PHYSICAL_PRODUCTION",
                schedulable=True,
                completion_marker=False,
                nominal_rate=Decimal("20"),
                rate_uom="UNITS/HOUR",
                active=True,
            )
            for code, sequence in (("OP10", 10), ("OP20", 20))
        ]
        session.add_all(routing_ops)
        session.flush()

        plan = ProductionPlan(plan_number=f"PLAN-{suffix}", status="DRAFT")
        session.add(plan)
        session.flush()
        taquilla = Taquilla(plan_id=plan.id, taquilla_code=f"TQ-{suffix}", sequence_no=1, vehicle_topology="SIMPLE", status="READY")
        session.add(taquilla)
        session.flush()
        line = TaquillaProductLine(
            taquilla_id=taquilla.id,
            article_id=article.id,
            sequence_no=1,
            requested_quantity=Decimal("10"),
            deck_position="SINGLE",
        )
        session.add(line)
        session.flush()

        horizon_start = datetime(2026, 11, 2, 14, 45, tzinfo=timezone.utc)
        horizon_end = datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc)
        scenario = SchedulingScenario(
            plan_id=plan.id,
            scenario_code=f"SC-{suffix}",
            name="Finite schedule",
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            planning_timezone="America/Argentina/Cordoba",
            status="READY",
        )
        session.add(scenario)
        session.flush()
        run = SchedulingRun(
            scenario_id=scenario.id,
            run_number=1,
            algorithm_key="earliest-finish-deterministic",
            algorithm_version="g4.4",
            status="CAPACITY_PROJECTED",
            operation_count=2,
        )
        session.add(run)
        session.flush()

        planning_ops = []
        for routing_op in routing_ops:
            planning = PlanningOperation(
                run_id=run.id,
                plan_id=plan.id,
                taquilla_id=taquilla.id,
                product_line_id=line.id,
                article_id=article.id,
                routing_revision_id=routing.id,
                routing_operation_id=routing_op.id,
                requested_quantity=Decimal("10"),
                deck_position="SINGLE",
                product_sequence_no=1,
                routing_sequence_no=routing_op.sequence_no,
                source_operation_code=routing_op.source_operation_code,
                source_description=routing_op.source_description,
                operation_kind="PHYSICAL_PRODUCTION",
                schedulable=True,
                completion_marker=False,
                area_id=area.id,
                work_center_id=wc.id,
                nominal_rate=Decimal("20"),
                rate_uom="UNITS/HOUR",
                routing_source_fingerprint=routing.source_fingerprint,
            )
            session.add(planning)
            session.flush()
            planning_ops.append(planning)
            session.add(
                CapacityCandidate(
                    run_id=run.id,
                    planning_operation_id=planning.id,
                    routing_operation_id=routing_op.id,
                    resource_id=resource.id,
                    source_mode="WORK_CENTER_POOL",
                    assignment_capacity_factor=Decimal("1"),
                )
            )

        morning = ResourceAvailabilityInterval(
            run_id=run.id,
            resource_id=resource.id,
            calendar_id=calendar.id,
            calendar_code=calendar.code,
            calendar_revision_no=1,
            target_scope="plant",
            timezone=calendar.timezone,
            start_at=datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc),
            calendar_capacity_factor=Decimal("1"),
            source="WEEKLY_WINDOW",
        )
        afternoon = ResourceAvailabilityInterval(
            run_id=run.id,
            resource_id=resource.id,
            calendar_id=calendar.id,
            calendar_code=calendar.code,
            calendar_revision_no=1,
            target_scope="plant",
            timezone=calendar.timezone,
            start_at=datetime(2026, 11, 2, 15, 30, tzinfo=timezone.utc),
            end_at=horizon_end,
            calendar_capacity_factor=Decimal("1"),
            source="WEEKLY_WINDOW",
        )
        session.add_all([morning, afternoon])
        session.commit()

        solved, operation_count, segment_count, makespan_start, makespan_finish, replay = APSService(session).solve_finite_capacity(run.id)

        assert solved.status == "SCHEDULED"
        assert operation_count == 2
        assert segment_count == 3
        assert replay is False
        assert makespan_start == horizon_start
        assert makespan_finish == datetime(2026, 11, 2, 16, 15, tzinfo=timezone.utc)

        schedule = list(APSService(session).list_scheduled_operations(run.id))
        assert [item.planning_operation_id for item in schedule] == [planning_ops[0].id, planning_ops[1].id]
        assert schedule[0].planned_start == horizon_start
        assert schedule[0].planned_finish == datetime(2026, 11, 2, 15, 45, tzinfo=timezone.utc)
        assert schedule[1].planned_start == schedule[0].planned_finish
        assert schedule[1].planned_finish == datetime(2026, 11, 2, 16, 15, tzinfo=timezone.utc)

        first_segments = list(APSService(session).list_schedule_segments(schedule[0].id))
        assert len(first_segments) == 2
        assert first_segments[0].end_at == datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
        assert first_segments[1].start_at == datetime(2026, 11, 2, 15, 30, tzinfo=timezone.utc)

        replayed, _, _, _, _, replay_flag = APSService(session).solve_finite_capacity(run.id)
        assert replayed.id == run.id
        assert replay_flag is True
