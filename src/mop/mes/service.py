"""Application service for G5.1 MES execution dispatch foundation."""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.aps.lifecycle_models import SchedulePublication, PublishedScheduledOperation
from mop.aps.models import SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.mes.models import ExecutionDispatch, ExecutionOperation
from mop.mes.schemas import ExecutionDispatchCreate


class MESConflictError(ValueError):
    pass


class MESRuleError(ValueError):
    pass


class MESNotFoundError(LookupError):
    pass


class MESService:
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
            raise MESConflictError("MES identity already exists") from exc

    def get_dispatch(self, dispatch_id: UUID) -> ExecutionDispatch:
        dispatch = self.session.get(ExecutionDispatch, dispatch_id)
        if dispatch is None:
            raise MESNotFoundError("execution dispatch not found")
        return dispatch

    def list_dispatches(
        self,
        *,
        plan_id: UUID | None = None,
        status: str | None = None,
    ) -> Sequence[ExecutionDispatch]:
        query = select(ExecutionDispatch)
        if plan_id is not None:
            query = query.where(ExecutionDispatch.plan_id == plan_id)
        if status is not None:
            query = query.where(ExecutionDispatch.status == status)
        return self.session.scalars(
            query.order_by(ExecutionDispatch.created_at.desc(), ExecutionDispatch.dispatch_code)
        ).all()

    def list_operations(self, dispatch_id: UUID) -> Sequence[ExecutionOperation]:
        self.get_dispatch(dispatch_id)
        return self.session.scalars(
            select(ExecutionOperation)
            .where(ExecutionOperation.dispatch_id == dispatch_id)
            .order_by(
                ExecutionOperation.taquilla_id,
                ExecutionOperation.product_sequence_no,
                ExecutionOperation.routing_sequence_no,
                ExecutionOperation.id,
            )
        ).all()

    def create_dispatch(
        self,
        data: ExecutionDispatchCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionDispatch, int, bool]:
        publication = self.session.get(SchedulePublication, data.publication_id)
        if publication is None:
            raise MESNotFoundError("schedule publication not found")
        if publication.status != "CURRENT":
            raise MESRuleError("execution dispatch can only be created from a CURRENT publication")

        existing = self.session.scalar(
            select(ExecutionDispatch).where(
                ExecutionDispatch.publication_id == publication.id
            )
        )
        if existing is not None:
            if existing.dispatch_code != data.dispatch_code.strip():
                raise MESConflictError(
                    "CURRENT publication already has an execution dispatch with a different dispatch_code"
                )
            count = len(self.list_operations(existing.id))
            return existing, count, True

        scenario = self.session.get(SchedulingScenario, publication.scenario_id)
        if scenario is None:
            raise MESNotFoundError("publication scheduling scenario not found")

        rows = self.session.execute(
            select(PublishedScheduledOperation, PlanningOperation)
            .join(
                PlanningOperation,
                PlanningOperation.id == PublishedScheduledOperation.planning_operation_id,
            )
            .where(PublishedScheduledOperation.publication_id == publication.id)
            .order_by(
                PlanningOperation.taquilla_id,
                PlanningOperation.product_sequence_no,
                PlanningOperation.routing_sequence_no,
                PublishedScheduledOperation.sequence_no,
            )
        ).all()
        if not rows:
            raise MESRuleError("CURRENT publication has no published operations to dispatch")

        dispatch = ExecutionDispatch(
            dispatch_code=data.dispatch_code.strip(),
            publication_id=publication.id,
            scenario_id=publication.scenario_id,
            run_id=publication.run_id,
            plan_id=scenario.plan_id,
            publication_version_no=publication.version_no,
            schedule_fingerprint=publication.schedule_fingerprint,
            operation_count=len(rows),
            status="DRAFT",
            created_by=actor_id,
        )
        try:
            self.session.add(dispatch)
            self.session.flush()

            operations = []
            for published, planning in rows:
                operations.append(
                    ExecutionOperation(
                        dispatch_id=dispatch.id,
                        publication_id=publication.id,
                        published_operation_id=published.id,
                        planning_operation_id=planning.id,
                        plan_id=planning.plan_id,
                        taquilla_id=planning.taquilla_id,
                        product_line_id=planning.product_line_id,
                        article_id=planning.article_id,
                        routing_revision_id=planning.routing_revision_id,
                        routing_operation_id=planning.routing_operation_id,
                        planned_resource_id=published.resource_id,
                        area_id=planning.area_id,
                        work_center_id=planning.work_center_id,
                        deck_position=planning.deck_position,
                        product_sequence_no=planning.product_sequence_no,
                        routing_sequence_no=planning.routing_sequence_no,
                        operation_code=planning.source_operation_code,
                        operation_description=planning.source_description,
                        requested_quantity=planning.requested_quantity,
                        planned_start=published.planned_start,
                        planned_finish=published.planned_finish,
                        status="PENDING",
                    )
                )
            self.session.add_all(operations)
            self.session.commit()
            self.session.refresh(dispatch)
            return dispatch, len(operations), False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("MES dispatch identity already exists") from exc

    def release_dispatch(self, dispatch_id: UUID) -> ExecutionDispatch:
        dispatch = self.get_dispatch(dispatch_id)
        if dispatch.status == "RELEASED":
            return dispatch
        if dispatch.status != "DRAFT":
            raise MESRuleError("only DRAFT execution dispatch can be released")

        publication = self.session.get(SchedulePublication, dispatch.publication_id)
        if publication is None:
            raise MESNotFoundError("dispatch publication not found")
        if publication.status != "CURRENT":
            raise MESRuleError("cannot release dispatch because its source publication is no longer CURRENT")

        operation_count = self.session.scalar(
            select(ExecutionOperation.id)
            .where(ExecutionOperation.dispatch_id == dispatch.id)
            .limit(1)
        )
        if operation_count is None:
            raise MESRuleError("execution dispatch has no operations")

        dispatch.status = "RELEASED"
        dispatch.released_at = datetime.now(timezone.utc)
        return self._commit(dispatch)

    def cancel_dispatch(self, dispatch_id: UUID) -> ExecutionDispatch:
        dispatch = self.get_dispatch(dispatch_id)
        if dispatch.status == "CANCELLED":
            return dispatch
        if dispatch.status != "DRAFT":
            raise MESRuleError("only DRAFT execution dispatch can be cancelled")
        dispatch.status = "CANCELLED"
        dispatch.cancelled_at = datetime.now(timezone.utc)
        return self._commit(dispatch)
