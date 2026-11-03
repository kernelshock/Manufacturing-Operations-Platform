"""G5.6 observational MES -> APS feedback; never mutates an APS publication."""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.mes.models import ExecutionDispatch, ExecutionOperation
from mop.mes.rework_models import ReworkCase
from mop.mes.service import MESNotFoundError
from mop.mes.feedback_schemas import DispatchFeedbackRead, OperationFeedbackRead


def classify_operation(operation: ExecutionOperation) -> str:
    """Only explicitly completed operations may be called ON_TIME or DELAYED."""
    if operation.status == "COMPLETED" and operation.actual_finish is not None:
        return "ON_TIME" if operation.actual_finish <= operation.planned_finish else "DELAYED"
    if operation.status in ("RUNNING", "PAUSED"):
        return "IN_PROGRESS"
    return "NOT_STARTED"


class FeedbackService:
    def __init__(self, session: Session):
        self.session = session

    def _dispatch(self, dispatch_id: UUID) -> ExecutionDispatch:
        dispatch = self.session.get(ExecutionDispatch, dispatch_id)
        if dispatch is None:
            raise MESNotFoundError("execution dispatch not found")
        return dispatch

    @staticmethod
    def _operation_feedback(operation: ExecutionOperation) -> OperationFeedbackRead:
        start_delta = (
            Decimal(str((operation.actual_start - operation.planned_start).total_seconds()))
            if operation.actual_start is not None else None
        )
        finish_delta = (
            Decimal(str((operation.actual_finish - operation.planned_finish).total_seconds()))
            if operation.actual_finish is not None else None
        )
        quantity_delta = (
            operation.produced_quantity - operation.requested_quantity
            if operation.produced_quantity is not None else None
        )
        return OperationFeedbackRead(
            execution_operation_id=operation.id,
            published_operation_id=operation.published_operation_id,
            plan_id=operation.plan_id,
            taquilla_id=operation.taquilla_id,
            product_line_id=operation.product_line_id,
            routing_operation_id=operation.routing_operation_id,
            planned_start=operation.planned_start,
            planned_finish=operation.planned_finish,
            actual_start=operation.actual_start,
            actual_finish=operation.actual_finish,
            requested_quantity=operation.requested_quantity,
            produced_quantity=operation.produced_quantity,
            start_delta_seconds=start_delta,
            finish_delta_seconds=finish_delta,
            quantity_delta=quantity_delta,
            classification=classify_operation(operation),
            resource_deviation=(
                operation.actual_resource_id != operation.planned_resource_id
                if operation.actual_resource_id is not None else None
            ),
        )

    def operation_feedback(self, operation_id: UUID) -> OperationFeedbackRead:
        operation = self.session.get(ExecutionOperation, operation_id)
        if operation is None:
            raise MESNotFoundError("execution operation not found")
        return self._operation_feedback(operation)

    def dispatch_feedback(self, dispatch_id: UUID) -> DispatchFeedbackRead:
        dispatch = self._dispatch(dispatch_id)
        operations = list(self.session.scalars(
            select(ExecutionOperation).where(ExecutionOperation.dispatch_id == dispatch_id)
            .order_by(ExecutionOperation.taquilla_id, ExecutionOperation.product_sequence_no,
                      ExecutionOperation.routing_sequence_no, ExecutionOperation.id)
        ).all())
        cases = list(self.session.scalars(
            select(ReworkCase).where(ReworkCase.dispatch_id == dispatch_id)
        ).all())
        items = [self._operation_feedback(operation) for operation in operations]
        completed = [item for item in items if item.classification in ("ON_TIME", "DELAYED")]
        open_rework = sum(case.status not in ("RETURNED", "CANCELLED") for case in cases)
        all_completed = bool(items) and len(completed) == len(items) and open_rework == 0
        if all_completed:
            classification = (
                "ON_TIME" if all(item.classification == "ON_TIME" for item in items)
                else "DELAYED"
            )
        elif any(item.classification == "IN_PROGRESS" for item in items) or completed or open_rework:
            classification = "IN_PROGRESS"
        else:
            classification = "NOT_STARTED"
        quantity_shortfall_count = sum(
            item.quantity_delta is not None and item.quantity_delta < 0 for item in items
        )
        # Feedback is observational. It is not a replan or a statement of root cause.
        return DispatchFeedbackRead(
            dispatch_id=dispatch.id,
            publication_id=dispatch.publication_id,
            schedule_fingerprint=dispatch.schedule_fingerprint,
            plan_id=dispatch.plan_id,
            dispatch_status=dispatch.status,
            classification=classification,
            operation_count=len(items),
            completed_count=len(completed),
            delayed_count=sum(item.classification == "DELAYED" for item in items),
            quantity_shortfall_count=quantity_shortfall_count,
            open_rework_count=open_rework,
            replan_review_recommended=(classification == "DELAYED"
                or quantity_shortfall_count > 0 or open_rework > 0),
            operations=items,
        )
