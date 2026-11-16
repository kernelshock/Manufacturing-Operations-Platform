"""G7.6 checks for normalized records supplied by trusted FAIC source adapters.

The source adapter must establish record authenticity, signer authority and
current revision. These checks bind that evidence to the case's exact scope.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from mop.materials.quantity import decimal_quantity
from mop.planning.policy_contracts import EvidenceState, PolicyError


class ReleaseAuthority(StrEnum):
    ENGINEERING = "ENGINEERING"
    LABORATORY = "LABORATORY"
    AREA_LEADER = "AREA_LEADER"


class SupplierClassification(StrEnum):
    PRIMARY = "PRIMARY"
    IN_PROCESS = "IN_PROCESS"
    ALTERNATIVE = "ALTERNATIVE"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class ReceiptScope:
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    receipt_line_ref: str
    lot_ref: str | None = None


@dataclass(frozen=True)
class ReceiptRelease:
    scope: ReceiptScope
    sheet_ref: str
    signer_id: str
    signed_at: datetime
    signature_state: EvidenceState
    authority: ReleaseAuthority
    authority_area_id: UUID | None
    released_quantity: Decimal


def released_receipt_quantity(
    release: ReceiptRelease,
    scope: ReceiptScope,
    *,
    engineering_defined: bool,
    responsible_area_id: UUID | None,
    received_quantity: Decimal,
    as_of: datetime,
) -> Decimal:
    """Return the verified release for a single receipt line and applicable lot."""
    if release.scope != scope or not scope.receipt_line_ref.strip():
        raise PolicyError("release must match the receipt line and lot")
    if scope.lot_ref is not None and not scope.lot_ref.strip():
        raise PolicyError("receipt lot reference cannot be blank")
    if not release.sheet_ref.strip() or not release.signer_id.strip():
        raise PolicyError("release needs a sheet reference and signer identity")
    if release.signature_state != EvidenceState.VERIFIED:
        raise PolicyError("release signature must be verified")
    if as_of.utcoffset() is None or release.signed_at.utcoffset() is None:
        raise PolicyError("release and cutoff need timezone-aware timestamps")
    if release.signed_at > as_of:
        raise PolicyError("release was signed after the cutoff")

    if engineering_defined:
        if release.authority not in (ReleaseAuthority.ENGINEERING, ReleaseAuthority.LABORATORY):
            raise PolicyError("engineering material requires Engineering or Laboratory release")
    elif (
        release.authority != ReleaseAuthority.AREA_LEADER
        or responsible_area_id is None
        or release.authority_area_id != responsible_area_id
    ):
        raise PolicyError("release requires the responsible area leader")

    quantity = decimal_quantity(release.released_quantity, allow_zero=False)
    if quantity > decimal_quantity(received_quantity):
        raise PolicyError("release quantity exceeds the received quantity")
    return quantity


@dataclass(frozen=True)
class SupplierScope:
    supplier_id: UUID
    plant_id: UUID
    article_id: UUID
    uom_id: UUID


@dataclass(frozen=True)
class SupplierEvaluation:
    scope: SupplierScope
    evaluation_ref: str
    verification: EvidenceState


@dataclass(frozen=True)
class SupplierClassificationRecord:
    scope: SupplierScope
    classification_ref: str
    evaluation_ref: str
    classification: SupplierClassification
    verification: EvidenceState


@dataclass(frozen=True)
class SupplierCapacity:
    scope: SupplierScope
    capacity_ref: str
    evaluation_ref: str
    verification: EvidenceState
    confirmed_quantity: Decimal
    confirmed_delivery_date: date


def verify_alternative_supplier(
    scope: SupplierScope,
    evaluation: SupplierEvaluation,
    classification: SupplierClassificationRecord,
    capacity: SupplierCapacity,
    *,
    required_quantity: Decimal,
    delivery_deadline: date,
) -> tuple[str, str, str]:
    """Return provenance for a verified alternative with scenario-specific capacity."""
    if any(record.scope != scope for record in (evaluation, classification, capacity)):
        raise PolicyError("supplier evidence must match the case scope")
    if any(record.verification != EvidenceState.VERIFIED
           for record in (evaluation, classification, capacity)):
        raise PolicyError("evaluation, classification and capacity must be verified")

    references = (evaluation.evaluation_ref, classification.classification_ref, capacity.capacity_ref)
    if any(not reference.strip() for reference in references):
        raise PolicyError("supplier evidence needs document references")
    if evaluation.evaluation_ref == classification.classification_ref:
        raise PolicyError("evaluation and classification must be separate documents")
    if evaluation.evaluation_ref != classification.evaluation_ref or (
        evaluation.evaluation_ref != capacity.evaluation_ref
    ):
        raise PolicyError("classification and capacity must trace to the evaluation")
    if classification.classification != SupplierClassification.ALTERNATIVE:
        raise PolicyError("supplier is not classified as an alternative")
    if decimal_quantity(capacity.confirmed_quantity) < decimal_quantity(required_quantity, allow_zero=False):
        raise PolicyError("confirmed supplier capacity is below the requested quantity")
    if capacity.confirmed_delivery_date > delivery_deadline:
        raise PolicyError("confirmed supplier delivery misses the deadline")
    return references
