"""Transport schemas for G3 operational demand."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PlanStatus = Literal["DRAFT", "OPEN", "COMPLETED", "CANCELLED"]
TaquillaStatus = Literal["DRAFT", "READY", "COMPLETED", "CANCELLED"]
VehicleTopology = Literal["SIMPLE", "DOUBLE_DECK"]
DeckPosition = Literal["SINGLE", "UPPER", "LOWER"]
HistoricalCompletionClassification = Literal["ON_TIME", "DELAYED"]


def _trim(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


class ProductionPlanCreate(BaseModel):
    plan_number: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=4000)

    _plan_number = field_validator("plan_number")(_trim)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProductionPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_number: str
    description: str | None
    status: PlanStatus
    historical_completion_classification: HistoricalCompletionClassification | None
    historical_completion_note: str | None
    historical_completed_at: datetime | None
    historical_completed_by: UUID | None
    cancellation_reason: str | None
    cancelled_at: datetime | None
    cancelled_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ProductionPlanNumberUpdate(BaseModel):
    plan_number: str = Field(min_length=1, max_length=80)

    _plan_number = field_validator("plan_number")(_trim)


class ProductionPlanStatusUpdate(BaseModel):
    status: PlanStatus


class TaquillaCreate(BaseModel):
    taquilla_code: str = Field(min_length=1, max_length=80)
    sequence_no: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=4000)

    _taquilla_code = field_validator("taquilla_code")(_trim)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TaquillaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    taquilla_code: str
    sequence_no: int
    description: str | None
    vehicle_topology: VehicleTopology
    status: TaquillaStatus
    historical_completion_classification: HistoricalCompletionClassification | None
    historical_completion_note: str | None
    historical_completed_at: datetime | None
    historical_completed_by: UUID | None
    cancellation_reason: str | None
    cancelled_at: datetime | None
    cancelled_by: UUID | None
    created_at: datetime
    updated_at: datetime


class TaquillaStatusUpdate(BaseModel):
    status: TaquillaStatus


class TaquillaTopologyUpdate(BaseModel):
    vehicle_topology: VehicleTopology


class TaquillaProductLineCreate(BaseModel):
    article_id: UUID
    sequence_no: int = Field(gt=0)
    requested_quantity: Decimal = Field(gt=0)
    source_line_key: str | None = Field(default=None, max_length=200)
    deck_position: DeckPosition = "SINGLE"
    source_document_key: str | None = Field(default=None, max_length=200)

    @field_validator("source_line_key", "source_document_key")
    @classmethod
    def normalize_optional_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TaquillaProductLineUpdate(BaseModel):
    sequence_no: int = Field(gt=0)
    requested_quantity: Decimal = Field(gt=0)
    deck_position: DeckPosition | None = None
    source_document_key: str | None = Field(default=None, max_length=200)

    @field_validator("source_document_key")
    @classmethod
    def normalize_source_document_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TaquillaProductLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    taquilla_id: UUID
    article_id: UUID
    sequence_no: int
    requested_quantity: Decimal
    source_line_key: str | None
    deck_position: DeckPosition
    source_document_key: str | None
    routing_revision_id: UUID | None
    routing_binding_mode: RoutingBindingMode | None
    routing_effective_at: datetime | None
    routing_override_reason: str | None
    routing_bound_at: datetime | None
    routing_bound_by: UUID | None
    created_at: datetime
    updated_at: datetime


RoutingBindingMode = Literal["RESOLVED", "OVERRIDE"]


class RoutingResolveRequest(BaseModel):
    effective_at: datetime | None = None


class RoutingOverrideRequest(BaseModel):
    routing_revision_id: UUID
    effective_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=4000)

    _reason = field_validator("reason")(_trim)


class HistoricalCompletionRequest(BaseModel):
    classification: HistoricalCompletionClassification
    note: str | None = Field(default=None, max_length=4000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DemandCancellationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)

    _reason = field_validator("reason")(_trim)



AssimilationStatus = Literal[
    "RECEIVED",
    "VALIDATED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "APPLIED",
]
AssimilationIssueSeverity = Literal["WARNING", "ERROR", "BLOCKER"]


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


class TaquillaAssimilationSourceDocument(BaseModel):
    source_document_key: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    exported_at: datetime | None = None

    _document_key = field_validator("source_document_key")(_trim)
    _filename = field_validator("filename")(_trim)

    @field_validator("sha256")
    @classmethod
    def normalize_sha(cls, value: str) -> str:
        return value.lower()


class TaquillaAssimilationSourceLine(BaseModel):
    source_document_key: str = Field(min_length=1, max_length=200)
    source_line_key: str = Field(min_length=1, max_length=200)
    article_code: str = Field(min_length=1, max_length=80)
    article_source_system: str | None = Field(default=None, max_length=40)
    requested_quantity: Decimal
    deck_position: DeckPosition

    _document_key = field_validator("source_document_key")(_trim)
    _line_key = field_validator("source_line_key")(_trim)
    _article_code = field_validator("article_code")(_trim)
    _quantity = field_validator(
        "requested_quantity", mode="before"
    )(_decimal_string)

    @field_validator("article_source_system")
    @classmethod
    def normalize_article_source_system(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return None
        return _trim(value)

    @field_validator("requested_quantity")
    @classmethod
    def positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("requested_quantity must be greater than zero")
        return value


class TaquillaAssimilationRequest(BaseModel):
    schema_version: Literal["1.0.0"]
    source_system: str = Field(min_length=1, max_length=40)
    parser_version: str = Field(min_length=1, max_length=80)
    mapping_version: str = Field(min_length=1, max_length=80)
    plan_id: UUID
    taquilla_code: str = Field(min_length=1, max_length=80)
    sequence_no: int = Field(gt=0)
    vehicle_topology: VehicleTopology
    documents: list[TaquillaAssimilationSourceDocument] = Field(
        min_length=1, max_length=2
    )
    lines: list[TaquillaAssimilationSourceLine] = Field(min_length=1)

    _source_system = field_validator("source_system")(_trim)
    _parser_version = field_validator("parser_version")(_trim)
    _mapping_version = field_validator("mapping_version")(_trim)
    _taquilla_code = field_validator("taquilla_code")(_trim)

    @model_validator(mode="after")
    def validate_source_shape(self):
        document_keys = [item.source_document_key for item in self.documents]
        if len(document_keys) != len(set(document_keys)):
            raise ValueError("source_document_key values must be unique")
        document_hashes = [item.sha256 for item in self.documents]
        if len(document_hashes) != len(set(document_hashes)):
            raise ValueError("source document hashes must be unique")

        line_keys = [item.source_line_key for item in self.lines]
        if len(line_keys) != len(set(line_keys)):
            raise ValueError("source_line_key values must be unique")

        known_documents = set(document_keys)
        if any(
            item.source_document_key not in known_documents
            for item in self.lines
        ):
            raise ValueError(
                "every source line must reference a supplied document"
            )

        deck_positions = {item.deck_position for item in self.lines}
        if self.vehicle_topology == "SIMPLE":
            if deck_positions != {"SINGLE"}:
                raise ValueError(
                    "SIMPLE assimilation requires SINGLE on every line"
                )
        else:
            if "SINGLE" in deck_positions:
                raise ValueError(
                    "DOUBLE_DECK assimilation requires explicit UPPER/LOWER"
                )
            if not {"UPPER", "LOWER"}.issubset(deck_positions):
                raise ValueError(
                    "DOUBLE_DECK assimilation must represent both UPPER and LOWER"
                )
        return self


class TaquillaAssimilationBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    target_taquilla_id: UUID | None
    source_system: str
    parser_version: str
    mapping_version: str
    payload_fingerprint: str
    taquilla_code: str
    sequence_no: int
    vehicle_topology: VehicleTopology
    status: AssimilationStatus
    accepted_lines: int
    rejected_lines: int
    imported_by: UUID | None
    imported_at: datetime


class TaquillaAssimilationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    rule_code: str
    severity: AssimilationIssueSeverity
    message: str
    source_document_key: str | None
    source_line_key: str | None
    created_at: datetime


class TaquillaAssimilationResult(BaseModel):
    batch: TaquillaAssimilationBatchRead
    issues: list[TaquillaAssimilationIssueRead]
    target_taquilla_id: UUID | None
    idempotent_replay: bool



class OperationalRoutingProjection(BaseModel):
    routing_revision_id: UUID | None
    binding_mode: RoutingBindingMode | None
    revision_no: int | None
    status: str | None
    effective_at: datetime | None
    override_reason: str | None


class OperationalProductProjection(BaseModel):
    id: UUID
    sequence_no: int
    article_id: UUID
    article_code: str
    article_description: str
    requested_quantity: Decimal
    deck_position: DeckPosition
    source_document_key: str | None
    source_line_key: str | None
    routing: OperationalRoutingProjection


class OperationalTaquillaProjection(BaseModel):
    id: UUID
    taquilla_code: str
    sequence_no: int
    status: TaquillaStatus
    vehicle_topology: VehicleTopology
    historical_completion_classification: HistoricalCompletionClassification | None
    cancellation_reason: str | None
    products: list[OperationalProductProjection]
    product_count: int
    total_requested_quantity: Decimal
    routing_bound_count: int
    routing_missing_count: int


class OperationalPlanProjection(BaseModel):
    id: UUID
    plan_number: str
    description: str | None
    status: PlanStatus
    historical_completion_classification: HistoricalCompletionClassification | None
    cancellation_reason: str | None
    taquillas: list[OperationalTaquillaProjection]
    taquilla_count: int
    product_line_count: int
    routing_missing_count: int
    blocked_taquilla_count: int
