"""G7.1 policy contracts; pure/read-only, no stock, PO or ERP side effects.

Not a reorder-point or replenishment algorithm. The contract fails closed when
Quality, supplier history or plant scope is missing. G7.2+ may consume it.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from mop.materials.quantity import decimal_quantity, MaterialQuantityError


class PolicyError(ValueError):
    """The requested planning policy or facts cannot support a reliable decision."""


class EvidenceState(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class RecommendationState(StrEnum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    PROVISIONAL = "PROVISIONAL"
    BLOCKED = "BLOCKED"


class ConsumptionBasis(StrEnum):
    PER_PRODUCT = "PER_PRODUCT"
    PER_SEAT = "PER_SEAT"
    BOTH = "BOTH"


class ReplenishmentMethod(StrEnum):
    FIXED = "FIXED"
    CALCULATED = "CALCULATED"


class SafetyMethod(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    VARIABILITY = "VARIABILITY"


@dataclass(frozen=True)
class PlanningPolicy:
    plant_id: UUID
    calendar_code: str
    consumption_basis: ConsumptionBasis = ConsumptionBasis.BOTH
    replenishment_method: ReplenishmentMethod = ReplenishmentMethod.CALCULATED
    safety_method: SafetyMethod = SafetyMethod.PERCENTAGE
    safety_percentage: Decimal = Decimal("0.25")
    horizon_business_days: int = 15
    fixed_replenishment_quantity: Decimal | None = None
    require_quality_evidence: bool = True
    auto_issue_purchase_order: bool = False

    def __post_init__(self) -> None:
        if not self.calendar_code.strip():
            raise PolicyError("a plant business-day calendar must be explicitly identified")
        if self.horizon_business_days <= 0:
            raise PolicyError("business-day horizon must be positive")
        try:
            safety = decimal_quantity(self.safety_percentage)
        except MaterialQuantityError as exc:
            raise PolicyError(str(exc)) from exc
        if safety > 1:
            raise PolicyError("safety percentage must be between 0 and 1")
        object.__setattr__(self, "safety_percentage", safety)
        if self.replenishment_method == ReplenishmentMethod.FIXED:
            if self.fixed_replenishment_quantity is None:
                raise PolicyError("fixed CR requires an explicit quantity")
            try:
                fixed = decimal_quantity(self.fixed_replenishment_quantity, allow_zero=False)
            except MaterialQuantityError as exc:
                raise PolicyError(str(exc)) from exc
            object.__setattr__(self, "fixed_replenishment_quantity", fixed)
        elif self.fixed_replenishment_quantity is not None:
            raise PolicyError("fixed CR quantity cannot silently override calculated CR")
        if not self.require_quality_evidence:
            raise PolicyError("G7 must not assume physical equals Quality-usable inventory")
        if self.auto_issue_purchase_order:
            raise PolicyError("G7.1 does not authorize automatic purchase order issuance")


@dataclass(frozen=True)
class PlanningFacts:
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    physical_on_hand: Decimal | None
    active_holds: Decimal
    quality_usable: Decimal | None
    source_coverage: EvidenceState
    supplier_lead_time: EvidenceState
    business_calendar_verified: bool
    source_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("physical_on_hand", "quality_usable", "active_holds"):
            value = getattr(self, field)
            if value is not None:
                try:
                    normalized = decimal_quantity(value)
                except MaterialQuantityError as exc:
                    raise PolicyError(f"{field}: {exc}") from exc
                object.__setattr__(self, field, normalized)
        if self.physical_on_hand is not None and self.quality_usable is not None:
            if self.quality_usable > self.physical_on_hand:
                raise PolicyError("Quality-usable stock cannot exceed known physical stock")
        if self.physical_on_hand is not None and self.active_holds > self.physical_on_hand:
            raise PolicyError("active holds cannot exceed known physical stock")


@dataclass(frozen=True)
class DecisionAssessment:
    state: RecommendationState
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    quality_unallocated: Decimal | None
    purchase_order_effect: Literal["NONE"] = "NONE"


def assess_planning_readiness(policy: PlanningPolicy, facts: PlanningFacts) -> DecisionAssessment:
    """Classify evidence only; NEVER infer unknown stock, supplier delay or Quality."""
    if policy.plant_id != facts.plant_id:
        raise PolicyError("cannot pool inventory or requirements from a different plant")
    blockers: list[str] = []
    warnings: list[str] = []
    if facts.physical_on_hand is None:
        blockers.append("PHYSICAL_STOCK_UNKNOWN")
    if facts.quality_usable is None:
        blockers.append("QUALITY_USABLE_UNKNOWN")
    if not facts.business_calendar_verified:
        blockers.append("BUSINESS_CALENDAR_UNVERIFIED")
    if facts.supplier_lead_time == EvidenceState.UNKNOWN:
        blockers.append("SUPPLIER_LEAD_TIME_UNKNOWN")
    elif facts.supplier_lead_time == EvidenceState.PARTIAL:
        warnings.append("SUPPLIER_HISTORY_PARTIAL")
    if facts.source_coverage == EvidenceState.UNKNOWN:
        blockers.append("SOURCE_COVERAGE_UNKNOWN")
    elif facts.source_coverage == EvidenceState.PARTIAL:
        warnings.append("SOURCE_COVERAGE_PARTIAL")
    if policy.safety_method == SafetyMethod.VARIABILITY and (
        facts.supplier_lead_time != EvidenceState.VERIFIED
    ):
        blockers.append("VARIABILITY_CANNOT_BE_ESTIMATED_FROM_PARTIAL_HISTORY")
    usable = (max(Decimal("0"), facts.quality_usable - facts.active_holds)
              if facts.quality_usable is not None and facts.physical_on_hand is not None else None)
    state = (RecommendationState.BLOCKED if blockers else
             RecommendationState.PROVISIONAL if warnings else
             RecommendationState.READY_FOR_REVIEW)
    return DecisionAssessment(state, tuple(blockers), tuple(warnings), usable)
