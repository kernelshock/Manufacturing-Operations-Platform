"""Application service for G5.1 MES execution dispatch foundation."""

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.aps.lifecycle_models import SchedulePublication, PublishedScheduledOperation
from mop.aps.models import SchedulingScenario
from mop.aps.operation_models import PlanningOperation
from mop.core.models import Resource
from mop.mes.models import ExecutionDispatch, ExecutionHandoff, ExecutionInterruption, ExecutionOperation, ExecutionOperationEvent, ExecutionSetup
from mop.mes.rework_models import ReworkCase
from mop.mes.schemas import (
    ExecutionCompleteCreate,
    ExecutionDeviationRead,
    ExecutionDispatchCreate,
    ExecutionStartCreate,
    ExecutionWIPTraceRead,
    HandoffReceiveCreate,
    HandoffTransferCreate,
    InterruptionResumeCreate,
    InterruptionStartCreate,
    SetupFinishCreate,
    SetupStartCreate,
)


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


    def get_operation(self, operation_id: UUID) -> ExecutionOperation:
        operation = self.session.get(ExecutionOperation, operation_id)
        if operation is None:
            raise MESNotFoundError("execution operation not found")
        return operation

    def list_operation_events(self, operation_id: UUID) -> Sequence[ExecutionOperationEvent]:
        self.get_operation(operation_id)
        return self.session.scalars(
            select(ExecutionOperationEvent)
            .where(ExecutionOperationEvent.execution_operation_id == operation_id)
            .order_by(ExecutionOperationEvent.occurred_at, ExecutionOperationEvent.created_at)
        ).all()

    def _get_operation_dispatch(self, operation: ExecutionOperation) -> ExecutionDispatch:
        dispatch = self.session.get(ExecutionDispatch, operation.dispatch_id)
        if dispatch is None:
            raise MESNotFoundError("execution dispatch not found")
        return dispatch


    def _adjacent_operations(
        self,
        operation: ExecutionOperation,
    ) -> tuple[ExecutionOperation | None, ExecutionOperation | None]:
        siblings = list(
            self.session.scalars(
                select(ExecutionOperation)
                .where(
                    ExecutionOperation.dispatch_id == operation.dispatch_id,
                    ExecutionOperation.product_line_id == operation.product_line_id,
                )
                .order_by(
                    ExecutionOperation.routing_sequence_no,
                    ExecutionOperation.id,
                )
            ).all()
        )
        predecessor = None
        successor = None
        for index, item in enumerate(siblings):
            if item.id != operation.id:
                continue
            if index > 0:
                predecessor = siblings[index - 1]
            if index + 1 < len(siblings):
                successor = siblings[index + 1]
            break
        return predecessor, successor

    def list_handoffs(
        self,
        operation_id: UUID,
    ) -> Sequence[ExecutionHandoff]:
        self.get_operation(operation_id)
        return self.session.scalars(
            select(ExecutionHandoff)
            .where(
                (ExecutionHandoff.from_execution_operation_id == operation_id)
                | (ExecutionHandoff.to_execution_operation_id == operation_id)
            )
            .order_by(
                ExecutionHandoff.transferred_at,
                ExecutionHandoff.sequence_no,
                ExecutionHandoff.created_at,
            )
        ).all()

    def transfer_wip(
        self,
        from_operation_id: UUID,
        data: HandoffTransferCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionHandoff, bool]:
        source = self.session.scalar(
            select(ExecutionOperation)
            .where(ExecutionOperation.id == from_operation_id)
            .with_for_update()
        )
        if source is None:
            raise MESNotFoundError("source execution operation not found")
        target = self.get_operation(data.to_execution_operation_id)
        if source.dispatch_id != target.dispatch_id:
            raise MESRuleError("WIP handoff operations must belong to the same dispatch")
        if source.product_line_id != target.product_line_id:
            raise MESRuleError("WIP handoff operations must belong to the same product line")

        _, expected_successor = self._adjacent_operations(source)
        if expected_successor is None or expected_successor.id != target.id:
            raise MESRuleError("WIP handoff target must be the immediate execution successor")
        if source.status != "COMPLETED" or source.produced_quantity is None:
            raise MESRuleError("WIP can only transfer from a COMPLETED predecessor")
        if target.status == "COMPLETED":
            raise MESRuleError("WIP cannot transfer to an already COMPLETED successor")

        already_transferred = self.session.scalar(
            select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0))
            .where(
                ExecutionHandoff.from_execution_operation_id == source.id,
                ExecutionHandoff.to_execution_operation_id == target.id,
            )
        )
        allocated_to_rework = self.session.scalar(
            select(func.coalesce(func.sum(ReworkCase.quantity), 0)).where(
                ReworkCase.source_execution_operation_id == source.id,
                ReworkCase.status != "CANCELLED",
            )
        )
        total_after = Decimal(str(already_transferred)) + Decimal(str(allocated_to_rework)) + data.quantity
        if total_after > source.produced_quantity:
            raise MESRuleError("WIP transfer quantity exceeds predecessor produced quantity or reserved rework quantity")

        latest_sequence = self.session.scalar(
            select(func.coalesce(func.max(ExecutionHandoff.sequence_no), 0))
            .where(
                ExecutionHandoff.from_execution_operation_id == source.id,
                ExecutionHandoff.to_execution_operation_id == target.id,
            )
        )
        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        if source.actual_finish is not None and occurred_at < source.actual_finish:
            raise MESRuleError("WIP transfer cannot precede predecessor actual finish")

        handoff = ExecutionHandoff(
            dispatch_id=source.dispatch_id,
            product_line_id=source.product_line_id,
            from_execution_operation_id=source.id,
            to_execution_operation_id=target.id,
            sequence_no=int(latest_sequence) + 1,
            quantity=data.quantity,
            status="TRANSFERRED",
            transferred_at=occurred_at,
            transferred_by=actor_id,
            note=data.note,
        )
        try:
            self.session.add(handoff)
            self.session.commit()
            self.session.refresh(handoff)
            return handoff, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("WIP handoff identity already exists") from exc

    def receive_handoff(
        self,
        handoff_id: UUID,
        data: HandoffReceiveCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionHandoff, bool]:
        handoff = self.session.get(ExecutionHandoff, handoff_id)
        if handoff is None:
            raise MESNotFoundError("execution handoff not found")
        if handoff.status == "RECEIVED":
            if data.occurred_at is not None and data.occurred_at != handoff.received_at:
                raise MESConflictError("WIP handoff was already received at a different timestamp")
            return handoff, True
        if handoff.status != "TRANSFERRED":
            raise MESRuleError("only TRANSFERRED WIP handoff can be received")

        target = self.get_operation(handoff.to_execution_operation_id)
        if target.status == "COMPLETED":
            raise MESRuleError("WIP handoff cannot be received by a COMPLETED successor")

        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        if occurred_at < handoff.transferred_at:
            raise MESRuleError("WIP receipt cannot precede transfer")

        handoff.status = "RECEIVED"
        handoff.received_at = occurred_at
        handoff.received_by = actor_id
        return self._commit(handoff), False

    def get_wip_trace(self, operation_id: UUID) -> ExecutionWIPTraceRead:
        operation = self.get_operation(operation_id)
        predecessor, successor = self._adjacent_operations(operation)

        incoming_transferred = self.session.scalar(
            select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0))
            .where(ExecutionHandoff.to_execution_operation_id == operation.id)
        )
        incoming_received = self.session.scalar(
            select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0))
            .where(
                ExecutionHandoff.to_execution_operation_id == operation.id,
                ExecutionHandoff.status == "RECEIVED",
            )
        )
        outgoing_transferred = self.session.scalar(
            select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0))
            .where(ExecutionHandoff.from_execution_operation_id == operation.id)
        )
        outgoing_received = self.session.scalar(
            select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0))
            .where(
                ExecutionHandoff.from_execution_operation_id == operation.id,
                ExecutionHandoff.status == "RECEIVED",
            )
        )

        available_to_transfer = None
        if operation.produced_quantity is not None:
            available_to_transfer = operation.produced_quantity - Decimal(str(outgoing_transferred))

        return ExecutionWIPTraceRead(
            operation_id=operation.id,
            predecessor_operation_id=predecessor.id if predecessor else None,
            successor_operation_id=successor.id if successor else None,
            produced_quantity=operation.produced_quantity,
            incoming_transferred_quantity=Decimal(str(incoming_transferred)),
            incoming_received_quantity=Decimal(str(incoming_received)),
            outgoing_transferred_quantity=Decimal(str(outgoing_transferred)),
            outgoing_received_quantity=Decimal(str(outgoing_received)),
            available_to_transfer=available_to_transfer,
        )

    def start_operation(
        self,
        operation_id: UUID,
        data: ExecutionStartCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionOperation, ExecutionOperationEvent, bool]:
        operation = self.get_operation(operation_id)
        dispatch = self._get_operation_dispatch(operation)
        if dispatch.status != "RELEASED":
            raise MESRuleError("execution operation can only start from a RELEASED dispatch")

        existing = self.session.scalar(
            select(ExecutionOperationEvent).where(
                ExecutionOperationEvent.execution_operation_id == operation.id,
                ExecutionOperationEvent.event_type == "START",
            )
        )
        if existing is not None:
            if operation.status not in {"RUNNING", "PAUSED", "COMPLETED"}:
                raise MESConflictError("START event exists but execution operation state is inconsistent")
            if data.occurred_at is not None and data.occurred_at != existing.occurred_at:
                raise MESConflictError("execution operation has already started at a different timestamp")
            if data.note is not None and data.note != existing.note:
                raise MESConflictError("execution operation START event already exists with different evidence")
            if data.actual_resource_id is not None and data.actual_resource_id != operation.actual_resource_id:
                raise MESConflictError("execution operation has already started with different actual resource evidence")
            if data.resource_deviation_reason is not None and data.resource_deviation_reason != operation.resource_deviation_reason:
                raise MESConflictError("execution operation has already started with different resource deviation evidence")
            return operation, existing, True

        if operation.status != "PENDING":
            raise MESRuleError("only PENDING execution operation can be started")

        predecessor, _ = self._adjacent_operations(operation)
        if predecessor is not None:
            received_quantity = self.session.scalar(
                select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0))
                .where(
                    ExecutionHandoff.from_execution_operation_id == predecessor.id,
                    ExecutionHandoff.to_execution_operation_id == operation.id,
                    ExecutionHandoff.status == "RECEIVED",
                )
            )
            returned_rework = self.session.scalar(
                select(func.coalesce(func.sum(ReworkCase.quantity), 0)).where(
                    ReworkCase.dispatch_id == operation.dispatch_id,
                    ReworkCase.return_execution_operation_id == operation.id,
                    ReworkCase.status == "RETURNED",
                )
            )
            if Decimal(str(received_quantity)) <= 0 and Decimal(str(returned_rework)) <= 0:
                raise MESRuleError("execution successor requires received WIP or an explicit returned rework path")

        setup = self.session.scalar(
            select(ExecutionSetup).where(ExecutionSetup.execution_operation_id == operation.id)
        )
        if setup is not None and setup.finished_at is None:
            raise MESRuleError("execution operation cannot start while setup is still open")

        if data.actual_resource_id is not None:
            actual_resource = self.session.get(Resource, data.actual_resource_id)
            if actual_resource is None:
                raise MESNotFoundError("actual execution resource not found")
            if not actual_resource.active:
                raise MESRuleError("actual execution resource must be active")
            if actual_resource.id != operation.planned_resource_id and not (data.resource_deviation_reason or "").strip():
                raise MESRuleError("resource deviation reason is required when actual resource differs from planned resource")
            if actual_resource.id == operation.planned_resource_id and data.resource_deviation_reason is not None:
                raise MESRuleError("resource deviation reason is only valid when actual resource differs from planned resource")
        elif data.resource_deviation_reason is not None:
            raise MESRuleError("resource deviation reason requires actual_resource_id")

        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        event = ExecutionOperationEvent(
            execution_operation_id=operation.id,
            event_type="START",
            occurred_at=occurred_at,
            note=data.note,
            actor_user_id=actor_id,
        )
        try:
            operation.status = "RUNNING"
            operation.actual_start = occurred_at
            operation.started_by = actor_id
            operation.actual_resource_id = data.actual_resource_id
            operation.resource_deviation_reason = (
                data.resource_deviation_reason.strip()
                if data.resource_deviation_reason is not None
                else None
            )
            self.session.add(operation)
            self.session.add(event)
            self.session.commit()
            self.session.refresh(operation)
            self.session.refresh(event)
            return operation, event, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("execution START event already exists") from exc

    def complete_operation(
        self,
        operation_id: UUID,
        data: ExecutionCompleteCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionOperation, ExecutionOperationEvent, bool]:
        operation = self.get_operation(operation_id)
        dispatch = self._get_operation_dispatch(operation)
        if dispatch.status != "RELEASED":
            raise MESRuleError("execution operation can only complete from a RELEASED dispatch")

        existing = self.session.scalar(
            select(ExecutionOperationEvent).where(
                ExecutionOperationEvent.execution_operation_id == operation.id,
                ExecutionOperationEvent.event_type == "COMPLETE",
            )
        )
        if existing is not None:
            if operation.status != "COMPLETED":
                raise MESConflictError("COMPLETE event exists but execution operation state is inconsistent")
            if existing.produced_quantity != data.produced_quantity:
                raise MESConflictError("execution operation is already completed with a different produced quantity")
            if data.occurred_at is not None and data.occurred_at != existing.occurred_at:
                raise MESConflictError("execution operation is already completed at a different timestamp")
            if data.note is not None and data.note != existing.note:
                raise MESConflictError("execution operation COMPLETE event already exists with different evidence")
            return operation, existing, True

        if operation.status != "RUNNING" or operation.actual_start is None:
            raise MESRuleError("only RUNNING execution operation can be completed")

        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        if occurred_at < operation.actual_start:
            raise MESRuleError("actual finish cannot precede actual start")

        event = ExecutionOperationEvent(
            execution_operation_id=operation.id,
            event_type="COMPLETE",
            occurred_at=occurred_at,
            produced_quantity=data.produced_quantity,
            note=data.note,
            actor_user_id=actor_id,
        )
        try:
            operation.status = "COMPLETED"
            operation.actual_finish = occurred_at
            operation.produced_quantity = data.produced_quantity
            operation.completed_by = actor_id
            self.session.add(operation)
            self.session.add(event)
            self.session.commit()
            self.session.refresh(operation)
            self.session.refresh(event)
            return operation, event, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("execution COMPLETE event already exists") from exc


    def get_setup(self, operation_id: UUID) -> ExecutionSetup | None:
        self.get_operation(operation_id)
        return self.session.scalar(
            select(ExecutionSetup).where(ExecutionSetup.execution_operation_id == operation_id)
        )

    def start_setup(
        self,
        operation_id: UUID,
        data: SetupStartCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionOperation, ExecutionSetup, bool]:
        operation = self.get_operation(operation_id)
        dispatch = self._get_operation_dispatch(operation)
        if dispatch.status != "RELEASED":
            raise MESRuleError("setup can only start from a RELEASED dispatch")

        existing = self.get_setup(operation.id)
        if existing is not None:
            if data.occurred_at is not None and data.occurred_at != existing.started_at:
                raise MESConflictError("setup has already started at a different timestamp")
            if data.note is not None and data.note != existing.note:
                raise MESConflictError("setup already exists with different evidence")
            return operation, existing, True

        if operation.status != "PENDING":
            raise MESRuleError("setup can only start while execution operation is PENDING")

        setup = ExecutionSetup(
            execution_operation_id=operation.id,
            started_at=data.occurred_at or datetime.now(timezone.utc),
            note=data.note,
            started_by=actor_id,
        )
        try:
            self.session.add(setup)
            self.session.commit()
            self.session.refresh(setup)
            return operation, setup, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("setup already exists for execution operation") from exc

    def finish_setup(
        self,
        operation_id: UUID,
        data: SetupFinishCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionOperation, ExecutionSetup, bool]:
        operation = self.get_operation(operation_id)
        setup = self.get_setup(operation.id)
        if setup is None:
            raise MESRuleError("setup has not been started")
        if setup.finished_at is not None:
            if data.occurred_at is not None and data.occurred_at != setup.finished_at:
                raise MESConflictError("setup has already finished at a different timestamp")
            return operation, setup, True
        if operation.status != "PENDING":
            raise MESRuleError("setup can only finish before execution operation starts")

        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        if occurred_at < setup.started_at:
            raise MESRuleError("setup finish cannot precede setup start")
        setup.finished_at = occurred_at
        setup.finished_by = actor_id
        return operation, self._commit(setup), False

    def list_interruptions(self, operation_id: UUID) -> Sequence[ExecutionInterruption]:
        self.get_operation(operation_id)
        return self.session.scalars(
            select(ExecutionInterruption)
            .where(ExecutionInterruption.execution_operation_id == operation_id)
            .order_by(ExecutionInterruption.started_at, ExecutionInterruption.created_at)
        ).all()

    def _open_interruption(self, operation_id: UUID) -> ExecutionInterruption | None:
        return self.session.scalar(
            select(ExecutionInterruption).where(
                ExecutionInterruption.execution_operation_id == operation_id,
                ExecutionInterruption.ended_at.is_(None),
            )
        )

    def pause_operation(
        self,
        operation_id: UUID,
        data: InterruptionStartCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionOperation, ExecutionInterruption, bool]:
        operation = self.get_operation(operation_id)
        dispatch = self._get_operation_dispatch(operation)
        if dispatch.status != "RELEASED":
            raise MESRuleError("execution operation can only pause from a RELEASED dispatch")

        existing = self._open_interruption(operation.id)
        if existing is not None:
            if operation.status != "PAUSED":
                raise MESConflictError("open interruption exists but operation is not PAUSED")
            if existing.reason_code != data.reason_code.strip():
                raise MESConflictError("open interruption already exists with a different reason")
            if data.reason_note is not None and data.reason_note != existing.reason_note:
                raise MESConflictError("open interruption already exists with different evidence")
            if data.occurred_at is not None and data.occurred_at != existing.started_at:
                raise MESConflictError("open interruption already exists at a different timestamp")
            return operation, existing, True

        if operation.status != "RUNNING":
            raise MESRuleError("only RUNNING execution operation can be paused")

        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        if operation.actual_start is not None and occurred_at < operation.actual_start:
            raise MESRuleError("interruption cannot precede actual start")

        interruption = ExecutionInterruption(
            execution_operation_id=operation.id,
            started_at=occurred_at,
            reason_code=data.reason_code.strip(),
            reason_note=data.reason_note,
            started_by=actor_id,
        )
        try:
            operation.status = "PAUSED"
            self.session.add(operation)
            self.session.add(interruption)
            self.session.commit()
            self.session.refresh(operation)
            self.session.refresh(interruption)
            return operation, interruption, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("execution interruption could not be recorded") from exc

    def resume_operation(
        self,
        operation_id: UUID,
        data: InterruptionResumeCreate,
        actor_id: UUID | None,
    ) -> tuple[ExecutionOperation, ExecutionInterruption, bool]:
        operation = self.get_operation(operation_id)
        interruption = self._open_interruption(operation.id)
        if interruption is None:
            if operation.status == "RUNNING":
                latest = self.session.scalar(
                    select(ExecutionInterruption)
                    .where(ExecutionInterruption.execution_operation_id == operation.id)
                    .order_by(ExecutionInterruption.started_at.desc())
                    .limit(1)
                )
                if latest is not None and latest.ended_at is not None:
                    if data.occurred_at is not None and data.occurred_at != latest.ended_at:
                        raise MESConflictError("latest interruption already resumed at a different timestamp")
                    return operation, latest, True
            raise MESRuleError("execution operation has no open interruption to resume")

        if operation.status != "PAUSED":
            raise MESConflictError("open interruption exists but operation is not PAUSED")

        occurred_at = data.occurred_at or datetime.now(timezone.utc)
        if occurred_at < interruption.started_at:
            raise MESRuleError("resume cannot precede interruption start")

        interruption.ended_at = occurred_at
        interruption.ended_by = actor_id
        operation.status = "RUNNING"
        try:
            self.session.add(operation)
            self.session.add(interruption)
            self.session.commit()
            self.session.refresh(operation)
            self.session.refresh(interruption)
            return operation, interruption, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("execution interruption resume failed") from exc

    def get_deviation(self, operation_id: UUID) -> ExecutionDeviationRead:
        operation = self.get_operation(operation_id)
        setup = self.get_setup(operation.id)
        interruptions = list(self.list_interruptions(operation.id))

        setup_seconds = None
        if setup is not None and setup.finished_at is not None:
            setup_seconds = Decimal(str((setup.finished_at - setup.started_at).total_seconds()))

        interruption_seconds = Decimal("0")
        open_interruption = False
        for interruption in interruptions:
            if interruption.ended_at is None:
                open_interruption = True
                continue
            interruption_seconds += Decimal(
                str((interruption.ended_at - interruption.started_at).total_seconds())
            )

        start_delta = None
        if operation.actual_start is not None:
            start_delta = Decimal(
                str((operation.actual_start - operation.planned_start).total_seconds())
            )

        finish_delta = None
        if operation.actual_finish is not None:
            finish_delta = Decimal(
                str((operation.actual_finish - operation.planned_finish).total_seconds())
            )

        quantity_delta = None
        if operation.produced_quantity is not None:
            quantity_delta = operation.produced_quantity - operation.requested_quantity

        resource_deviation = None
        if operation.actual_resource_id is not None:
            resource_deviation = operation.actual_resource_id != operation.planned_resource_id

        return ExecutionDeviationRead(
            operation_id=operation.id,
            planned_start=operation.planned_start,
            actual_start=operation.actual_start,
            start_delta_seconds=start_delta,
            planned_finish=operation.planned_finish,
            actual_finish=operation.actual_finish,
            finish_delta_seconds=finish_delta,
            requested_quantity=operation.requested_quantity,
            produced_quantity=operation.produced_quantity,
            quantity_delta=quantity_delta,
            planned_resource_id=operation.planned_resource_id,
            actual_resource_id=operation.actual_resource_id,
            resource_deviation=resource_deviation,
            setup_seconds=setup_seconds,
            interruption_seconds=interruption_seconds,
            open_interruption=open_interruption,
        )
