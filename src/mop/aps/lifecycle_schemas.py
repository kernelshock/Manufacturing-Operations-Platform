"""Schemas for G4.5 schedule lifecycle, replan and publication."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mop.aps.schemas import SchedulingRunRead


class ReplanCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)
    algorithm_key: str | None = Field(default=None, min_length=1, max_length=80)
    algorithm_version: str | None = Field(default=None, min_length=1, max_length=80)


class PublishScheduleRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=4000)


class SchedulePublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scenario_id: UUID
    run_id: UUID
    version_no: int
    status: str
    supersedes_publication_id: UUID | None
    publish_reason: str | None
    schedule_fingerprint: str
    published_by: UUID | None
    published_at: datetime


class ReplanResult(BaseModel):
    source_run_id: UUID
    run: SchedulingRunRead


class PublishResult(BaseModel):
    publication: SchedulePublicationRead
    superseded_publication_id: UUID | None
    idempotent_replay: bool


class PublishedScheduledOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    publication_id: UUID
    source_scheduled_operation_id: UUID
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


class ScheduleComparisonRead(BaseModel):
    source_publication_id: UUID
    source_run_id: UUID
    candidate_run_id: UUID
    baseline_operation_count: int
    candidate_operation_count: int
    added_operation_count: int
    removed_operation_count: int
    timing_changed_count: int
    resource_changed_count: int
    baseline_start: datetime
    baseline_finish: datetime
    candidate_start: datetime
    candidate_finish: datetime
    makespan_delta_seconds: Decimal
