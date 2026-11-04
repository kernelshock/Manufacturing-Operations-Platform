"""G6.4 measured and explicitly authorized material-consumption API contracts."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsumptionCreate(BaseModel):
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8, allow_inf_nan=False)
    evidence_reference: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    observed_at: datetime

    @field_validator("quantity", mode="before")
    @classmethod
    def exact_decimal(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantities must be exact decimal strings")
        return value

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at requires an explicit timezone")
        return value

    @field_validator("evidence_reference", "idempotency_key")
    @classmethod
    def nonblank(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("evidence fields cannot be blank")
        return clean


class ConsumptionReverse(BaseModel):
    evidence_reference: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    reason_code: str = Field(min_length=1, max_length=80)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at requires an explicit timezone")
        return value

    @field_validator("evidence_reference", "idempotency_key", "reason_code")
    @classmethod
    def nonblank(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("reversal reason and evidence cannot be blank")
        return clean


class ConsumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    execution_operation_id: UUID
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    quantity: Decimal
    stock_movement_id: UUID
    idempotency_key: str
    evidence_reference: str
    reversal_of_id: UUID | None
    reason_code: str | None
    observed_at: datetime
    recorded_by: UUID
    created_at: datetime


class ConsumptionResult(BaseModel):
    consumption: ConsumptionRead
    idempotent_replay: bool
