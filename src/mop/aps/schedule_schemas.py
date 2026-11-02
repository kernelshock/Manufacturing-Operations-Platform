"""Schemas for G4.4 finite-capacity sequencing."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from mop.aps.schemas import SchedulingRunRead


class ScheduledOperationSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scheduled_operation_id: UUID
    resource_id: UUID
    availability_interval_id: UUID
    segment_no: int
    start_at: datetime
    end_at: datetime
    effective_rate_per_hour: Decimal
    produced_quantity: Decimal


class ScheduledOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    planning_operation_id: UUID
    resource_id: UUID
    sequence_no: int
    planned_start: datetime
    planned_finish: datetime
    processing_seconds: Decimal
    requested_quantity: Decimal
    nominal_rate: Decimal
    normalized_rate_uom: str
    algorithm_key: str
    algorithm_version: str


class ScheduleSolveResult(BaseModel):
    run: SchedulingRunRead
    scheduled_operation_count: int
    segment_count: int
    makespan_start: datetime
    makespan_finish: datetime
    idempotent_replay: bool
