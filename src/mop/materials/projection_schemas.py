"""G6.7 read-only material projections: explicit scope and unknown semantics."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MaterialPlantOption(BaseModel):
    id: UUID
    code: str
    name: str


class MaterialPlanOption(BaseModel):
    id: UUID
    plan_number: str
    status: str


class MaterialLocationProjection(BaseModel):
    location_id: UUID
    warehouse_code: str
    location_code: str
    location_name: str
    on_hand: Decimal | None
    held: Decimal
    unallocated: Decimal | None
    state: Literal["KNOWN", "UNKNOWN"]


class MaterialItemProjection(BaseModel):
    source_basis: Literal["BOM", "MEASURED_WITHOUT_BOM"]
    article_id: UUID
    article_code: str
    article_description: str
    uom_id: UUID
    uom_code: str
    theoretical_plan_quantity: Decimal
    actual_net_measured_consumption: Decimal
    theoretical_minus_measured: Decimal
    physical_on_hand: Decimal | None
    reserved_all_plans: Decimal
    reserved_this_plan: Decimal
    unallocated_physical: Decimal | None
    provisional_gross_gap: Decimal | None
    stock_state: Literal["KNOWN", "UNKNOWN"]
    location_breakdown: list[MaterialLocationProjection]
    distinct_taquillas: int
    source_path_count: int
    bom_revision_ids: list[UUID]
    warnings: list[str]


class MaterialPlanOverview(BaseModel):
    plan_id: UUID
    plan_number: str
    plan_status: str
    plant_id: UUID
    plant_code: str
    effective_at: datetime
    generated_at: datetime
    basis: Literal["THEORETICAL_BOM_PLUS_PHYSICAL_LEDGER"] = "THEORETICAL_BOM_PLUS_PHYSICAL_LEDGER"
    stock_state: Literal["UNKNOWN_IF_ANY_LOCATION_UNINITIALIZED"] = "UNKNOWN_IF_ANY_LOCATION_UNINITIALIZED"
    gap_policy: Literal["GROSS_PROVISIONAL_NOT_ATP"] = "GROSS_PROVISIONAL_NOT_ATP"
    source_taquillas: int
    excluded_cancelled_taquillas: list[UUID]
    material_count: int
    bom_material_count: int
    unplanned_consumption_materials: int
    unknown_stock_materials: int
    indicative_gap_materials: int
    items: list[MaterialItemProjection]
    warnings: list[str]


class MaterialPurchaseEvidenceLine(BaseModel):
    article_id: UUID
    article_code: str
    verified_order_lines: int
    verified_receipt_events: int
    verified_claims: int
    verified_escalations: int
    latest_verified_event_at: datetime | None
    original_promise_dates: list[datetime]
    revised_promise_dates: list[datetime]


class MaterialPurchaseEvidenceOverview(BaseModel):
    plan_id: UUID
    effective_at: datetime
    data_scope: Literal["VERIFIED_MANUAL_SAMPLES_ONLY"] = "VERIFIED_MANUAL_SAMPLES_ONLY"
    no_verified_records_means: Literal["UNKNOWN_NOT_ZERO"] = "UNKNOWN_NOT_ZERO"
    stock_effect: Literal["NONE"] = "NONE"
    items: list[MaterialPurchaseEvidenceLine]
