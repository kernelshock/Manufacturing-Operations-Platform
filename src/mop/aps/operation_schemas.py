"""Schemas for G4.2 demand/routing expansion."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from mop.aps.schemas import SchedulingRunRead


class PlanningOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    plan_id: UUID
    taquilla_id: UUID
    product_line_id: UUID
    article_id: UUID
    routing_revision_id: UUID
    routing_operation_id: UUID
    requested_quantity: Decimal
    deck_position: str
    product_sequence_no: int
    routing_sequence_no: int
    source_operation_code: str
    source_description: str
    operation_kind: str
    schedulable: bool
    completion_marker: bool
    area_id: UUID | None
    work_center_id: UUID | None
    nominal_rate: Decimal | None
    rate_uom: str | None
    routing_source_fingerprint: str
    created_at: datetime


class ExpansionResult(BaseModel):
    run: SchedulingRunRead
    operation_count: int
    product_line_count: int
    routing_revision_count: int
    idempotent_replay: bool
