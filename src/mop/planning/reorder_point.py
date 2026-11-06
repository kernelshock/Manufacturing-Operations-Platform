"""G7.4 deterministic reorder-point policy scenarios (NO purchase execution).

The input is deliberately a source-verified demand-rate *scenario*, not an
inventory/ERP ingestion endpoint. G7.3 sampled Prolowin history is never
automatically promoted to a statistically representative lead-time sample.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal
from uuid import UUID

from mop.planning.policy_contracts import (
    ConsumptionBasis, EvidenceState, PlanningFacts, PlanningPolicy, PolicyError,
    RecommendationState, SafetyMethod, assess_planning_readiness,
)

ZERO = Decimal("0")
MIN_VARIABILITY_OBSERVATIONS = 12


def _positive_decimal(name: str, value: Decimal, *, allow_zero: bool = False) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise PolicyError(f"{name} requires a finite Decimal")
    if value < ZERO or (value == ZERO and not allow_zero):
        raise PolicyError(f"{name} must be {'nonnegative' if allow_zero else 'positive'}")
    return value


@dataclass(frozen=True)
class DemandRate:
    """One source-identified *daily* material rate for one plant/article/unit.

    Values describing the same underlying demand cannot be added together
    simply because they were normalized per product and per seat.
    """
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    basis: ConsumptionBasis
    source_key: str
    daily_quantity: Decimal
    evidence_state: EvidenceState

    def __post_init__(self):
        if self.basis == ConsumptionBasis.BOTH:
            raise PolicyError("BOTH is a comparison mode, not a consumption source")
        if not self.source_key.strip():
            raise PolicyError("a traceable demand source key is required")
        _positive_decimal("daily_quantity", self.daily_quantity, allow_zero=True)


@dataclass(frozen=True)
class VariabilityEvidence:
    demand_std_daily: Decimal
    lead_time_std_business_days: Decimal
    service_factor_z: Decimal
    demand_observations: int
    completed_supplier_orders: int
    representative_coverage: EvidenceState

    def __post_init__(self):
        for name in ("demand_std_daily", "lead_time_std_business_days", "service_factor_z"):
            _positive_decimal(name, getattr(self, name), allow_zero=True)
        if self.demand_observations < 0 or self.completed_supplier_orders < 0:
            raise PolicyError("observation counts must be nonnegative")


@dataclass(frozen=True)
class ReorderPointResult:
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    method: SafetyMethod
    input_basis: ConsumptionBasis
    selected_demand_source: str | None
    daily_demand: Decimal | None
    lead_time_business_days: Decimal | None
    lead_time_demand: Decimal | None
    safety_stock: Decimal | None
    reorder_point: Decimal | None
    known_quality_unallocated: Decimal | None
    state: RecommendationState
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    candidate_demand_sources: tuple[str, ...]
    purchase_order_effect: Literal["NONE"] = "NONE"
    physical_stock_effect: Literal["NONE"] = "NONE"
    operational_purchase_trigger: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"


def project_reorder_point(
    policy: PlanningPolicy,
    facts: PlanningFacts,
    rates: tuple[DemandRate, ...],
    lead_days: Decimal | None,
    *,
    selected_source_key: str | None = None,
    variability: VariabilityEvidence | None = None,
) -> ReorderPointResult:
    """Calculate only source-qualified threshold scenarios.

    Percentage: expected lead-time use × configured safety percentage.
    Variability: z × sqrt(lead_days × daily_demand_std² +
                         daily_demand² × supplier_lead_time_std²).
    The latter is explicitly blocked without representative samples. The
    formula assumes independence; applicability requires later data review.
    """
    assessed = assess_planning_readiness(policy, facts)
    blockers = list(assessed.blockers)
    warnings = list(assessed.warnings)
    matched = []
    seen = set()
    for rate in rates:
        if (rate.plant_id, rate.article_id, rate.uom_id) != (
            policy.plant_id, facts.article_id, facts.uom_id
        ):
            raise PolicyError("demand rate does not match plant, article and canonical unit")
        if rate.source_key in seen:
            raise PolicyError("duplicate demand source key risks double counting")
        seen.add(rate.source_key)
        if policy.consumption_basis != ConsumptionBasis.BOTH and rate.basis != policy.consumption_basis:
            raise PolicyError("demand source basis conflicts with selected policy")
        matched.append(rate)
    keys = tuple(rate.source_key for rate in matched)
    chosen = next((rate for rate in matched if rate.source_key == selected_source_key), None)
    if not matched:
        blockers.append("DEMAND_HISTORY_MISSING")
    elif selected_source_key is None:
        if len(matched) == 1:
            chosen = matched[0]
        else:
            blockers.append("DEMAND_SOURCE_SELECTION_REQUIRED")
    elif chosen is None:
        blockers.append("DEMAND_SOURCE_NOT_FOUND")

    if chosen is not None:
        if chosen.evidence_state == EvidenceState.UNKNOWN:
            blockers.append("DEMAND_EVIDENCE_UNKNOWN")
        elif chosen.evidence_state == EvidenceState.PARTIAL:
            warnings.append("DEMAND_EVIDENCE_PARTIAL")
    if lead_days is None:
        blockers.append("SUPPLIER_LEAD_TIME_VALUE_MISSING")
    else:
        _positive_decimal("lead_days", lead_days)
    if variability is not None and policy.safety_method != SafetyMethod.VARIABILITY:
        raise PolicyError("variability inputs cannot be silently used with percentage policy")

    if policy.safety_method == SafetyMethod.VARIABILITY:
        if variability is None:
            blockers.append("VARIABILITY_EVIDENCE_MISSING")
        else:
            if variability.representative_coverage != EvidenceState.VERIFIED:
                blockers.append("VARIABILITY_COVERAGE_NOT_VERIFIED")
            if variability.demand_observations < MIN_VARIABILITY_OBSERVATIONS:
                blockers.append("DEMAND_SAMPLE_TOO_SMALL")
            if variability.completed_supplier_orders < MIN_VARIABILITY_OBSERVATIONS:
                blockers.append("LEAD_TIME_SAMPLE_TOO_SMALL")
            if variability.service_factor_z == ZERO:
                blockers.append("SERVICE_FACTOR_NOT_SELECTED")

    result_ready = not blockers
    rate = chosen.daily_quantity if chosen else None
    lead_demand = safety = point = None
    if result_ready and rate is not None and lead_days is not None:
        lead_demand = rate * lead_days
        if policy.safety_method == SafetyMethod.PERCENTAGE:
            safety = lead_demand * policy.safety_percentage
        else:
            assert variability is not None
            safety = variability.service_factor_z * (
                lead_days * variability.demand_std_daily ** 2
                + rate ** 2 * variability.lead_time_std_business_days ** 2
            ).sqrt()
        point = lead_demand + safety
    state = (RecommendationState.BLOCKED if blockers else
             RecommendationState.PROVISIONAL if warnings else
             RecommendationState.READY_FOR_REVIEW)
    return ReorderPointResult(
        plant_id=policy.plant_id, article_id=facts.article_id, uom_id=facts.uom_id,
        method=policy.safety_method, input_basis=policy.consumption_basis,
        selected_demand_source=chosen.source_key if chosen else None,
        daily_demand=rate, lead_time_business_days=lead_days,
        lead_time_demand=lead_demand, safety_stock=safety, reorder_point=point,
        known_quality_unallocated=assessed.quality_unallocated,
        state=state, blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)), candidate_demand_sources=keys,
    )
