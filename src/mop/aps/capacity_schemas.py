"""Schemas for G4.3 calendar and capacity projection."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from mop.aps.schemas import SchedulingRunRead


class CapacityCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    planning_operation_id: UUID
    routing_operation_id: UUID
    resource_id: UUID
    source_mode: str
    resource_assignment_id: UUID | None
    assignment_capacity_factor: Decimal


class ResourceAvailabilityIntervalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    resource_id: UUID
    calendar_id: UUID
    calendar_code: str
    calendar_revision_no: int
    target_scope: str
    timezone: str
    start_at: datetime
    end_at: datetime
    calendar_capacity_factor: Decimal
    source: str


class CapacityProjectionResult(BaseModel):
    run: SchedulingRunRead
    candidate_count: int
    interval_count: int
    idempotent_replay: bool
