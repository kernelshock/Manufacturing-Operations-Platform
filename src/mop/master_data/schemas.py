"""Transport schemas for canonical Master Data."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UomDimension = Literal["COUNT", "LENGTH", "MASS", "VOLUME", "OTHER"]
UomMappingStatus = Literal["MAPPED", "UNMAPPED", "REVIEW_REQUIRED"]
ArticleKind = Literal[
    "UNKNOWN",
    "PURCHASED",
    "MANUFACTURED",
    "FINISHED_PRODUCT",
    "CONSUMABLE",
    "SERVICE",
]
ArticleRevisionStatus = Literal["DRAFT", "ACTIVE", "SUPERSEDED", "REJECTED"]
SupplierCategory = Literal["UNKNOWN", "PRODUCT", "PROCESS", "SERVICE", "MIXED"]
SupplierMappingStatus = Literal["MAPPED", "REVIEW_REQUIRED", "REJECTED"]
BOMRevisionStatus = Literal["DRAFT", "ACTIVE", "SUPERSEDED", "REJECTED"]


def _upper_trim(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


def _trim(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


class UnitOfMeasureCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    dimension: UomDimension
    canonical: bool = True
    active: bool = True

    _code = field_validator("code")(_upper_trim)


class UnitOfMeasureRead(UnitOfMeasureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class UnitOfMeasureAliasCreate(BaseModel):
    source_system: str = Field(min_length=1, max_length=40)
    raw_value: str = Field(min_length=1, max_length=80)
    uom_id: UUID | None = None
    mapping_status: UomMappingStatus
    conversion_factor: Decimal | None = Field(default=None, gt=0)

    _source = field_validator("source_system")(_upper_trim)
    _raw = field_validator("raw_value")(_trim)

    @model_validator(mode="after")
    def validate_mapping(self) -> "UnitOfMeasureAliasCreate":
        if self.mapping_status == "MAPPED" and self.uom_id is None:
            raise ValueError("MAPPED alias requires uom_id")
        if self.mapping_status == "UNMAPPED" and self.uom_id is not None:
            raise ValueError("UNMAPPED alias must not have uom_id")
        if self.conversion_factor is not None and self.uom_id is None:
            raise ValueError("conversion_factor requires uom_id")
        return self


class UnitOfMeasureAliasRead(UnitOfMeasureAliasCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    approved_at: datetime | None
    approved_by: UUID | None


class ArticleCreate(BaseModel):
    external_system: str = Field(min_length=1, max_length=40)
    external_code: str = Field(min_length=1, max_length=80)
    canonical_description: str = Field(min_length=1, max_length=4000)
    article_kind: ArticleKind = "UNKNOWN"
    default_uom_id: UUID | None = None
    active: bool = True

    _system = field_validator("external_system")(_upper_trim)
    _code = field_validator("external_code")(_trim)
    _description = field_validator("canonical_description")(_trim)


class ArticleRead(ArticleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class ArticleRevisionCreate(BaseModel):
    revision_label: str | None = Field(default=None, max_length=80)
    source_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    valid_from: datetime | None = None
    source_batch_id: UUID | None = None

    @field_validator("revision_label")
    @classmethod
    def normalize_revision_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("source_fingerprint")
    @classmethod
    def normalize_fingerprint(cls, value: str) -> str:
        return value.lower()


class ArticleRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    article_id: UUID
    revision_label: str | None
    source_fingerprint: str
    valid_from: datetime
    valid_to: datetime | None
    status: ArticleRevisionStatus
    source_batch_id: UUID | None
    approved_at: datetime | None
    approved_by: UUID | None


class ProductConfigurationCreate(BaseModel):
    article_id: UUID
    family_code: str = Field(min_length=1, max_length=64)
    family_name: str = Field(min_length=1, max_length=255)
    model_code: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=255)
    product_class: str = Field(min_length=1, max_length=64)
    width: Decimal | None = Field(default=None, gt=0)
    width_uom_id: UUID | None = None
    configuration_string: str = Field(min_length=1, max_length=4000)
    active: bool = True

    _family_code = field_validator("family_code")(_upper_trim)
    _family_name = field_validator("family_name")(_trim)
    _model_code = field_validator("model_code")(_upper_trim)
    _model_name = field_validator("model_name")(_trim)
    _product_class = field_validator("product_class")(_trim)
    _configuration = field_validator("configuration_string")(_trim)

    @model_validator(mode="after")
    def validate_width_unit_pair(self) -> "ProductConfigurationCreate":
        if (self.width is None) != (self.width_uom_id is None):
            raise ValueError("width and width_uom_id must be provided together")
        return self


class ProductConfigurationRead(ProductConfigurationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    supply_category: SupplierCategory = "UNKNOWN"
    active: bool = True

    _code = field_validator("code")(_upper_trim)
    _legal_name = field_validator("legal_name")(_trim)

    @field_validator("trade_name")
    @classmethod
    def normalize_trade_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupplierRead(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class SupplierSourceMappingCreate(BaseModel):
    supplier_id: UUID | None = None
    external_system: str = Field(min_length=1, max_length=40)
    external_code: str = Field(min_length=1, max_length=80)
    source_name: str | None = Field(default=None, max_length=255)
    source_category_raw: str | None = Field(default=None, max_length=255)
    mapping_status: SupplierMappingStatus
    active: bool = True

    _external_system = field_validator("external_system")(_upper_trim)
    _external_code = field_validator("external_code")(_trim)

    @field_validator("source_name", "source_category_raw")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_mapping(self) -> "SupplierSourceMappingCreate":
        if self.mapping_status == "MAPPED" and self.supplier_id is None:
            raise ValueError("MAPPED supplier source requires supplier_id")
        if self.mapping_status == "REJECTED" and self.supplier_id is not None:
            raise ValueError("REJECTED supplier source must not have supplier_id")
        return self


class SupplierSourceMappingRead(SupplierSourceMappingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    approved_at: datetime | None
    approved_by: UUID | None
    last_seen_at: datetime


class SupplierArticleCreate(BaseModel):
    supplier_id: UUID
    article_id: UUID
    supplier_article_code: str | None = Field(default=None, max_length=120)
    preferred: bool = False
    lead_time_days: int | None = Field(default=None, ge=0)
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0)
    order_uom_id: UUID | None = None
    active: bool = True

    @field_validator("supplier_article_code")
    @classmethod
    def normalize_supplier_article_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupplierArticleRead(SupplierArticleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime



class BOMRevisionCreate(BaseModel):
    parent_article_revision_id: UUID
    revision_no: int = Field(gt=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source_system: str = Field(min_length=1, max_length=40)
    source_batch_id: UUID | None = None
    source_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    _source_system = field_validator("source_system")(_upper_trim)

    @field_validator("source_fingerprint")
    @classmethod
    def normalize_bom_fingerprint(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def validate_effectivity(self) -> "BOMRevisionCreate":
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to <= self.valid_from
        ):
            raise ValueError("valid_to must be later than valid_from")
        return self


class BOMRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_article_revision_id: UUID
    revision_no: int
    valid_from: datetime
    valid_to: datetime | None
    status: BOMRevisionStatus
    source_system: str
    source_batch_id: UUID | None
    source_fingerprint: str
    created_at: datetime


class BOMComponentCreate(BaseModel):
    child_article_id: UUID
    child_revision_id: UUID | None = None
    quantity: Decimal = Field(gt=0)
    source_uom_raw: str = Field(min_length=1, max_length=80)
    uom_id: UUID | None = None
    sequence_no: int | None = Field(default=None, ge=0)
    source_relation_key: str | None = Field(default=None, max_length=200)
    scrap_factor: Decimal | None = Field(default=None, ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    _source_uom_raw = field_validator("source_uom_raw")(_trim)

    @field_validator("source_relation_key")
    @classmethod
    def normalize_relation_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_effectivity(self) -> "BOMComponentCreate":
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must be later than effective_from")
        return self


class BOMComponentRead(BOMComponentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bom_revision_id: UUID
    created_at: datetime


class BOMSupersedeRequest(BaseModel):
    replacement_bom_revision_id: UUID
    effective_at: datetime | None = None


class BOMExplosionLine(BaseModel):
    component_id: UUID
    bom_revision_id: UUID
    article_id: UUID
    article_code: str
    quantity: Decimal
    uom_id: UUID | None
    source_uom_raw: str
    depth: int
    leaf: bool
    path_article_ids: list[UUID]
    path_article_codes: list[str]
    path_component_ids: list[UUID]


class BOMExplosionAggregate(BaseModel):
    article_id: UUID
    article_code: str
    quantity: Decimal
    uom_id: UUID | None
    source_uom_raw: str


class BOMExplosionRead(BaseModel):
    root_bom_revision_id: UUID
    root_quantity: Decimal
    effective_at: datetime
    paths: list[BOMExplosionLine]
    aggregate: list[BOMExplosionAggregate]
