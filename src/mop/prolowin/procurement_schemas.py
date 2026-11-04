"""Validated transcription and review contracts for legacy Prolowin."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("explicit timezone required")
    return value


def nonempty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ManualCaptureCreate(BaseModel):
    source_type: Literal["MANUAL", "WEEKLY_SNAPSHOT"] = "MANUAL"
    source_reference: str = Field(min_length=1, max_length=150)

    @field_validator("source_reference")
    @classmethod
    def clean(cls, value: str): return nonempty(value)


class CaptureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_type: str
    source_reference: str
    source_sha256: str | None
    image_mime: str | None
    captured_by: UUID
    created_at: datetime


class EvidenceCreate(BaseModel):
    capture_id: UUID
    source_event_key: str = Field(min_length=1, max_length=180)
    kind: Literal["ORDER", "RECEIPT", "RESCHEDULE", "CLAIM", "ESCALATION"]
    po_number: str = Field(min_length=1, max_length=80)
    line_number: int = Field(ge=1)
    supplier_code: str = Field(min_length=1, max_length=80)
    article_code: str = Field(min_length=1, max_length=80)
    uom_code: str = Field(min_length=1, max_length=30)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8, allow_inf_nan=False)
    accepted_quantity: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8, allow_inf_nan=False)
    event_date: datetime
    original_promise_date: datetime | None = None
    revised_promise_date: datetime | None = None
    reason: str | None = Field(default=None, max_length=1200)
    continuity_safe: bool | None = None
    source_reference: str = Field(min_length=1, max_length=128)

    @field_validator("source_event_key", "po_number", "supplier_code", "article_code", "uom_code", "source_reference")
    @classmethod
    def clean(cls, value: str): return nonempty(value)

    @field_validator("quantity", "accepted_quantity", mode="before")
    @classmethod
    def exact(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantity must be provided as an exact decimal string")
        return value

    @field_validator("event_date", "original_promise_date", "revised_promise_date")
    @classmethod
    def dates(cls, value):
        return aware(value) if value else value

    @model_validator(mode="after")
    def event_contract(self):
        if self.accepted_quantity is not None and (
            self.quantity is None or self.accepted_quantity > self.quantity
        ):
            raise ValueError("accepted quantity cannot exceed delivered quantity")
        if self.kind == "ORDER":
            if not self.quantity or not self.original_promise_date:
                raise ValueError("order requires quantity and original promised date")
            if self.event_date > self.original_promise_date:
                raise ValueError("original promise predates purchase order")
        elif self.kind == "RECEIPT":
            if not self.quantity:
                raise ValueError("partial or full receipt requires delivered quantity")
        elif self.kind == "RESCHEDULE":
            if not self.revised_promise_date or self.continuity_safe is not True:
                raise ValueError("accepted reschedule requires revised date and confirmed no production risk")
            if not self.reason:
                raise ValueError("reschedule requires reason")
        elif self.kind in {"CLAIM", "ESCALATION"}:
            if not self.reason:
                raise ValueError("claim or alternate-supplier escalation requires reason")
        return self


class EvidenceReview(BaseModel):
    decision: Literal["VERIFIED", "REJECTED"]
    note: str = Field(min_length=4, max_length=1200)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    capture_id: UUID
    source_event_key: str
    kind: str
    po_number: str
    line_number: int
    supplier_code: str
    article_code: str
    uom_code: str
    quantity: Decimal | None
    accepted_quantity: Decimal | None
    event_date: datetime
    original_promise_date: datetime | None
    revised_promise_date: datetime | None
    reason: str | None
    continuity_safe: bool | None
    source_reference: str
    mapped_supplier_id: UUID | None
    mapped_article_id: UUID | None
    mapped_uom_id: UUID | None
    review_status: str
    entered_by: UUID
    entered_at: datetime
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_note: str | None


class OrderLineSummary(BaseModel):
    po_number: str
    line_number: int
    supplier_code: str
    article_code: str
    original_promise_date: datetime
    latest_revised_promise_date: datetime | None
    order_date: datetime
    ordered_quantity: Decimal
    delivered_quantity: Decimal
    accepted_quantity: Decimal | None
    outstanding_delivered_quantity: Decimal
    overdue_against_original: bool
    delayed_days_calendar: int | None
    claim_count: int
    production_risk_escalations: int
    partial_receipt_count: int
    source: Literal["VERIFIED_PROLOWIN_EVIDENCE"] = "VERIFIED_PROLOWIN_EVIDENCE"
    physical_inventory_effect: Literal["NONE"] = "NONE"
