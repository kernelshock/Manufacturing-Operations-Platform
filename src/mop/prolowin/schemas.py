"""Transport contracts for Prolowin staging and reconciliation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ImportBatchStatus = Literal[
    "RECEIVED",
    "PARSED",
    "VALIDATED",
    "REJECTED",
    "APPLIED",
    "RECONCILED",
]
DQSeverity = Literal["INFO", "WARNING", "ERROR", "BLOCKER"]
DQStatus = Literal["OPEN", "ACCEPTED", "RESOLVED", "WAIVED"]
ReconciliationStatus = Literal[
    "MATCH", "MATCH_WITH_WARNINGS", "MISMATCH", "BLOCKED"
]


def _nonempty_preserve(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be empty")
    return value


def _code(value: str) -> str:
    value = value.strip().upper()
    if not value:
        raise ValueError("code must not be empty")
    return value


def _decimal_string(value) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("quantity must be serialized as a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal string") from exc
    if not parsed.is_finite():
        raise ValueError("quantity must be finite")
    return parsed


class ProlowinSourceDescriptor(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    exported_at: datetime | None = None
    parser_version: str = Field(min_length=1, max_length=80)

    _filename = field_validator("filename")(_nonempty_preserve)

    @field_validator("sha256")
    @classmethod
    def normalize_sha(cls, value: str) -> str:
        return value.lower()

    @field_validator("parser_version")
    @classmethod
    def normalize_parser_version(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("parser_version must not be empty")
        return value


class ProlowinRootArticle(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    description: str | None = None
    quantity: Decimal
    uom_raw: str = Field(min_length=1, max_length=80)

    _code = field_validator("code")(_code)
    _uom = field_validator("uom_raw")(_nonempty_preserve)
    _quantity = field_validator("quantity", mode="before")(_decimal_string)

    @field_validator("quantity")
    @classmethod
    def nonnegative_quantity(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("quantity must be non-negative")
        return value


class ProlowinCompleteRow(BaseModel):
    row_no: int = Field(ge=1)
    page: int | None = Field(default=None, ge=1)
    article_code: str = Field(min_length=1, max_length=80)
    operation_code: str = Field(min_length=1, max_length=30)
    description_raw: str
    quantity: Decimal
    uom_raw: str = Field(min_length=1, max_length=80)
    row_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-fA-F]{64}$"
    )

    _article_code = field_validator("article_code")(_code)
    _operation_code = field_validator("operation_code")(_code)
    _uom = field_validator("uom_raw")(_nonempty_preserve)
    _quantity = field_validator("quantity", mode="before")(_decimal_string)

    @field_validator("quantity")
    @classmethod
    def nonnegative_quantity(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("quantity must be non-negative")
        return value

    @field_validator("row_hash")
    @classmethod
    def normalize_row_hash(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None


class ProlowinCompleteStructureImport(BaseModel):
    schema_version: Literal["1.0.0"]
    source_system: Literal["PROLOWIN"]
    report_type: Literal["COMPLETE_ARTICLE_STRUCTURE"]
    source: ProlowinSourceDescriptor
    root_article: ProlowinRootArticle
    rows: list[ProlowinCompleteRow] = Field(min_length=1)


class ProlowinDirectRelationCreate(BaseModel):
    row_no: int = Field(ge=1)
    sequence_no: int | None = Field(default=None, ge=1)
    parent_article_code: str = Field(min_length=1, max_length=80)
    parent_description_raw: str | None = None
    child_article_code: str = Field(min_length=1, max_length=80)
    child_description_raw: str | None = None
    quantity: Decimal
    uom_raw: str = Field(min_length=1, max_length=80)
    source_relation_key: str | None = Field(default=None, max_length=200)
    row_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-fA-F]{64}$"
    )

    _parent_code = field_validator("parent_article_code")(_code)
    _child_code = field_validator("child_article_code")(_code)
    _uom = field_validator("uom_raw")(_nonempty_preserve)
    _quantity = field_validator("quantity", mode="before")(_decimal_string)

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be greater than zero")
        return value

    @field_validator("source_relation_key")
    @classmethod
    def normalize_relation_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("row_hash")
    @classmethod
    def normalize_row_hash(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None


class ProlowinDirectStructureImport(BaseModel):
    schema_version: Literal["1.0.0"]
    source_system: Literal["PROLOWIN"]
    report_type: Literal["DIRECT_ARTICLE_STRUCTURE"]
    source: ProlowinSourceDescriptor
    root_article_code: str = Field(min_length=1, max_length=80)
    relations: list[ProlowinDirectRelationCreate] = Field(min_length=1)

    _root_code = field_validator("root_article_code")(_code)


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_system: str
    source_type: str
    source_filename: str
    source_sha256: str
    exported_at: datetime | None
    imported_at: datetime
    parser_version: str
    mapping_version: str
    imported_by: UUID | None
    status: ImportBatchStatus
    accepted_rows: int
    rejected_rows: int


class DataQualityIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    entity_type: str
    entity_key: str
    rule_code: str
    severity: DQSeverity
    message: str
    source_row_id: UUID | None
    source_value: str | None
    suggested_action: str | None
    status: DQStatus
    resolution_note: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime


class FlatRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_id: UUID
    article_code: str
    quantity: Decimal
    uom_raw: str
    source_fin_row_id: UUID
    is_root: bool


class SourceOperationStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_id: UUID
    article_code: str
    source_operation_code: str
    source_description: str
    quantity: Decimal
    uom_raw: str
    source_row_id: UUID


class CompleteImportResult(BaseModel):
    batch: ImportBatchRead
    root_article_revision_id: UUID | None
    snapshot_id: UUID | None
    flat_requirements: int
    operation_states: int
    data_quality_issues: list[DataQualityIssueRead]
    idempotent_replay: bool = False


class DirectImportResult(BaseModel):
    batch: ImportBatchRead
    candidate_article_revision_ids: list[UUID]
    candidate_bom_revision_ids: list[UUID]
    data_quality_issues: list[DataQualityIssueRead]
    idempotent_replay: bool = False


class ReconciliationRequest(BaseModel):
    complete_batch_id: UUID
    bom_revision_id: UUID
    tolerance: Decimal = Field(default=Decimal("0"), ge=0)


class ReconciliationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reconciliation_run_id: UUID
    article_code: str
    source_fin_quantity: Decimal | None
    source_uom_raw: str | None
    calculated_quantity: Decimal | None
    calculated_uom_raw: str | None
    comparison_uom: str
    variance: Decimal | None
    result: Literal[
        "MATCH", "MISMATCH", "SOURCE_ONLY", "CALCULATED_ONLY"
    ]


class ReconciliationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    root_article_revision_id: UUID
    bom_revision_id: UUID
    run_at: datetime
    status: ReconciliationStatus
    tolerance: Decimal
    compared_items: int
    matching_items: int
    mismatching_items: int


class ReconciliationResult(BaseModel):
    run: ReconciliationRunRead
    items: list[ReconciliationItemRead]


class NormalizedProjectionRead(BaseModel):
    flat_requirements: list[FlatRequirementRead]
    operation_states: list[SourceOperationStateRead]
