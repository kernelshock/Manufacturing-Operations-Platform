"""G6.5 explicit reservation, release and unallocated-stock projections."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReservationCreate(BaseModel):
    taquilla_id: UUID
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8, allow_inf_nan=False)
    bom_effective_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=128)
    source_reference: str = Field(min_length=1, max_length=128)

    @field_validator("quantity", mode="before")
    @classmethod
    def exact_quantity(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantity must be an exact decimal string")
        return value

    @field_validator("bom_effective_at")
    @classmethod
    def aware_date(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("explicit timezone required")
        return value

    @field_validator("idempotency_key", "source_reference")
    @classmethod
    def nonblank(cls, value):
        clean = value.strip()
        if not clean:
            raise ValueError("evidence must not be blank")
        return clean


class ReservationRelease(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8, allow_inf_nan=False)
    idempotency_key: str = Field(min_length=1, max_length=128)
    source_reference: str = Field(min_length=1, max_length=128)
    reason_code: str = Field(min_length=1, max_length=80)

    @field_validator("quantity", mode="before")
    @classmethod
    def exact_quantity(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantity must be an exact decimal string")
        return value

    @field_validator("idempotency_key", "source_reference", "reason_code")
    @classmethod
    def nonblank(cls, value):
        clean = value.strip()
        if not clean:
            raise ValueError("evidence must not be blank")
        return clean


class ReservationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    plan_id: UUID
    taquilla_id: UUID
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    quantity: Decimal
    signed_quantity: Decimal
    bom_effective_at: datetime
    idempotency_key: str
    source_reference: str
    reason_code: str | None
    release_of_id: UUID | None
    recorded_by: UUID
    recorded_at: datetime


class ReservationResult(BaseModel):
    reservation: ReservationEventRead
    idempotent_replay: bool


class LocationAvailability(BaseModel):
    article_id: UUID
    location_id: UUID
    uom_id: UUID | None
    on_hand: Decimal | None
    reserved: Decimal
    unallocated_on_hand: Decimal | None
    state: str = "PHYSICAL_UNALLOCATED_NOT_QUALITY_CERTIFIED"


class TaquillaCoverage(BaseModel):
    plan_id: UUID
    taquilla_id: UUID
    article_id: UUID
    uom_id: UUID | None
    bom_effective_at: datetime
    theoretical_required: Decimal
    held_for_taquilla: Decimal
    unallocated_on_hand: Decimal | None
    shortage: Decimal | None
    stock_state: str
    quality_status: str = "NOT_VERIFIED"
