"""Schemas for G5.1 MES execution dispatch foundation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionDispatchCreate(BaseModel):
    publication_id: UUID
    dispatch_code: str = Field(min_length=1, max_length=80)


class ExecutionDispatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dispatch_code: str
    publication_id: UUID
    scenario_id: UUID
    run_id: UUID
    plan_id: UUID
    publication_version_no: int
    schedule_fingerprint: str
    operation_count: int
    status: str
    created_by: UUID | None
    created_at: datetime
    released_at: datetime | None
    cancelled_at: datetime | None


class ExecutionOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dispatch_id: UUID
    publication_id: UUID
    published_operation_id: UUID
    planning_operation_id: UUID
    plan_id: UUID
    taquilla_id: UUID
    product_line_id: UUID
    article_id: UUID
    routing_revision_id: UUID
    routing_operation_id: UUID
    planned_resource_id: UUID
    area_id: UUID | None
    work_center_id: UUID | None
    deck_position: str
    product_sequence_no: int
    routing_sequence_no: int
    operation_code: str
    operation_description: str
    requested_quantity: Decimal
    planned_start: datetime
    planned_finish: datetime
    status: str
    created_at: datetime


class DispatchMaterializationResult(BaseModel):
    dispatch: ExecutionDispatchRead
    operation_count: int
    idempotent_replay: bool
