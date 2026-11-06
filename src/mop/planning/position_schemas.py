"""G7.2 read-only inventory and verified legacy supply position transport.

Physical, Quality, reservations and provisional inbound are intentionally distinct.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PositionLocation(BaseModel):
    location_id: UUID
    warehouse_code: str
    location_code: str
    physical_on_hand: Decimal | None
    committed_holds: Decimal
    unallocated_physical: Decimal | None
    state: Literal["KNOWN", "UNKNOWN"]


class VerifiedOrderLine(BaseModel):
    po_number: str
    line_number: int
    supplier_code: str
    original_promise_at: datetime
    revised_promise_at: datetime | None
    effective_promise_at: datetime
    ordered: Decimal
    received_reported: Decimal
    accepted_reported: Decimal | None
    outstanding_reported: Decimal
    receipt_count: int
    evidence_event_ids: list[UUID]
    assurance: Literal["PARTIAL_VERIFIED_MANUAL"] = "PARTIAL_VERIFIED_MANUAL"
    inventory_effect: Literal["NONE"] = "NONE"


class PositionSnapshot(BaseModel):
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    snapshot_at: datetime
    evidence_cutoff_at: datetime
    physical_on_hand: Decimal | None
    physical_state: Literal["KNOWN", "UNKNOWN"]
    committed_holds: Decimal
    unallocated_physical: Decimal | None
    quality_usable: Decimal | None = None
    quality_state: Literal["NOT_INTEGRATED"] = "NOT_INTEGRATED"
    quality_unallocated: Decimal | None = None
    confirmed_in_transit: Decimal | None = None
    in_transit_state: Literal["UNKNOWN"] = "UNKNOWN"
    verified_open_order_sample: Decimal | None
    supplier_evidence_state: Literal["UNKNOWN", "PARTIAL_VERIFIED_MANUAL"]
    location_breakdown: list[PositionLocation]
    order_lines: list[VerifiedOrderLine]
    warnings: list[str]
    purchasing_effect: Literal["NONE"] = "NONE"
    stock_effect: Literal["NONE"] = "NONE"
