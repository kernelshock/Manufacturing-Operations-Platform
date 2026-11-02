import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.aps.capacity_models import CapacityCandidate
from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.service import APSService
from mop.config import Settings
from mop.core.models import Area, Organization, Plant, Resource, WorkCenter
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import (
    Article,
    ArticleRevision,
    CalendarWeeklyWindow,
    ManufacturingCalendar,
    ResourceAssignment,
    RoutingOperation,
    RoutingRevision,
)
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_capacity_projection_preserves_lunch_gap() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with database.session() as session:
        org = Organization(code=f"G43-ORG-{suffix}", name="G4.3 Org")
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
        resource = Resource(
            work_center_id=wc.id,
            code=f"R-{suffix}",
            name="Resource",
            resource_type="machine",
            active=True,
        )
        session.add(resource)
        session.flush()

        calendar = ManufacturingCalendar(
            code=f"CAL-{suffix}",
            name="FAIC shift",
            revision_no=1,
            timezone="America/Argentina/Cordoba",
            plant_id=plant.id,
            valid_from=date(2026, 11, 1),
            status="ACTIVE",
        )
        session.add(calendar)
        session.flush()
        session.add_all(
            [
                CalendarWeeklyWindow(
                    calendar_id=calendar.id,
                    weekday=0,
                    start_minute=420,
                    end_minute=720,
                    spans_midnight=False,
                    capacity_factor=Decimal("1"),
                    active=True,
                ),
                CalendarWeeklyWindow(
                    calendar_id=calendar.id,
                    weekday=0,
                    start_minute=750,
                    end_minute=960,
                    spans_midnight=False,
                    capacity_factor=Decimal("1"),
                    active=True,
                ),
            ]
        )

        article = Article(
            external_system="TEST",
            external_code=f"ART-{suffix}",
            canonical_description="G4.3 product",
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
        routing_op = RoutingOperation(
            routing_revision_id=routing.id,
            source_operation_code="OP10",
            sequence_no=10,
            source_description="Operation",
            area_id=area.id,
            work_center_id=wc.id,
            operation_kind="PHYSICAL_PRODUCTION",
            schedulable=True,
            completion_marker=False,
            active=True,
        )
        session.add(routing_op)
        session.flush()
        assignment = ResourceAssignment(
            routing_operation_id=routing_op.id,
            resource_id=resource.id,
            principal=True,
            capacity_factor=Decimal("1"),
        )
        session.add(assignment)

        plan = ProductionPlan(plan_number=f"PLAN-{suffix}", status="DRAFT")
        session.add(plan)
        session.flush()
        taquilla = Taquilla(
            plan_id=plan.id,
            taquilla_code=f"TQ-{suffix}",
            sequence_no=1,
            vehicle_topology="SIMPLE",
            status="READY",
        )
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

        scenario = SchedulingScenario(
            plan_id=plan.id,
            scenario_code=f"SC-{suffix}",
            name="Capacity projection",
            horizon_start=datetime.fromisoformat("2026-11-02T07:00:00-03:00"),
            horizon_end=datetime.fromisoformat("2026-11-02T16:00:00-03:00"),
            planning_timezone="America/Argentina/Cordoba",
            status="READY",
        )
        session.add(scenario)
        session.flush()
        run = SchedulingRun(
            scenario_id=scenario.id,
            run_number=1,
            algorithm_key="g4.3-test",
            algorithm_version="1",
            status="EXPANDED",
            operation_count=1,
        )
        session.add(run)
        session.flush()
        planning_op = PlanningOperation(
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
            routing_sequence_no=10,
            source_operation_code="OP10",
            source_description="Operation",
            operation_kind="PHYSICAL_PRODUCTION",
            schedulable=True,
            completion_marker=False,
            area_id=area.id,
            work_center_id=wc.id,
            routing_source_fingerprint=routing.source_fingerprint,
        )
        session.add(planning_op)
        session.commit()

        projected, candidate_count, interval_count, replay = APSService(session).project_capacity(run.id)
        assert projected.status == "CAPACITY_PROJECTED"
        assert candidate_count == 1
        assert interval_count == 2
        assert replay is False

        candidates = list(APSService(session).list_capacity_candidates(run.id))
        assert len(candidates) == 1
        assert candidates[0].source_mode == "EXPLICIT_ASSIGNMENT"
        assert candidates[0].resource_id == resource.id

        intervals = list(APSService(session).list_resource_availability(run.id))
        assert len(intervals) == 2
        assert intervals[0].end_at < intervals[1].start_at

        replayed, _, _, replay_flag = APSService(session).project_capacity(run.id)
        assert replayed.id == run.id
        assert replay_flag is True
