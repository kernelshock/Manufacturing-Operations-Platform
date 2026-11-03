"""G5.5 service for explicit non-nominal execution paths."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.core.models import Resource
from mop.master_data.models import RoutingOperation
from mop.mes.models import ExecutionDispatch, ExecutionHandoff, ExecutionOperation
from mop.mes.rework_models import ReworkCase, ReworkStep
from mop.mes.rework_schemas import ReworkCaseCreate, ReworkStepCreate, ReworkStart, ReworkComplete
from mop.mes.service import MESConflictError, MESNotFoundError, MESRuleError


class ReworkService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_case(self, case_id: UUID) -> ReworkCase:
        case = self.session.get(ReworkCase, case_id)
        if case is None:
            raise MESNotFoundError("rework case not found")
        return case

    def get_step(self, step_id: UUID) -> ReworkStep:
        step = self.session.get(ReworkStep, step_id)
        if step is None:
            raise MESNotFoundError("rework step not found")
        return step

    def list_cases(self, dispatch_id: UUID) -> list[ReworkCase]:
        if self.session.get(ExecutionDispatch, dispatch_id) is None:
            raise MESNotFoundError("execution dispatch not found")
        return list(self.session.scalars(
            select(ReworkCase).where(ReworkCase.dispatch_id == dispatch_id)
            .order_by(ReworkCase.created_at, ReworkCase.case_code)
        ).all())

    def list_steps(self, case_id: UUID) -> list[ReworkStep]:
        self.get_case(case_id)
        return list(self.session.scalars(
            select(ReworkStep).where(ReworkStep.case_id == case_id)
            .order_by(ReworkStep.sequence_no)
        ).all())

    def _commit(self, entity):
        try:
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("rework identity conflict") from exc

    def create_case(self, data: ReworkCaseCreate, actor_id: UUID | None) -> tuple[ReworkCase, bool]:
        source = self.session.scalar(
            select(ExecutionOperation).where(
                ExecutionOperation.id == data.source_execution_operation_id
            ).with_for_update()
        )
        if source is None:
            raise MESNotFoundError("source execution operation not found")
        target = self.session.get(ExecutionOperation, data.return_execution_operation_id)
        if target is None:
            raise MESNotFoundError("return execution operation not found")
        if source.id == target.id:
            raise MESRuleError("rework return must target a distinct execution operation")
        if source.dispatch_id != target.dispatch_id or source.product_line_id != target.product_line_id:
            raise MESRuleError("rework path must remain inside one dispatch and product line")
        dispatch = self.session.get(ExecutionDispatch, source.dispatch_id)
        if dispatch is None or dispatch.status != "RELEASED":
            raise MESRuleError("rework requires a RELEASED execution dispatch")
        if source.status != "COMPLETED" or source.produced_quantity is None:
            raise MESRuleError("rework source must be COMPLETED with explicit produced quantity")
        if target.status == "COMPLETED":
            raise MESRuleError("rework cannot return to an already COMPLETED operation")
        if not data.case_code.strip() or not data.reason_code.strip():
            raise MESRuleError("rework code and reason cannot be blank")

        existing = self.session.scalar(
            select(ReworkCase).where(
                ReworkCase.dispatch_id == source.dispatch_id,
                ReworkCase.case_code == data.case_code.strip(),
            )
        )
        if existing is not None:
            if (
                existing.source_execution_operation_id != source.id
                or existing.return_execution_operation_id != target.id
                or existing.quantity != data.quantity
                or existing.reason_code != data.reason_code.strip()
                or existing.reason_note != data.reason_note
            ):
                raise MESConflictError("rework case code already exists with different evidence")
            return existing, True

        transferred = self.session.scalar(
            select(func.coalesce(func.sum(ExecutionHandoff.quantity), 0)).where(
                ExecutionHandoff.from_execution_operation_id == source.id
            )
        )
        allocated = self.session.scalar(
            select(func.coalesce(func.sum(ReworkCase.quantity), 0)).where(
                ReworkCase.source_execution_operation_id == source.id,
                ReworkCase.status != "CANCELLED",
            )
        )
        if Decimal(str(transferred)) + Decimal(str(allocated)) + data.quantity > source.produced_quantity:
            raise MESRuleError("rework allocation exceeds untransferred produced quantity")

        case = ReworkCase(
            dispatch_id=source.dispatch_id,
            product_line_id=source.product_line_id,
            source_execution_operation_id=source.id,
            return_execution_operation_id=target.id,
            case_code=data.case_code.strip(),
            reason_code=data.reason_code.strip(),
            reason_note=data.reason_note,
            quantity=data.quantity,
            status="OPEN",
            created_by=actor_id,
        )
        return self._commit(case), False

    def add_step(self, case_id: UUID, data: ReworkStepCreate) -> ReworkStep:
        case = self.session.scalar(
            select(ReworkCase).where(ReworkCase.id == case_id).with_for_update()
        )
        if case is None:
            raise MESNotFoundError("rework case not found")
        if case.status != "OPEN":
            raise MESRuleError("rework route can only be edited before execution starts")

        source = self.session.get(ExecutionOperation, case.source_execution_operation_id)
        routing = self.session.get(RoutingOperation, data.routing_operation_id)
        resource = self.session.get(Resource, data.resource_id)
        if routing is None or source is None or routing.routing_revision_id != source.routing_revision_id:
            raise MESRuleError("rework step must reference a routing operation in the source revision")
        if not routing.active:
            raise MESRuleError("rework routing operation must be active")
        if resource is None or not resource.active:
            raise MESRuleError("rework resource must exist and be active")
        existing = self.list_steps(case.id)
        step = ReworkStep(
            case_id=case.id,
            sequence_no=len(existing) + 1,
            routing_operation_id=routing.id,
            resource_id=resource.id,
            operation_code=routing.source_operation_code,
            operation_description=routing.source_description,
            status="PENDING",
        )
        return self._commit(step)

    def start_step(self, step_id: UUID, data: ReworkStart, actor_id: UUID | None) -> tuple[ReworkStep, bool]:
        step = self.get_step(step_id)
        case = self.get_case(step.case_id)
        if step.status in ("RUNNING", "COMPLETED"):
            if data.occurred_at is not None and step.actual_start != data.occurred_at:
                raise MESConflictError("rework step already started at a different timestamp")
            return step, True
        if case.status not in ("OPEN", "IN_PROGRESS") or step.status != "PENDING":
            raise MESRuleError("rework step is not eligible to start")
        steps = self.list_steps(case.id)
        index = next(i for i, item in enumerate(steps) if item.id == step.id)
        source = self.session.get(ExecutionOperation, case.source_execution_operation_id)
        prior_finish = source.actual_finish if index == 0 else steps[index - 1].actual_finish
        if index > 0 and steps[index - 1].status != "COMPLETED":
            raise MESRuleError("previous rework step must be COMPLETED")
        occurred = data.occurred_at or datetime.now(timezone.utc)
        if prior_finish is not None and occurred < prior_finish:
            raise MESRuleError("rework step start cannot precede previous completion")
        step.status = "RUNNING"
        step.actual_start = occurred
        step.started_by = actor_id
        case.status = "IN_PROGRESS"
        try:
            self.session.add_all([step, case])
            self.session.commit()
            self.session.refresh(step)
            return step, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("rework step start conflict") from exc

    def complete_step(self, step_id: UUID, data: ReworkComplete, actor_id: UUID | None) -> tuple[ReworkStep, bool]:
        step = self.get_step(step_id)
        case = self.get_case(step.case_id)
        if step.status == "COMPLETED":
            if step.produced_quantity != data.produced_quantity or (
                data.occurred_at is not None and step.actual_finish != data.occurred_at
            ):
                raise MESConflictError("rework step already completed with different evidence")
            return step, True
        if step.status != "RUNNING" or case.status != "IN_PROGRESS":
            raise MESRuleError("only a RUNNING rework step can be completed")
        steps = self.list_steps(case.id)
        index = next(i for i, item in enumerate(steps) if item.id == step.id)
        upstream = case.quantity if index == 0 else steps[index - 1].produced_quantity
        if upstream is None or data.produced_quantity > upstream:
            raise MESRuleError("rework step output exceeds received rework quantity")
        occurred = data.occurred_at or datetime.now(timezone.utc)
        if step.actual_start is not None and occurred < step.actual_start:
            raise MESRuleError("rework completion cannot precede start")
        step.status = "COMPLETED"
        step.actual_finish = occurred
        step.produced_quantity = data.produced_quantity
        step.completed_by = actor_id
        if index == len(steps) - 1:
            case.status = "READY_TO_RETURN"
        try:
            self.session.add_all([step, case])
            self.session.commit()
            self.session.refresh(step)
            return step, False
        except IntegrityError as exc:
            self.session.rollback()
            raise MESConflictError("rework step completion conflict") from exc

    def return_case(self, case_id: UUID, occurred_at: datetime | None, actor_id: UUID | None) -> tuple[ReworkCase, bool]:
        case = self.get_case(case_id)
        if case.status == "RETURNED":
            if occurred_at is not None and case.returned_at != occurred_at:
                raise MESConflictError("rework already returned at a different timestamp")
            return case, True
        if case.status != "READY_TO_RETURN":
            raise MESRuleError("all rework steps must complete before return")
        steps = self.list_steps(case.id)
        if not steps or steps[-1].produced_quantity != case.quantity:
            raise MESRuleError("rework return quantity must match allocated quantity")
        target = self.session.get(ExecutionOperation, case.return_execution_operation_id)
        if target is None or target.status != "PENDING":
            raise MESRuleError("rework return target must be PENDING")
        occurred = occurred_at or datetime.now(timezone.utc)
        if steps[-1].actual_finish is not None and occurred < steps[-1].actual_finish:
            raise MESRuleError("rework return cannot precede final step completion")
        case.status = "RETURNED"
        case.returned_at = occurred
        case.returned_by = actor_id
        return self._commit(case), False
