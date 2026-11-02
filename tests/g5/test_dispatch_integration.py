import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.aps.capacity_models import ResourceAvailabilityInterval
from mop.aps.lifecycle_models import SchedulePublication
from mop.aps.models import SchedulingRun, SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.aps.schedule_models import ScheduledOperation, ScheduledOperationSegment
from mop.aps.service import APSService
from mop.config import Settings
from mop.core.models import Area, Organization, Plant, Resource, WorkCenter
from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import (
    Article,
    ArticleRevision,
    ManufacturingCalendar,
    RoutingOperation,
    RoutingRevision,
)
from mop.mes.schemas import ExecutionDispatchCreate
from mop.mes.service import MESRuleError, MESService
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_current_publication_materializes_idempotent_dispatch_and_requires_current_on_release() -> None:
    database = DatabaseManager(Settings(environment="test", _env_file=None).database_url)
    suffix = uuid4().hex[:8].upper()

    with database.session() as session:
        org = Organization(code=f"G51-ORG-{suffix}", name="G5.1 Org")
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
            canonical_description="G5.1 product",
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
        product_line = TaquillaProductLine(
            taquilla_id=taquilla.id,
            article_id=article.id,
            sequence_no=1,
            requested_quantity=Decimal("10"),
            deck_position="SINGLE",
        )
        session.add(product_line)
        session.flush()

        scenario = SchedulingScenario(
            plan_id=plan.id,
            scenario_code=f"SC-{suffix}",
            name="G5.1 source schedule",
            horizon_start=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
            horizon_end=datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc),
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
            status="SCHEDULED",
            operation_count=1,
        )
        session.add(run)
        session.flush()

        planning = PlanningOperation(
            run_id=run.id,
            plan_id=plan.id,
            taquilla_id=taquilla.id,
            product_line_id=product_line.id,
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

        start_at = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
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

        publication, _, _ = APSService(session).publish_schedule(
            run.id,
            "G5.1 dispatch baseline",
            None,
        )
        assert publication.status == "CURRENT"

        mes = MESService(session)
        payload = ExecutionDispatchCreate(
            publication_id=publication.id,
            dispatch_code=f"DISP-{suffix}",
        )
        dispatch, count, replay = mes.create_dispatch(payload, None)
        assert replay is False
        assert count == 1
        assert dispatch.status == "DRAFT"
        assert dispatch.publication_id == publication.id
        assert dispatch.plan_id == plan.id
        assert dispatch.schedule_fingerprint == publication.schedule_fingerprint

        operations = list(mes.list_operations(dispatch.id))
        assert len(operations) == 1
        operation = operations[0]
        assert operation.status == "PENDING"
        assert operation.plan_id == plan.id
        assert operation.taquilla_id == taquilla.id
        assert operation.product_line_id == product_line.id
        assert operation.routing_revision_id == routing.id
        assert operation.routing_operation_id == routing_op.id
        assert operation.planned_resource_id == resource.id
        assert operation.planned_start == start_at
        assert operation.planned_finish == start_at + timedelta(hours=1)
        assert operation.requested_quantity == Decimal("10")

        replayed, replay_count, replay_flag = mes.create_dispatch(payload, None)
        assert replayed.id == dispatch.id
        assert replay_count == 1
        assert replay_flag is True

        publication.status = "SUPERSEDED"
        session.add(publication)
        session.commit()
        with pytest.raises(MESRuleError):
            mes.release_dispatch(dispatch.id)

        publication.status = "CURRENT"
        session.add(publication)
        session.commit()
        released = mes.release_dispatch(dispatch.id)
        assert released.status == "RELEASED"
        assert released.released_at is not None

        released_again = mes.release_dispatch(dispatch.id)
        assert released_again.id == released.id
        assert released_again.status == "RELEASED"

        history = session.get(SchedulePublication, publication.id)
        assert history is not None
        assert history.status == "CURRENT"
