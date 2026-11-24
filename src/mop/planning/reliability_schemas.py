"""G7.3: verifiable sample only, not global supplier performance."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel


class SupplierLineMetric(BaseModel):
    po_number: str
    line_number: int
    original_promised_at: datetime
    latest_revised_at: datetime | None
    ordered: Decimal
    delivered_reported: Decimal
    outstanding_reported: Decimal
    partial_receipt_count: int
    claims: int
    production_risk_escalations: int
    first_receipt_at: datetime | None
    final_receipt_at: datetime | None
    actual_lead_time_business_days: int | None
    original_delay_business_days: int | None
    revised_delay_business_days: int | None
    source_event_ids: list[UUID]
    status: Literal["OPEN", "COMPLETED", "INVALID_SOURCE"]
    original_promise_status: Literal["ON_TIME", "LATE", "NOT_YET_DUE", "UNKNOWN"]
    revised_promise_status: Literal["ON_TIME", "LATE", "NOT_YET_DUE", "NOT_REPROGRAMMED", "UNKNOWN"]


class SupplierReliabilityOverview(BaseModel):
    supplier_code: str
    article_id: UUID
    calendar_id: UUID
    calendar_code: str
    calendar_timezone: str
    evidence_cutoff_at: datetime
    source_scope: Literal["PARTIAL_VERIFIED_MANUAL_SAMPLE"] = "PARTIAL_VERIFIED_MANUAL_SAMPLE"
    calendar_scope: Literal["PLANT_CALENDAR_PROXY_NOT_SUPPLIER_AGREEMENT"] = "PLANT_CALENDAR_PROXY_NOT_SUPPLIER_AGREEMENT"
    sample_size: int
    completed_lines: int
    open_lines: int
    late_against_original_completed: int
    late_against_revised_completed: int | None
    on_time_original_sample_ratio: Decimal | None
    mean_actual_lead_business_days: Decimal | None
    observed_lead_std_business_days: Decimal | None
    mean_original_delay_business_days: Decimal | None
    statistical_reliability_state: Literal["INSUFFICIENT_COVERAGE"] = "INSUFFICIENT_COVERAGE"
    completeness: Literal["UNKNOWN_ERP_COVERAGE"] = "UNKNOWN_ERP_COVERAGE"
    physical_stock_effect: Literal["NONE"] = "NONE"
    purchase_order_effect: Literal["NONE"] = "NONE"
    lines: list[SupplierLineMetric]
    warnings: list[str]
