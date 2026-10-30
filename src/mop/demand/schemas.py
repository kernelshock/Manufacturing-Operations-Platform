"""Transport schemas for G3 operational demand."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PlanStatus = Literal["DRAFT", "OPEN", "COMPLETED", "CANCELLED"]
TaquillaStatus = Literal["DRAFT", "READY", "COMPLETED", "CANCELLED"]


def _trim(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


class ProductionPlanCreate(BaseModel):
    plan_number: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=4000)

    _plan_number = field_validator("plan_number")(_trim)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProductionPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_number: str
    description: str | None
    status: PlanStatus
    created_at: datetime
    updated_at: datetime


class ProductionPlanNumberUpdate(BaseModel):
    plan_number: str = Field(min_length=1, max_length=80)

    _plan_number = field_validator("plan_number")(_trim)


class ProductionPlanStatusUpdate(BaseModel):
    status: PlanStatus


class TaquillaCreate(BaseModel):
    taquilla_code: str = Field(min_length=1, max_length=80)
    sequence_no: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=4000)

    _taquilla_code = field_validator("taquilla_code")(_trim)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TaquillaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    taquilla_code: str
    sequence_no: int
    description: str | None
    status: TaquillaStatus
    created_at: datetime
    updated_at: datetime


class TaquillaStatusUpdate(BaseModel):
    status: TaquillaStatus


class TaquillaProductLineCreate(BaseModel):
    article_id: UUID
    sequence_no: int = Field(gt=0)
    requested_quantity: Decimal = Field(gt=0)
    source_line_key: str | None = Field(default=None, max_length=200)

    @field_validator("source_line_key")
    @classmethod
    def normalize_source_line_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TaquillaProductLineUpdate(BaseModel):
    sequence_no: int = Field(gt=0)
    requested_quantity: Decimal = Field(gt=0)


class TaquillaProductLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    taquilla_id: UUID
    article_id: UUID
    sequence_no: int
    requested_quantity: Decimal
    source_line_key: str | None
    created_at: datetime
    updated_at: datetime
