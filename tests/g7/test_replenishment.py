"""G7.5 synthetic acceptance: CR scenarios never write purchases or stock."""
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.planning.policy_contracts import (
    ConsumptionBasis, EvidenceState, PlanningFacts, PlanningPolicy,
    PolicyError, RecommendationState, ReplenishmentMethod,
)
from mop.planning.reorder_point import DemandRate, project_reorder_point
from mop.planning.replenishment import (
    IncomingPosition, SupplierTerms, ReplenishmentScenario, calculate_replenishment, compare_scenarios,
)

PLANT, OTHER, ARTICLE, UOM = (uuid4() for _ in range(4))


def policy(**overrides):
    values = dict(plant_id=PLANT, calendar_code="FAIC-BUSINESS",
                  replenishment_method=ReplenishmentMethod.CALCULATED,
                  horizon_business_days=15)
    values.update(overrides)
    return PlanningPolicy(**values)


def facts(**overrides):
    values=dict(plant_id=PLANT, article_id=ARTICLE, uom_id=UOM,
                physical_on_hand=Decimal("100"), quality_usable=Decimal("90"),
                active_holds=Decimal("20"), source_coverage=EvidenceState.VERIFIED,
                supplier_lead_time=EvidenceState.VERIFIED, business_calendar_verified=True)
    values.update(overrides)
    return PlanningFacts(**values)


def point(p=None, f=None):
    p=p or policy()
    f=f or facts()
    return project_reorder_point(p, f, (DemandRate(
        plant_id=PLANT, article_id=ARTICLE, uom_id=UOM,
        basis=ConsumptionBasis.PER_PRODUCT, source_key="HISTORY-FAIC",
        daily_quantity=Decimal("4"), evidence_state=EvidenceState.VERIFIED,
    ),), Decimal("15"))


def terms(**overrides):
    values=dict(supplier_code="SUP-ONE", article_id=ARTICLE, uom_id=UOM,
                minimum_quantity=Decimal("10"), pack_multiple=Decimal("5"),
                verified=EvidenceState.VERIFIED, evidence_reference="SUP-TERMS-VERIFIED-1")
    values.update(overrides)
    return SupplierTerms(**values)


def inbound(**overrides):
    values=dict(plant_id=PLANT, article_id=ARTICLE, uom_id=UOM,
                quantity=Decimal("0"), state=EvidenceState.VERIFIED,
                evidence_reference="NO-CONFIRMED-INBOUND-CHECKED")
    values.update(overrides)
    return IncomingPosition(**values)


def scenario(p=None,f=None,t=None,i=None,**kw):
    p=p or policy()
    f=f or facts()
    return calculate_replenishment("SYNTHETIC-SCENARIO",p,point(p,f),
                                   terms() if t is None else t,
                                   inbound() if i is None else i,**kw)


def test_calculated_cr_uses_quality_not_physical_and_no_double_hold():
    # Target 4*15+15=75; Quality usable 90 - held 20 = 70 => deficit 5.
    r=scenario()
    assert r.target_stock==Decimal("75")
    assert r.quality_unallocated==Decimal("70")
    assert r.deficit==Decimal("5")
    assert r.raw_quantity==Decimal("5")
    assert r.suggested_quantity==Decimal("10")  # verified supplier MOQ
    assert r.state==RecommendationState.PROVISIONAL
    assert "QUANTITY_ROUNDED_TO_VERIFIED_SUPPLIER_TERMS" in r.warnings
    assert r.approval=="HUMAN_REVIEW_REQUIRED"
    assert r.purchase_order_effect=="NONE" and r.inventory_effect=="NONE"


def test_no_deficit_never_forces_moq_order():
    r=scenario(f=facts(physical_on_hand=Decimal("150"),quality_usable=Decimal("150")))
    assert r.deficit==0
    assert r.suggested_quantity==0
    assert r.state==RecommendationState.READY_FOR_REVIEW


def test_pack_multiple_rounds_up_only_calculated_quantity():
    r=scenario(f=facts(physical_on_hand=Decimal("90"),quality_usable=Decimal("76")),
               t=terms(minimum_quantity=Decimal("5"),pack_multiple=Decimal("4")))
    # usable=56; target=75; gap 19, pack multiple 4 -> 20.
    assert r.deficit==Decimal("19")
    assert r.suggested_quantity==Decimal("20")


def test_confirmed_incoming_only_when_plant_specific_and_verified():
    r=scenario(i=inbound(quantity=Decimal("3")))
    assert r.deficit==Decimal("2")
    assert r.suggested_quantity==Decimal("10")
    no_evidence=scenario(i=inbound(state=EvidenceState.UNKNOWN,quantity=None,
                                  evidence_reference=None))
    assert no_evidence.state==RecommendationState.BLOCKED
    assert "PLANT_INCOMING_NOT_CONFIRMED" in no_evidence.blockers
    assert no_evidence.suggested_quantity is None
    manual=scenario(i=inbound(state=EvidenceState.PARTIAL,quantity=Decimal("99"),
                              evidence_reference="PROLOWIN-MANUAL-UNASSIGNED"))
    assert manual.suggested_quantity is None
    assert manual.confirmed_incoming is None


def test_fixed_cr_is_preserved_when_verified_terms_match():
    p=policy(replenishment_method=ReplenishmentMethod.FIXED,
             fixed_replenishment_quantity=Decimal("30"))
    r=scenario(p=p)
    assert r.method==ReplenishmentMethod.FIXED
    assert r.raw_quantity==Decimal("30")
    assert r.suggested_quantity==Decimal("30")
    assert r.state==RecommendationState.READY_FOR_REVIEW


@pytest.mark.parametrize("qty",["8","9","12"])
def test_fixed_cr_fails_closed_not_silently_rounded(qty):
    p=policy(replenishment_method=ReplenishmentMethod.FIXED,
             fixed_replenishment_quantity=Decimal(qty))
    r=scenario(p=p)
    assert r.state==RecommendationState.BLOCKED
    assert "FIXED_CR_CONFLICTS_WITH_VERIFIED_SUPPLIER_TERMS" in r.blockers
    assert r.suggested_quantity is None


def test_fixed_can_raise_warning_with_no_deficit():
    p=policy(replenishment_method=ReplenishmentMethod.FIXED,
             fixed_replenishment_quantity=Decimal("30"))
    r=scenario(p=p,f=facts(physical_on_hand=Decimal("150"),quality_usable=Decimal("150")))
    assert r.suggested_quantity==Decimal("30")
    assert r.state==RecommendationState.PROVISIONAL
    assert "FIXED_QUANTITY_DESPITE_NO_CALCULATED_DEFICIT" in r.warnings


def test_unknown_quality_blocks_even_if_physical_is_known():
    r=scenario(f=facts(quality_usable=None))
    assert r.state==RecommendationState.BLOCKED
    assert r.suggested_quantity is None
    assert "QUALITY_USABLE_UNKNOWN" in r.blockers


def test_partial_prolowin_history_is_not_authoritative_terms():
    r=scenario(t=terms(verified=EvidenceState.PARTIAL))
    assert "SUPPLIER_TERMS_NOT_VERIFIED" in r.blockers
    assert r.suggested_quantity is None


def test_missing_supplier_terms_is_blocked():
    p=policy()
    result=calculate_replenishment("UNKNOWN-TERMS",p,point(p),None,inbound())
    assert result.state==RecommendationState.BLOCKED
    assert "SUPPLIER_TERMS_MISSING" in result.blockers


def test_unready_point_never_issues_quantity():
    p=policy()
    blocked=point(p,facts(quality_usable=None))
    r=calculate_replenishment("BLOCKED",p,blocked,terms(),inbound())
    assert r.suggested_quantity is None
    assert "REORDER_POINT_NOT_READY" in r.blockers


def test_explicit_coverage_horizon_controls_target():
    r=scenario(coverage_business_days=20)
    assert r.expected_coverage_demand==Decimal("80")
    assert r.target_stock==Decimal("95")
    assert r.deficit==Decimal("25")
    assert r.suggested_quantity==Decimal("25")


@pytest.mark.parametrize("bad", [0,-1,1.0,True])
def test_bad_horizon_rejected(bad):
    with pytest.raises(PolicyError):
        scenario(coverage_business_days=bad)


@pytest.mark.parametrize("bad", [
    {"plant_id":OTHER},
    {"article_id":uuid4()},
    {"uom_id":uuid4()},
])
def test_incoming_must_match_selected_plant_article_and_uom(bad):
    with pytest.raises(PolicyError):
        scenario(i=inbound(**bad))


@pytest.mark.parametrize("bad", [
    {"article_id":uuid4()},
    {"uom_id":uuid4()},
])
def test_terms_must_match_article_and_canonical_unit(bad):
    with pytest.raises(PolicyError):
        scenario(t=terms(**bad))


@pytest.mark.parametrize("bad", [
    {"minimum_quantity":Decimal("NaN")},
    {"pack_multiple":Decimal("0")},
    {"pack_multiple":Decimal("-1")},
    {"pack_multiple":2.5},
])
def test_unverified_numeric_format_is_rejected(bad):
    with pytest.raises(PolicyError):
        terms(**bad)


def test_zero_confirmed_incoming_requires_provenance():
    with pytest.raises(PolicyError):
        inbound(evidence_reference=None)
    with pytest.raises(PolicyError):
        inbound(quantity=None)


def test_scenario_comparison_has_no_auto_ranking():
    p=policy()
    rp=point(p)
    a=calculate_replenishment("A",p,rp,terms(),inbound())
    b=calculate_replenishment("B",p,rp,
               terms(supplier_code="SUP-TWO",minimum_quantity=Decimal("25")),
               inbound())
    options=compare_scenarios((b,a))
    assert [x.scenario_key for x in options]==["A","B"]
    assert options[0].supplier_code=="SUP-ONE"
    assert options[1].supplier_code=="SUP-TWO"
    assert all(x.purchase_order_effect=="NONE" for x in options)
    with pytest.raises(PolicyError,match="duplicate"):
        compare_scenarios((a,a))


def test_reject_mixed_plant_scenario_comparison():
    a=scenario()
    b=ReplenishmentScenario(
        **{**a.__dict__, "scenario_key":"OTHER", "plant_id":OTHER})
    with pytest.raises(PolicyError):
        compare_scenarios((a,b))
