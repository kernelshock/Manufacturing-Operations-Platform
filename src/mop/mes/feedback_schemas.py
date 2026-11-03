"""G5.6 read-only execution feedback projections."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class OperationFeedbackRead(BaseModel):
    execution_operation_id: UUID
    published_operation_id: UUID
    plan_id: UUID
    taquilla_id: UUID
    product_line_id: UUID
    routing_operation_id: UUID
    planned_start: datetime
    planned_finish: datetime
    actual_start: datetime | None
    actual_finish: datetime | None
    requested_quantity: Decimal
    produced_quantity: Decimal | None
    start_delta_seconds: Decimal | None
    finish_delta_seconds: Decimal | None
    quantity_delta: Decimal | None
    classification: str
    resource_deviation: bool | None


class DispatchFeedbackRead(BaseModel):
    dispatch_id: UUID
    publication_id: UUID
    schedule_fingerprint: str
    plan_id: UUID
    dispatch_status: str
    classification: str
    operation_count: int
    completed_count: int
    delayed_count: int
    quantity_shortfall_count: int
    open_rework_count: int
    replan_review_recommended: bool
    operations: list[OperationFeedbackRead]
