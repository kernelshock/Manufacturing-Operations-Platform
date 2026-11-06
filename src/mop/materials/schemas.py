"""G6.2 transactional stock location and ledger transport."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

StockKind = Literal["OPENING", "OPENING_ZERO", "RECEIPT", "ISSUE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"]


class WarehouseCreate(BaseModel):
    plant_id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("code")
    @classmethod
    def code_format(cls, value: str) -> str:
        code = value.strip().upper()
        if not code:
            raise ValueError("code must not be blank")
        return code


class WarehouseRead(WarehouseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    active: bool


class LocationCreate(BaseModel):
    warehouse_id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("code")
    @classmethod
    def code_format(cls, value: str) -> str:
        code = value.strip().upper()
        if not code:
            raise ValueError("code must not be blank")
        return code


class LocationRead(LocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    active: bool


class MovementCreate(BaseModel):
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    kind: StockKind
    quantity: Decimal = Field(ge=0, max_digits=24, decimal_places=8, allow_inf_nan=False)
    source_system: str = Field(min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    occurred_at: datetime | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def exact_quantity(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantities must be decimal strings, not binary floats")
        return value

    @model_validator(mode="after")
    def validate_zero_opening(self):
        if self.kind == "OPENING_ZERO":
            if self.quantity != 0:
                raise ValueError("OPENING_ZERO requires exactly zero quantity")
        elif self.quantity == 0:
            raise ValueError("non-opening-zero movements require a positive quantity")
        return self

    @field_validator("source_system", "source_reference", "idempotency_key")
    @classmethod
    def nonempty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("source evidence cannot be blank")
        return trimmed


class MovementReverse(BaseModel):
    source_system: str = Field(min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("source_system", "source_reference", "idempotency_key")
    @classmethod
    def nonempty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("source evidence cannot be blank")
        return trimmed


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    kind: str
    quantity: Decimal
    signed_quantity: Decimal
    source_system: str
    source_reference: str
    idempotency_key: str
    reversal_of_id: UUID | None
    occurred_at: datetime
    posted_by: UUID
    posted_at: datetime


class PostingResult(BaseModel):
    movement: MovementRead
    idempotent_replay: bool


class BalanceRead(BaseModel):
    article_id: UUID
    location_id: UUID
    uom_id: UUID | None
    initialized: bool
    on_hand: Decimal | None
    # An empty ledger means UNKNOWN, never an implicit 0.


