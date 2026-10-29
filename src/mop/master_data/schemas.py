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
