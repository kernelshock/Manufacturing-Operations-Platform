import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.aps.capacity_models import CapacityCandidate, ResourceAvailabilityInterval
from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.schedule_models import ScheduledOperation, ScheduledOperationSegment
from mop.aps.service import APSService
from mop.aps.whatif_schemas import WhatIfCreate, WhatIfExceptionCreate
from mop.config import Settings
from mop.core.models import Area, Organization, Plant, Resource, WorkCenter
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import Article, ArticleRevision, ManufacturingCalendar, RoutingOperation, RoutingRevision
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_blackout_evaluation_isolated_until_explicit_apply() -> None:
    database = DatabaseManager(Settings(environment="test", _env_file=None).database_url)
    suffix = uuid4().hex[:8].upper()

    with database.session() as session:
        org = Organization(code=f"G47-ORG-{suffix}", name="G4.7 Org")
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
            name="Calendar",
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
            canonical_description="What-if product",
            article_kind="FINISHED_PRODUCT",
            active=True,
        )
        session.add(article)
        session.flush()
        article_revision = ArticleRevision(
            article_id=article.id,
            source_fingerprint="a" * 64,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="ACTIVE",
        )
        session.add(article_revision)
        session.flush()
        routing = RoutingRevision(
            article_revision_id=article_revision.id,
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
            nominal_rate=Decimal("10"),
            rate_uom="UNITS/HOUR",
            active=True,
        )
        session.add(routing_op)
        session.flush()

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

        horizon_start = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
        horizon_end = datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc)
        scheduling_scenario = SchedulingScenario(
            plan_id=plan.id,
            scenario_code=f"SC-{suffix}",
            name="What-if baseline",
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            planning_timezone="America/Argentina/Cordoba",
            status="READY",
        )
        session.add(scheduling_scenario)
        session.flush()

        baseline_run = SchedulingRun(
            scenario_id=scheduling_scenario.id,
            run_number=1,
            algorithm_key="earliest-finish-deterministic",
            algorithm_version="g4.4",
            status="SCHEDULED",
            operation_count=1,
        )
        session.add(baseline_run)
        session.flush()

        planning = PlanningOperation(
            run_id=baseline_run.id,
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
            nominal_rate=Decimal("10"),
            rate_uom="UNITS/HOUR",
            routing_source_fingerprint=routing.source_fingerprint,
        )
        session.add(planning)
        session.flush()

        candidate = CapacityCandidate(
            run_id=baseline_run.id,
            planning_operation_id=planning.id,
            routing_operation_id=routing_op.id,
            resource_id=resource.id,
            source_mode="WORK_CENTER_POOL",
            assignment_capacity_factor=Decimal("1"),
        )
        availability = ResourceAvailabilityInterval(
            run_id=baseline_run.id,
            resource_id=resource.id,
            calendar_id=calendar.id,
            calendar_code=calendar.code,
            calendar_revision_no=1,
            target_scope="plant",
            timezone=calendar.timezone,
            start_at=horizon_start,
            end_at=horizon_end,
            calendar_capacity_factor=Decimal("1"),
            source="WEEKLY_WINDOW",
        )
        session.add_all([candidate, availability])
        session.flush()

        scheduled = ScheduledOperation(
            run_id=baseline_run.id,
            planning_operation_id=planning.id,
            resource_id=resource.id,
            sequence_no=1,
            planned_start=horizon_start,
            planned_finish=horizon_start + timedelta(hours=1),
            processing_seconds=Decimal("3600"),
            requested_quantity=Decimal("10"),
            nominal_rate=Decimal("10"),
            normalized_rate_uom="UNITS_PER_HOUR",
            algorithm_key=baseline_run.algorithm_key,
            algorithm_version=baseline_run.algorithm_version,
        )
        session.add(scheduled)
        session.flush()
        session.add(
            ScheduledOperationSegment(
                scheduled_operation_id=scheduled.id,
                resource_id=resource.id,
                availability_interval_id=availability.id,
                segment_no=1,
                start_at=horizon_start,
                end_at=horizon_start + timedelta(hours=1),
                effective_rate_per_hour=Decimal("10"),
                produced_quantity=Decimal("10"),
            )
        )
        session.commit()

        aps = APSService(session)
        baseline_publication, _, _ = aps.publish_schedule(
            baseline_run.id,
            "Baseline",
            None,
        )

        whatif = aps.create_whatif(
            WhatIfCreate(
                scenario_code=f"WI-{suffix}",
                name="Resource blackout",
                baseline_publication_id=baseline_publication.id,
            ),
            None,
        )
        aps.add_whatif_exception(
            whatif.id,
            WhatIfExceptionCreate(
                exception_type="RESOURCE_BLACKOUT",
                resource_id=resource.id,
                start_at=horizon_start,
                end_at=horizon_start + timedelta(hours=1),
                reason="Hypothetical outage",
            ),
        )

        evaluated, comparison = aps.evaluate_whatif(whatif.id, None)
        assert evaluated.status == "EVALUATED"
        assert evaluated.candidate_run_id is not None
        assert comparison["timing_changed_count"] == 1
        assert comparison["exception_count"] == 1

        session.refresh(baseline_publication)
        assert baseline_publication.status == "CURRENT"

        candidate_schedule = list(
            aps.list_scheduled_operations(evaluated.candidate_run_id)
        )
        assert candidate_schedule[0].planned_start == horizon_start + timedelta(hours=1)
        assert candidate_schedule[0].planned_finish == horizon_start + timedelta(hours=2)

        applied, new_publication, superseded_id = aps.apply_whatif(evaluated.id, None)
        assert applied.status == "APPLIED"
        assert superseded_id == baseline_publication.id
        assert new_publication.status == "CURRENT"

        session.refresh(baseline_publication)
        assert baseline_publication.status == "SUPERSEDED"
