"""G7.5 — Deterministic replenishment quantity scenarios (NO purchase execution).

A scenario is a proposal for human review, never an executable PO or ATP promise.
Incoming supply is subtractable only when independently confirmed for this plant,
article and canonical UoM. Partial Prolowin captures do not satisfy that contract.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Literal
from uuid import UUID

from mop.planning.policy_contracts import (
    EvidenceState, PlanningPolicy, PolicyError, RecommendationState,
    ReplenishmentMethod,
)
from mop.planning.reorder_point import ReorderPointResult, _positive_decimal


@dataclass(frozen=True)
class SupplierTerms:
    supplier_code: str
    article_id: UUID
    uom_id: UUID
    minimum_quantity: Decimal
    pack_multiple: Decimal
    verified: EvidenceState
    evidence_reference: str

    def __post_init__(self):
        if not self.supplier_code.strip() or not self.evidence_reference.strip():
            raise PolicyError("supplier terms require source identity and evidence reference")
        _positive_decimal("minimum_quantity", self.minimum_quantity)
        _positive_decimal("pack_multiple", self.pack_multiple)


@dataclass(frozen=True)
class IncomingPosition:
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    quantity: Decimal | None
    state: EvidenceState
    evidence_reference: str | None

    def __post_init__(self):
        if self.quantity is not None:
            _positive_decimal("incoming_quantity", self.quantity, allow_zero=True)
        if self.state == EvidenceState.VERIFIED:
            if self.quantity is None or not self.evidence_reference or not self.evidence_reference.strip():
                raise PolicyError("confirmed incoming requires quantity and independent provenance")


@dataclass(frozen=True)
class ReplenishmentScenario:
    scenario_key: str
    supplier_code: str | None
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    method: ReplenishmentMethod
    state: RecommendationState
    target_coverage_business_days: int
    demand_rate: Decimal | None
    expected_coverage_demand: Decimal | None
    safety_stock: Decimal | None
    target_stock: Decimal | None
    quality_unallocated: Decimal | None
    confirmed_incoming: Decimal | None
    deficit: Decimal | None
    raw_quantity: Decimal | None
    suggested_quantity: Decimal | None
    minimum_quantity: Decimal | None
    pack_multiple: Decimal | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    purchase_order_effect: Literal["NONE"] = "NONE"
    inventory_effect: Literal["NONE"] = "NONE"
    approval: Literal["HUMAN_REVIEW_REQUIRED"] = "HUMAN_REVIEW_REQUIRED"


def _ceil_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    return (value / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple


def calculate_replenishment(
    scenario_key: str,
    policy: PlanningPolicy,
    point: ReorderPointResult,
    terms: SupplierTerms | None,
    incoming: IncomingPosition,
    *,
    coverage_business_days: int | None = None,
) -> ReplenishmentScenario:
    """Compare FIXED or CALCULATED C.R. with supplier terms and confirmed incoming.

    CALCULATED target = daily demand × target coverage days + safety stock.
    This *target-level* model is not a time-phased MRP projection; no open PO is
    presumed confirmed incoming. HOLD is already excluded from quality_unallocated.
    """
    if not scenario_key.strip():
        raise PolicyError("scenario requires a stable identity")
    if (point.plant_id != policy.plant_id or
            (incoming.plant_id, incoming.article_id, incoming.uom_id) !=
            (point.plant_id, point.article_id, point.uom_id)):
        raise PolicyError("scenario would mix plants, articles or canonical units")
    if terms is not None and (terms.article_id, terms.uom_id) != (
            point.article_id, point.uom_id):
        raise PolicyError("supplier terms mismatch article or canonical UoM")
    days = policy.horizon_business_days if coverage_business_days is None else coverage_business_days
    if type(days) is not int or days <= 0:
        raise PolicyError("coverage horizon must be positive integer business days")
    blockers = list(point.blockers)
    warnings = list(point.warnings)

    if point.state == RecommendationState.BLOCKED:
        blockers.append("REORDER_POINT_NOT_READY")
    if point.state == RecommendationState.PROVISIONAL:
        warnings.append("REORDER_POINT_PROVISIONAL")
    if point.daily_demand is None or point.safety_stock is None:
        blockers.append("TARGET_DEMAND_OR_SAFETY_UNKNOWN")
    if point.known_quality_unallocated is None:
        blockers.append("QUALITY_UNALLOCATED_UNKNOWN")
    if terms is None:
        blockers.append("SUPPLIER_TERMS_MISSING")
    elif terms.verified != EvidenceState.VERIFIED:
        blockers.append("SUPPLIER_TERMS_NOT_VERIFIED")

    if incoming.state != EvidenceState.VERIFIED or incoming.quantity is None:
        blockers.append("PLANT_INCOMING_NOT_CONFIRMED")
    if policy.replenishment_method == ReplenishmentMethod.FIXED:
        if policy.fixed_replenishment_quantity is None:
            blockers.append("FIXED_CR_MISSING")
    elif policy.replenishment_method != ReplenishmentMethod.CALCULATED:
        raise PolicyError("unsupported replenishment method")

    target_demand = (point.daily_demand * Decimal(days)
                     if point.daily_demand is not None else None)
    target = (target_demand + point.safety_stock
              if target_demand is not None and point.safety_stock is not None else None)
    deficit = (max(Decimal("0"), target - point.known_quality_unallocated - incoming.quantity)
               if target is not None and point.known_quality_unallocated is not None
               and incoming.state == EvidenceState.VERIFIED and incoming.quantity is not None
               else None)
    raw = (policy.fixed_replenishment_quantity
           if policy.replenishment_method == ReplenishmentMethod.FIXED
           else deficit)
    if (policy.replenishment_method == ReplenishmentMethod.FIXED and
            deficit == Decimal("0")):
        warnings.append("FIXED_QUANTITY_DESPITE_NO_CALCULATED_DEFICIT")

    quantity = None
    if not blockers and raw is not None and terms is not None:
        if raw == Decimal("0"):
            quantity = raw
        elif policy.replenishment_method == ReplenishmentMethod.FIXED:
            # A fixed quantity is a user-governed choice: do not silently rewrite it.
            if raw < terms.minimum_quantity or raw % terms.pack_multiple != 0:
                blockers.append("FIXED_CR_CONFLICTS_WITH_VERIFIED_SUPPLIER_TERMS")
            else:
                quantity = raw
        else:
            quantity = _ceil_multiple(
                max(raw, terms.minimum_quantity), terms.pack_multiple)
            if quantity > raw:
                warnings.append("QUANTITY_ROUNDED_TO_VERIFIED_SUPPLIER_TERMS")

    status = (RecommendationState.BLOCKED if blockers else
              RecommendationState.PROVISIONAL if warnings else
              RecommendationState.READY_FOR_REVIEW)
    return ReplenishmentScenario(
        scenario_key=scenario_key, supplier_code=terms.supplier_code if terms else None,
        plant_id=point.plant_id, article_id=point.article_id, uom_id=point.uom_id,
        method=policy.replenishment_method, state=status,
        target_coverage_business_days=days,
        demand_rate=point.daily_demand, expected_coverage_demand=target_demand,
        safety_stock=point.safety_stock, target_stock=target,
        quality_unallocated=point.known_quality_unallocated,
        confirmed_incoming=incoming.quantity if incoming.state == EvidenceState.VERIFIED else None,
        deficit=deficit, raw_quantity=raw if not blockers else None,
        suggested_quantity=quantity,
        minimum_quantity=terms.minimum_quantity if terms else None,
        pack_multiple=terms.pack_multiple if terms else None,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def compare_scenarios(scenarios: tuple[ReplenishmentScenario, ...]) -> tuple[ReplenishmentScenario, ...]:
    """Stable grouping for human comparison, not supplier ranking or auto-selection."""
    keys = [s.scenario_key for s in scenarios]
    if len(keys) != len(set(keys)):
        raise PolicyError("duplicate scenario key")
    if scenarios:
        base = (scenarios[0].plant_id, scenarios[0].article_id, scenarios[0].uom_id)
        if any((s.plant_id, s.article_id, s.uom_id) != base for s in scenarios):
            raise PolicyError("scenario comparison cannot mix plants, articles or UoMs")
    return tuple(sorted(scenarios, key=lambda s: s.scenario_key))
