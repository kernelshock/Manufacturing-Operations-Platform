"""G7.1 deterministic synthetic acceptance. No database and no purchasing writes."""
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.planning.policy_contracts import (
    ConsumptionBasis, EvidenceState, PlanningFacts, PlanningPolicy,
    PolicyError, RecommendationState, ReplenishmentMethod, SafetyMethod,
    assess_planning_readiness,
)


PLANT, OTHER_PLANT, ARTICLE, UOM = (uuid4() for _ in range(4))


def policy(**kwargs):
    return PlanningPolicy(plant_id=PLANT, calendar_code="FAIC-ROS-BUSINESS", **kwargs)


def facts(**overrides):
    values = dict(
        plant_id=PLANT, article_id=ARTICLE, uom_id=UOM,
        physical_on_hand=Decimal("20"), active_holds=Decimal("16"),
        quality_usable=Decimal("18"), source_coverage=EvidenceState.VERIFIED,
        supplier_lead_time=EvidenceState.VERIFIED, business_calendar_verified=True,
        source_paths=("BOM-MOONRAKER-TQ1", "BOM-APOLLO-TQ2"),
    )
    values.update(overrides)
    return PlanningFacts(**values)


def test_complete_review_only_no_purchase_effect():
    result = assess_planning_readiness(policy(), facts())
    assert result.state == RecommendationState.READY_FOR_REVIEW
    assert result.quality_unallocated == Decimal("2")
    assert result.purchase_order_effect == "NONE"
    assert not result.blockers


def test_zero_known_not_unknown_and_policy_25_percent_is_only_default():
    result = assess_planning_readiness(policy(), facts(
        physical_on_hand=Decimal("0"), quality_usable=Decimal("0"), active_holds=Decimal("0"),
    ))
    assert result.state == RecommendationState.READY_FOR_REVIEW
    assert result.quality_unallocated == Decimal("0")
    assert policy().safety_percentage == Decimal("0.25")
    assert policy(safety_percentage=Decimal("0.10")).safety_percentage == Decimal("0.10")


def test_unknown_physical_and_quality_fail_closed():
    state = assess_planning_readiness(policy(), facts(
        physical_on_hand=None, quality_usable=None,
    ))
    assert state.state == RecommendationState.BLOCKED
    assert "PHYSICAL_STOCK_UNKNOWN" in state.blockers
    assert "QUALITY_USABLE_UNKNOWN" in state.blockers
    assert state.quality_unallocated is None


def test_partially_transcribed_prolowin_is_not_verified_history():
    state = assess_planning_readiness(policy(), facts(
        source_coverage=EvidenceState.PARTIAL, supplier_lead_time=EvidenceState.PARTIAL,
    ))
    assert state.state == RecommendationState.PROVISIONAL
    assert set(state.warnings) == {"SOURCE_COVERAGE_PARTIAL", "SUPPLIER_HISTORY_PARTIAL"}
    assert state.purchase_order_effect == "NONE"


def test_variability_model_needs_verified_supplier_history():
    result = assess_planning_readiness(
        policy(safety_method=SafetyMethod.VARIABILITY),
        facts(supplier_lead_time=EvidenceState.PARTIAL),
    )
    assert result.state == RecommendationState.BLOCKED
    assert "VARIABILITY_CANNOT_BE_ESTIMATED_FROM_PARTIAL_HISTORY" in result.blockers


def test_missing_supplier_and_business_calendar_block_recommendation():
    result = assess_planning_readiness(policy(), facts(
        supplier_lead_time=EvidenceState.UNKNOWN, business_calendar_verified=False,
    ))
    assert result.state == RecommendationState.BLOCKED
    assert "SUPPLIER_LEAD_TIME_UNKNOWN" in result.blockers
    assert "BUSINESS_CALENDAR_UNVERIFIED" in result.blockers


def test_plant_segregation_for_shared_bom_material():
    with pytest.raises(PolicyError, match="different plant"):
        assess_planning_readiness(policy(), facts(plant_id=OTHER_PLANT))


@pytest.mark.parametrize("invalid", [
    {"calendar_code": " "},
    {"horizon_business_days": 0},
    {"safety_percentage": Decimal("-0.01")},
    {"safety_percentage": Decimal("1.01")},
    {"safety_percentage": 0.25},
    {"auto_issue_purchase_order": True},
    {"require_quality_evidence": False},
    {"replenishment_method": ReplenishmentMethod.FIXED},
    {"fixed_replenishment_quantity": Decimal("4")},
    {"replenishment_method": ReplenishmentMethod.FIXED,
     "fixed_replenishment_quantity": Decimal("0")},
])
def test_invalid_or_unsafe_policy_fails_closed(invalid):
    with pytest.raises(PolicyError):
        policy(**invalid)


def test_fixed_quantity_and_both_consumption_bases_are_explicit():
    p = policy(
        consumption_basis=ConsumptionBasis.BOTH,
        replenishment_method=ReplenishmentMethod.FIXED,
        fixed_replenishment_quantity=Decimal("30"),
    )
    assert p.fixed_replenishment_quantity == Decimal("30")
    assert p.consumption_basis == ConsumptionBasis.BOTH


@pytest.mark.parametrize("invalid", [
    {"physical_on_hand": Decimal("-1")},
    {"active_holds": Decimal("21")},
    {"quality_usable": Decimal("21")},
    {"physical_on_hand": 0.1},
])
def test_inventory_facts_reject_invalid_quantities(invalid):
    with pytest.raises(PolicyError):
        facts(**invalid)


def test_no_synthetic_supplier_receipts_promoted_to_physical():
    # G7.1 contains no inbound/PO argument and cannot create physical on-hand
    # from a verified Prolowin order or even a source-reported receipt.
    incomplete = facts(physical_on_hand=None, quality_usable=None,
                       supplier_lead_time=EvidenceState.VERIFIED)
    result = assess_planning_readiness(policy(), incomplete)
    assert result.state == RecommendationState.BLOCKED
    assert result.purchase_order_effect == "NONE"
