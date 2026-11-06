"""G7.4 exact Decimal PP / stock-safety policy scenarios; no integration writes."""
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.planning.policy_contracts import (
    ConsumptionBasis, EvidenceState, PlanningFacts, PlanningPolicy,
    PolicyError, RecommendationState, SafetyMethod,
)
from mop.planning.reorder_point import (
    DemandRate, VariabilityEvidence, project_reorder_point,
)

PLANT, OTHER, ARTICLE, UOM = (uuid4() for _ in range(4))


def policy(**kwargs):
    data = dict(plant_id=PLANT, calendar_code="FAIC-BUSINESS")
    data.update(kwargs)
    return PlanningPolicy(**data)


def facts(**kwargs):
    data = dict(
        plant_id=PLANT, article_id=ARTICLE, uom_id=UOM,
        physical_on_hand=Decimal("100"), active_holds=Decimal("20"),
        quality_usable=Decimal("90"), source_coverage=EvidenceState.VERIFIED,
        supplier_lead_time=EvidenceState.VERIFIED, business_calendar_verified=True,
    )
    data.update(kwargs)
    return PlanningFacts(**data)


def rate(key="MOONRAKER", amount="4", basis=ConsumptionBasis.PER_PRODUCT, **kw):
    data=dict(plant_id=PLANT, article_id=ARTICLE, uom_id=UOM, basis=basis,
              source_key=key, daily_quantity=Decimal(amount),
              evidence_state=EvidenceState.VERIFIED)
    data.update(kw)
    return DemandRate(**data)


def var(**kwargs):
    data=dict(demand_std_daily=Decimal("2"), lead_time_std_business_days=Decimal("1"),
              service_factor_z=Decimal("2"), demand_observations=18,
              completed_supplier_orders=18, representative_coverage=EvidenceState.VERIFIED)
    data.update(kwargs)
    return VariabilityEvidence(**data)


def test_percentage_baseline_expected_lead_time_demand_and_safety():
    result = project_reorder_point(policy(), facts(), (rate(),), Decimal("15"))
    assert result.state == RecommendationState.READY_FOR_REVIEW
    assert result.lead_time_demand == Decimal("60")
    assert result.safety_stock == Decimal("15")
    assert result.reorder_point == Decimal("75")
    assert result.known_quality_unallocated == Decimal("70")
    assert result.operational_purchase_trigger == "NOT_EVALUATED"
    assert result.purchase_order_effect == "NONE"


def test_percentage_can_be_changed_without_mutating_stock():
    result=project_reorder_point(
        policy(safety_percentage=Decimal("0.10")), facts(),
        (rate(amount="4.5"),), Decimal("10"),
    )
    assert result.lead_time_demand==Decimal("45")
    assert result.safety_stock==Decimal("4.5")
    assert result.reorder_point==Decimal("49.5")
    assert result.physical_stock_effect=="NONE"


def test_both_consumption_bases_must_choose_nonduplicated_source():
    sources=(rate("MOP-BOM-MOONRAKER",amount="4"),
             rate("MOP-HISTORY-PER-SEAT",amount="3",
                  basis=ConsumptionBasis.PER_SEAT))
    ambiguous=project_reorder_point(policy(),facts(),sources,Decimal("15"))
    assert ambiguous.state==RecommendationState.BLOCKED
    assert "DEMAND_SOURCE_SELECTION_REQUIRED" in ambiguous.blockers
    assert ambiguous.reorder_point is None
    chosen=project_reorder_point(policy(),facts(),sources,Decimal("15"),
                                 selected_source_key="MOP-HISTORY-PER-SEAT")
    assert chosen.reorder_point==Decimal("56.25")
    assert chosen.daily_demand==Decimal("3")


def test_partial_manual_history_produces_provisional_percentage_result():
    result=project_reorder_point(policy(),facts(source_coverage=EvidenceState.PARTIAL,
         supplier_lead_time=EvidenceState.PARTIAL),
         (rate(evidence_state=EvidenceState.PARTIAL),),Decimal("12"))
    assert result.state==RecommendationState.PROVISIONAL
    assert result.reorder_point==Decimal("60")
    assert "SOURCE_COVERAGE_PARTIAL" in result.warnings
    assert "DEMAND_EVIDENCE_PARTIAL" in result.warnings


def test_variability_formula_decimal_exact_for_perfect_square():
    result=project_reorder_point(
        policy(safety_method=SafetyMethod.VARIABILITY),
        facts(), (rate(amount="4"),), Decimal("5"),
        variability=var(demand_std_daily=Decimal("3"),
                        lead_time_std_business_days=Decimal("1.5")),
    )
    # sqrt(5*9 + 4^2*1.5^2)=sqrt(81)=9; z=2 -> safety 18
    assert result.state==RecommendationState.READY_FOR_REVIEW
    assert result.lead_time_demand==Decimal("20")
    assert result.safety_stock==Decimal("18")
    assert result.reorder_point==Decimal("38")


@pytest.mark.parametrize("v,reason",[
    (var(demand_observations=11),"DEMAND_SAMPLE_TOO_SMALL"),
    (var(completed_supplier_orders=11),"LEAD_TIME_SAMPLE_TOO_SMALL"),
    (var(representative_coverage=EvidenceState.PARTIAL),"VARIABILITY_COVERAGE_NOT_VERIFIED"),
    (var(service_factor_z=Decimal("0")),"SERVICE_FACTOR_NOT_SELECTED"),
])
def test_variability_requires_representative_history(v,reason):
    r=project_reorder_point(policy(safety_method=SafetyMethod.VARIABILITY),
                            facts(),(rate(),),Decimal("5"),variability=v)
    assert r.state==RecommendationState.BLOCKED
    assert reason in r.blockers
    assert r.reorder_point is None


def test_g73_partial_supplier_sample_must_not_enable_variability():
    r=project_reorder_point(policy(safety_method=SafetyMethod.VARIABILITY),
          facts(supplier_lead_time=EvidenceState.PARTIAL),
          (rate(),),Decimal("5"),variability=var())
    assert r.state==RecommendationState.BLOCKED
    assert "VARIABILITY_CANNOT_BE_ESTIMATED_FROM_PARTIAL_HISTORY" in r.blockers


@pytest.mark.parametrize("override,reason",[
    ({"physical_on_hand":None, "quality_usable":None},"PHYSICAL_STOCK_UNKNOWN"),
    ({"quality_usable":None},"QUALITY_USABLE_UNKNOWN"),
    ({"business_calendar_verified":False},"BUSINESS_CALENDAR_UNVERIFIED"),
    ({"supplier_lead_time":EvidenceState.UNKNOWN},"SUPPLIER_LEAD_TIME_UNKNOWN"),
])
def test_missing_operational_inputs_block_point(override,reason):
    result=project_reorder_point(policy(),facts(**override),(rate(),),Decimal("5"))
    assert result.reorder_point is None
    assert reason in result.blockers


def test_missing_lead_days_or_rate_blocks_without_fake_zero():
    missing=project_reorder_point(policy(),facts(),(rate(),),None)
    assert missing.reorder_point is None
    assert "SUPPLIER_LEAD_TIME_VALUE_MISSING" in missing.blockers
    no_source=project_reorder_point(policy(),facts(),(),Decimal("5"))
    assert "DEMAND_HISTORY_MISSING" in no_source.blockers
    assert no_source.reorder_point is None


def test_known_zero_demand_and_zero_stock_are_not_unknown():
    r=project_reorder_point(policy(),facts(physical_on_hand=Decimal("0"),
         quality_usable=Decimal("0"),active_holds=Decimal("0")),
         (rate(amount="0"),),Decimal("4"))
    assert r.state==RecommendationState.READY_FOR_REVIEW
    assert r.reorder_point==Decimal("0")
    assert r.known_quality_unallocated==Decimal("0")


@pytest.mark.parametrize("sources",[
    (rate("SAME"), rate("SAME")),
    (rate("WRONG-PLANT",plant_id=OTHER),),
    (rate("WRONG-UNIT",uom_id=uuid4()),),
    (rate("WRONG-BASIS",basis=ConsumptionBasis.PER_SEAT),),
])
def test_invalid_identity_duplicate_or_basis_is_rejected(sources):
    with pytest.raises(PolicyError):
        project_reorder_point(
            policy(consumption_basis=ConsumptionBasis.PER_PRODUCT),
            facts(), sources, Decimal("5"),
        )


@pytest.mark.parametrize("value",[
    Decimal("NaN"), Decimal("-1"), Decimal("Infinity"), Decimal("0.0"),
    5.5,
])
def test_bad_lead_days_refused(value):
    with pytest.raises(PolicyError):
        project_reorder_point(policy(),facts(),(rate(),),value)


def test_unknown_or_invalid_rate_and_variability_rejected():
    with pytest.raises(PolicyError):
        rate(amount="-1")
    with pytest.raises(PolicyError):
        rate(amount="NaN")
    with pytest.raises(PolicyError):
        var(demand_std_daily=Decimal("-1"))
    with pytest.raises(PolicyError):
        project_reorder_point(policy(),facts(),(rate(),),Decimal("5"),
                              variability=var())


def test_zero_quality_unallocated_is_not_auto_purchase_trigger():
    result=project_reorder_point(policy(),facts(physical_on_hand=Decimal("80"),
       quality_usable=Decimal("20"),active_holds=Decimal("20")),
       (rate(),),Decimal("15"))
    assert result.known_quality_unallocated==Decimal("0")
    assert result.reorder_point==Decimal("75")
    assert result.purchase_order_effect=="NONE"
    assert result.operational_purchase_trigger=="NOT_EVALUATED"
