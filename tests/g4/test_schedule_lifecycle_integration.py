import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from mop.aps.capacity_models import ResourceAvailabilityInterval
from mop.aps.lifecycle_models import SchedulePublication
from mop.aps.lifecycle_schemas import ReplanCreate
from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.schedule_models import ScheduledOperation, ScheduledOperationSegment
from mop.aps.service import APSRuleError, APSService
from mop.config import Settings
from mop.core.models import Area, Organization, Plant, Resource, WorkCenter
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import Article, ArticleRevision, ManufacturingCalendar, RoutingOperation, RoutingRevision
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_publish_replan_supersede_preserves_immutable_history() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with database.session() as session:
        org = Organization(code=f"G45-ORG-{suffix}", name="G4.5 Org")
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
            canonical_description="G4.5 product",
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

        scenario = SchedulingScenario(
            plan_id=plan.id,
            scenario_code=f"SC-{suffix}",
            name="Publication lifecycle",
            horizon_start=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
            horizon_end=datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc),
            planning_timezone="America/Argentina/Cordoba",
            status="READY",
        )
        session.add(scenario)
        session.flush()

        def add_scheduled_run(run: SchedulingRun, start_at: datetime) -> None:
            session.add(run)
            session.flush()
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
            availability = ResourceAvailabilityInterval(
                run_id=run.id,
                resource_id=resource.id,
                calendar_id=calendar.id,
                calendar_code=calendar.code,
                calendar_revision_no=1,
                target_scope="plant",
                timezone=calendar.timezone,
                start_at=start_at,
                end_at=start_at + timedelta(hours=4),
                calendar_capacity_factor=Decimal("1"),
                source="WEEKLY_WINDOW",
            )
            session.add(availability)
            session.flush()
            scheduled = ScheduledOperation(
                run_id=run.id,
                planning_operation_id=planning.id,
                resource_id=resource.id,
                sequence_no=1,
                planned_start=start_at,
                planned_finish=start_at + timedelta(hours=1),
                processing_seconds=Decimal("3600"),
                requested_quantity=Decimal("10"),
                nominal_rate=Decimal("10"),
                normalized_rate_uom="UNITS_PER_HOUR",
                algorithm_key=run.algorithm_key,
                algorithm_version=run.algorithm_version,
            )
            session.add(scheduled)
            session.flush()
            session.add(
                ScheduledOperationSegment(
                    scheduled_operation_id=scheduled.id,
                    resource_id=resource.id,
                    availability_interval_id=availability.id,
                    segment_no=1,
                    start_at=start_at,
                    end_at=start_at + timedelta(hours=1),
                    effective_rate_per_hour=Decimal("10"),
                    produced_quantity=Decimal("10"),
                )
            )
            session.commit()

        run1 = SchedulingRun(
            scenario_id=scenario.id,
            run_number=1,
            algorithm_key="earliest-finish-deterministic",
            algorithm_version="g4.4",
            status="SCHEDULED",
            operation_count=1,
        )
        start1 = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
        add_scheduled_run(run1, start1)

        aps = APSService(session)
        publication1, superseded1, replay1 = aps.publish_schedule(run1.id, "Initial production schedule", None)
        assert publication1.version_no == 1
        assert publication1.status == "CURRENT"
        assert superseded1 is None
        assert replay1 is False
        snapshot1 = list(aps.list_published_operations(publication1.id))
        assert snapshot1[0].planned_start == start1

        replan = aps.create_replan(
            run1.id,
            ReplanCreate(reason="Capacity adjustment after planning review"),
            None,
        )
        assert replan.status == "CREATED"
        assert replan.replan_from_run_id == run1.id
        assert replan.replan_reason == "Capacity adjustment after planning review"

        replan.status = "SCHEDULED"
        replan.operation_count = 1
        session.add(replan)
        session.commit()
        start2 = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        add_scheduled_run(replan, start2)

        publication2, superseded2, replay2 = aps.publish_schedule(replan.id, "Approved replan", None)
        assert publication2.version_no == 2
        assert publication2.status == "CURRENT"
        assert publication2.supersedes_publication_id == publication1.id
        assert superseded2 == publication1.id
        assert replay2 is False

        session.refresh(publication1)
        assert publication1.status == "SUPERSEDED"
        assert list(aps.list_published_operations(publication1.id))[0].planned_start == start1
        assert list(aps.list_published_operations(publication2.id))[0].planned_start == start2

        replayed, _, replay_flag = aps.publish_schedule(replan.id, "Ignored replay reason", None)
        assert replayed.id == publication2.id
        assert replay_flag is True

        with pytest.raises(APSRuleError):
            aps.cancel_run(run1.id)

        history = list(aps.list_publications(scenario.id))
        assert [(item.version_no, item.status) for item in history] == [
            (1, "SUPERSEDED"),
            (2, "CURRENT"),
        ]
