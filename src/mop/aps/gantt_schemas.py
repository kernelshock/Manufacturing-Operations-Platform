"""Read-only Gantt projection schemas for G4.6."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class GanttSegmentRead(BaseModel):
    segment_no: int
    start_at: datetime
    end_at: datetime
    effective_rate_per_hour: Decimal
    produced_quantity: Decimal


class GanttOperationRead(BaseModel):
    publication_id: UUID
    publication_version: int
    publication_status: str
    run_id: UUID
    scenario_id: UUID
    plan_id: UUID
    plan_number: str
    taquilla_id: UUID
    taquilla_code: str
    taquilla_sequence_no: int
    product_line_id: UUID
    product_sequence_no: int
    article_id: UUID
    article_code: str
    article_description: str
    deck_position: str
    routing_revision_id: UUID
    routing_operation_id: UUID
    routing_sequence_no: int
    operation_code: str
    operation_description: str | None
    resource_id: UUID
    resource_code: str
    resource_name: str
    work_center_id: UUID
    work_center_code: str
    work_center_name: str
    area_id: UUID
    area_code: str
    area_name: str
    sequence_no: int
    planned_start: datetime
    planned_finish: datetime
    processing_seconds: Decimal
    requested_quantity: Decimal
    segments: list[GanttSegmentRead]


class GanttPublicationRead(BaseModel):
    publication_id: UUID
    scenario_id: UUID
    run_id: UUID
    plan_id: UUID
    plan_number: str
    version_no: int
    status: str
    published_at: datetime
    schedule_fingerprint: str
    operation_count: int


class GanttProjectionRead(BaseModel):
    scope: str
    plan_id: UUID | None
    plan_number: str | None
    window_start: datetime | None
    window_end: datetime | None
    publications: list[GanttPublicationRead]
    operations: list[GanttOperationRead]
    operation_count: int
    taquilla_count: int
    resource_count: int
    constraints_evaluated: list[str]
    constraints_not_evaluated: list[str]
