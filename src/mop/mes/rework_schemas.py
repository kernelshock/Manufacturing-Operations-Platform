"""G5.5 MES rework and alternative execution schemas."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")
    return value


class ReworkCaseCreate(BaseModel):
    source_execution_operation_id: UUID
    return_execution_operation_id: UUID
    case_code: str = Field(min_length=1, max_length=80)
    reason_code: str = Field(min_length=1, max_length=80)
    reason_note: str | None = Field(default=None, max_length=1000)
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)


class ReworkStepCreate(BaseModel):
    routing_operation_id: UUID
    resource_id: UUID


class ReworkStart(BaseModel):
    occurred_at: datetime | None = None
    @field_validator("occurred_at")
    @classmethod
    def validate_time(cls, value: datetime | None) -> datetime | None:
        return _aware(value)


class ReworkComplete(ReworkStart):
    produced_quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)


class ReworkCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dispatch_id: UUID
    product_line_id: UUID
    source_execution_operation_id: UUID
    return_execution_operation_id: UUID
    case_code: str
    reason_code: str
    reason_note: str | None
    quantity: Decimal
    status: str
    created_by: UUID | None
    created_at: datetime
    returned_at: datetime | None
    returned_by: UUID | None


class ReworkStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    case_id: UUID
    sequence_no: int
    routing_operation_id: UUID
    resource_id: UUID
    operation_code: str
    operation_description: str
    status: str
    actual_start: datetime | None
    actual_finish: datetime | None
    produced_quantity: Decimal | None
    started_by: UUID | None
    completed_by: UUID | None
    created_at: datetime


class ReworkActionResult(BaseModel):
    case: ReworkCaseRead
    idempotent_replay: bool


class ReworkStepActionResult(BaseModel):
    step: ReworkStepRead
    idempotent_replay: bool
