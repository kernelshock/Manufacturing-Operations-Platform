"""G6.3 — read-only theoretical materials requirements projections."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MaterialRequirementPath(BaseModel):
    plan_id: UUID
    plan_number: str
    taquilla_id: UUID
    taquilla_code: str
    taquilla_status: str
    product_line_id: UUID
    product_sequence_no: int
    deck_position: str
    product_article_id: UUID
    product_article_code: str
    product_quantity: Decimal
    bom_revision_id: UUID
    component_id: UUID
    component_bom_revision_id: UUID
    path_component_ids: list[UUID]
    path_article_ids: list[UUID]
    material_article_id: UUID
    material_article_code: str
    uom_id: UUID
    uom_code: str
    theoretical_quantity: Decimal


class MaterialRequirementAggregate(BaseModel):
    material_article_id: UUID
    material_article_code: str
    uom_id: UUID
    uom_code: str
    theoretical_quantity: Decimal


class MaterialDemandProjection(BaseModel):
    scope: Literal["PLAN", "TAQUILLA"]
    scope_id: UUID
    plan_id: UUID
    plan_number: str
    plan_status: str
    effective_at: datetime
    classification: Literal["THEORETICAL_ONLY"] = "THEORETICAL_ONLY"
    stock_effect: Literal["NONE"] = "NONE"
    excluded_cancelled_taquillas: list[UUID]
    source_product_lines: int
    paths: list[MaterialRequirementPath]
    aggregate: list[MaterialRequirementAggregate]
