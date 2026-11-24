"""G7.6 synthetic governance cases — maker/checker and no ERP side effects."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from mop.planning.governance import (
    DecisionKind, ExceptionStatus, GovernanceEvent, GovernanceRole, Severity,
    SourcingAlternative, ProductionRiskEvidence, classify_severity,
    open_exception, replay_governance,
)
from mop.planning.policy_contracts import (
    ConsumptionBasis, EvidenceState, PlanningFacts, PlanningPolicy, PolicyError,
    RecommendationState,
)
from mop.planning.reorder_point import DemandRate, project_reorder_point
from mop.planning.replenishment import (
    IncomingPosition, SupplierTerms, calculate_replenishment,
)


PLANT, ARTICLE, UOM, MAKER, REVIEWER, DIRECTOR, OTHER = (uuid4() for _ in range(7))
T = datetime(2026,11,6,12,tzinfo=timezone.utc)


def scenario(*, partial=False):
    policy=PlanningPolicy(plant_id=PLANT,calendar_code="FAIC-SYNTHETIC")
    facts=PlanningFacts(
        plant_id=PLANT,article_id=ARTICLE,uom_id=UOM,
        physical_on_hand=Decimal("100"),active_holds=Decimal("20"),
        quality_usable=Decimal("85"),
        source_coverage=EvidenceState.PARTIAL if partial else EvidenceState.VERIFIED,
        supplier_lead_time=EvidenceState.VERIFIED,business_calendar_verified=True,
    )
    point=project_reorder_point(policy,facts,(DemandRate(
        plant_id=PLANT,article_id=ARTICLE,uom_id=UOM,
        basis=ConsumptionBasis.PER_PRODUCT,source_key="DEMAND-REVIEWED",
        daily_quantity=Decimal("4"),evidence_state=EvidenceState.VERIFIED,
    ),),Decimal("15"))
    return calculate_replenishment(
        "CR-CANDIDATE-1",policy,point,
        SupplierTerms(supplier_code="PRIMARY",article_id=ARTICLE,uom_id=UOM,
            minimum_quantity=Decimal("10"),pack_multiple=Decimal("5"),
            verified=EvidenceState.VERIFIED,evidence_reference="SUPPLIER-MOQ-1"),
        IncomingPosition(plant_id=PLANT,article_id=ARTICLE,uom_id=UOM,
            quantity=Decimal("0"),state=EvidenceState.VERIFIED,
            evidence_reference="INBOUND-CONFIRMED-ZERO"),
    )


def alternative(**overrides):
    values=dict(supplier_code="BACKUP",terms_evidence=EvidenceState.VERIFIED,
                supplier_qualification=EvidenceState.VERIFIED,
                capacity_confirmation=EvidenceState.VERIFIED,
                evidence_keys=("SUPPLIER-ALT-TERMS", "QUALITY-ALT-QUAL", "CAPACITY-ALT"))
    values.update(overrides)
    return SourcingAlternative(**values)


def case(*, partial=False,severity=Severity.SHORTAGE, alt=None, references=("G6:LEDGER", "PCP:TQ-2026-1")):
    impact=ProductionRiskEvidence(
        verified=EvidenceState.VERIFIED,
        known_material_shortage=severity != Severity.WATCH,
        threatened_published_operation=severity in (Severity.PRODUCTION_RISK,Severity.STOPPAGE),
        active_production_stoppage=severity == Severity.STOPPAGE,
        source_references=(references[0],),
    )
    return open_exception(
        uuid4(),scenario(partial=partial),severity=severity,
        reason_code="SHORTAGE_OR_DELAY",creator_id=MAKER,
        created_at=T,source_references=references,impact=impact,alternative=alt,
    )


def event(c, revision, kind, actor, role, **overrides):
    values=dict(case_id=c.case_id,revision=revision,kind=kind,
                actor_id=actor,actor_role=role,
                recorded_at=T+timedelta(minutes=revision),
                reason="Synthetic governance reason",
                evidence_refs=("PCP:TQ-2026-1",) if kind==DecisionKind.APPROVE else ())
    values.update(overrides)
    return GovernanceEvent(**values)


def submitted(c):
    return event(c,1,DecisionKind.SUBMIT,MAKER,GovernanceRole.PLANNER)


def acknowledged(c):
    return event(c,2,DecisionKind.ACKNOWLEDGE,REVIEWER,GovernanceRole.PRODUCTION_MANAGER)


def approved(c):
    return event(c,3,DecisionKind.APPROVE,DIRECTOR,GovernanceRole.DIRECTOR)


def test_open_submitted_and_independent_approval_for_manual_action_only():
    c=case(severity=Severity.PRODUCTION_RISK)
    first=submitted(c)
    second=acknowledged(c)
    third=approved(c)
    log=(first,second,third)
    p=replay_governance(c,log)
    assert p.status==ExceptionStatus.APPROVED_FOR_MANUAL_ACTION
    assert p.revision==3 and p.event_log==log
    assert p.approved_by_id==DIRECTOR
    assert p.purchase_order_effect=="NONE"
    assert p.supplier_change_effect=="NONE"
    assert p.physical_inventory_effect=="NONE"
    assert p.case.scenario_key=="CR-CANDIDATE-1"
    assert p.case.plant_id==PLANT


def test_reject_and_close_keep_full_event_history():
    c=case()
    events=(submitted(c),acknowledged(c),
            event(c,3,DecisionKind.REJECT,DIRECTOR,GovernanceRole.DIRECTOR),
            event(c,4,DecisionKind.CLOSE,REVIEWER,GovernanceRole.PURCHASING))
    p=replay_governance(c,events)
    assert p.status==ExceptionStatus.CLOSED
    assert p.approved_by_id is None and p.revision==4
    assert [e.kind for e in p.event_log]==[
        DecisionKind.SUBMIT,DecisionKind.ACKNOWLEDGE,DecisionKind.REJECT,DecisionKind.CLOSE]


def test_approved_manual_action_may_be_closed_but_not_reapproved():
    c=case()
    events=(submitted(c),acknowledged(c),approved(c),
            event(c,4,DecisionKind.CLOSE,REVIEWER,GovernanceRole.PURCHASING))
    assert replay_governance(c,events).status==ExceptionStatus.CLOSED
    with pytest.raises(PolicyError):
        replay_governance(c,events+(event(c,5,DecisionKind.APPROVE,DIRECTOR,GovernanceRole.DIRECTOR),))


def test_blocked_or_provisional_material_scenario_cannot_be_approved():
    c=case(partial=True)
    assert c.scenario_state==RecommendationState.PROVISIONAL
    p=replay_governance(c,(submitted(c),acknowledged(c)))
    assert "SCENARIO_HAS_UNRESOLVED_SOURCE_WARNINGS_OR_BLOCKERS" in p.warnings
    with pytest.raises(PolicyError,match="blocked/provisional"):
        replay_governance(c,(submitted(c),acknowledged(c),approved(c)))
    assert replay_governance(c,(submitted(c),acknowledged(c),
        event(c,3,DecisionKind.REJECT,DIRECTOR,GovernanceRole.DIRECTOR))).status==ExceptionStatus.REJECTED


def test_alternate_supplier_requires_verified_terms_quality_and_capacity():
    c=case(alt=alternative())
    assert replay_governance(c,(submitted(c),acknowledged(c),approved(c))).status==ExceptionStatus.APPROVED_FOR_MANUAL_ACTION
    for bad in (
        {"terms_evidence":EvidenceState.PARTIAL},
        {"supplier_qualification":EvidenceState.UNKNOWN},
        {"capacity_confirmation":EvidenceState.PARTIAL},
        {"evidence_keys":()},
    ):
        c=case(alt=alternative(**bad))
        with pytest.raises(PolicyError,match="alternate supplier"):
            replay_governance(c,(submitted(c),acknowledged(c),approved(c)))


def test_production_critical_requires_real_plan_or_execution_reference():
    for severity in (Severity.PRODUCTION_RISK,Severity.STOPPAGE):
        with pytest.raises(PolicyError,match="production/plan evidence"):
            case(severity=severity,references=("PROLOWIN:UNVERIFIED",))
    c=case(severity=Severity.STOPPAGE)
    assert c.source_references[1].startswith("PCP:")


@pytest.mark.parametrize("actor,role",[
    (OTHER,GovernanceRole.PLANNER),
    (MAKER,GovernanceRole.DIRECTOR),
    (MAKER,GovernanceRole.QUALITY),
])
def test_only_identified_creator_can_submit(actor,role):
    c=case()
    with pytest.raises(PolicyError):
        replay_governance(c,(event(c,1,DecisionKind.SUBMIT,actor,role),))


@pytest.mark.parametrize("actor,role",[
    (MAKER,GovernanceRole.PRODUCTION_MANAGER),
    (REVIEWER,GovernanceRole.PLANNER),
])
def test_independent_qualified_reviewer_required(actor,role):
    c=case()
    with pytest.raises(PolicyError):
        replay_governance(c,(submitted(c),event(c,2,DecisionKind.ACKNOWLEDGE,actor,role)))


@pytest.mark.parametrize("actor,role",[
    (MAKER,GovernanceRole.DIRECTOR),
    (REVIEWER,GovernanceRole.DIRECTOR),
    (OTHER,GovernanceRole.PLANNER),
])
def test_distinct_director_decides(actor,role):
    c=case()
    with pytest.raises(PolicyError):
        replay_governance(c,(submitted(c),acknowledged(c),
            event(c,3,DecisionKind.APPROVE,actor,role)))


def test_approval_requires_decision_evidence():
    c=case()
    with pytest.raises(PolicyError,match="supporting evidence"):
        replay_governance(c,(submitted(c),acknowledged(c),
            event(c,3,DecisionKind.APPROVE,DIRECTOR,GovernanceRole.DIRECTOR,evidence_refs=())))


def test_approval_without_acknowledgement_is_rejected():
    c=case()
    with pytest.raises(PolicyError,match="acknowledgement"):
        replay_governance(c,(submitted(c),
            event(c,2,DecisionKind.APPROVE,DIRECTOR,GovernanceRole.DIRECTOR)))


@pytest.mark.parametrize("bad",[
    {"revision":2},
    {"case_id":uuid4()},
    {"recorded_at":T-timedelta(days=1)},
])
def test_append_only_revision_identity_and_time_are_enforced(bad):
    c=case()
    with pytest.raises(PolicyError):
        replay_governance(c,(replace(event(c,1,DecisionKind.SUBMIT,MAKER,GovernanceRole.PLANNER),**bad),))


def test_repeated_submit_and_close_before_decision_fail():
    c=case()
    with pytest.raises(PolicyError):
        replay_governance(c,(submitted(c),
            event(c,2,DecisionKind.SUBMIT,MAKER,GovernanceRole.PLANNER)))
    with pytest.raises(PolicyError):
        replay_governance(c,(submitted(c),
            event(c,2,DecisionKind.CLOSE,REVIEWER,GovernanceRole.PURCHASING)))


def test_alternative_must_not_be_primary_supplier_and_sources_are_unique():
    with pytest.raises(PolicyError,match="differ"):
        case(alt=alternative(supplier_code="PRIMARY"))
    with pytest.raises(PolicyError,match="duplicated"):
        alternative(evidence_keys=("SAME","SAME"))


def test_invalid_events_are_rejected_before_replay():
    c=case()
    with pytest.raises(PolicyError,match="reason"):
        event(c,1,DecisionKind.SUBMIT,MAKER,GovernanceRole.PLANNER,reason=" ")
    with pytest.raises(PolicyError,match="timezone"):
        event(c,1,DecisionKind.SUBMIT,MAKER,GovernanceRole.PLANNER,recorded_at=datetime(2026,11,6))
    with pytest.raises(PolicyError,match="positive"):
        event(c,0,DecisionKind.SUBMIT,MAKER,GovernanceRole.PLANNER)


def test_event_tuple_does_not_modify_original_case_or_supplier_state():
    c=case(alt=alternative())
    before=c
    p=replay_governance(c,(submitted(c),acknowledged(c),approved(c)))
    assert c==before
    assert p.case.alternative.supplier_code=="BACKUP"
    assert p.supplier_change_effect=="NONE"
    assert p.purchase_order_effect=="NONE"


@pytest.mark.parametrize("shortage,risk,stoppage,expected",[
    (False, False, False, Severity.WATCH),
    (True, False, False, Severity.SHORTAGE),
    (True, True, False, Severity.PRODUCTION_RISK),
    (True, True, True, Severity.STOPPAGE),
])
def test_risk_severity_uses_verified_production_facts(shortage,risk,stoppage,expected):
    evidence=ProductionRiskEvidence(
        verified=EvidenceState.VERIFIED,known_material_shortage=shortage,
        threatened_published_operation=risk,active_production_stoppage=stoppage,
        source_references=("PCP:PLAN-1",),
    )
    assert classify_severity(evidence)==expected


@pytest.mark.parametrize("state",[EvidenceState.PARTIAL,EvidenceState.UNKNOWN])
def test_missing_impact_evidence_never_becomes_low_severity(state):
    evidence=ProductionRiskEvidence(
        verified=state,known_material_shortage=None,
        threatened_published_operation=None,active_production_stoppage=None,
        source_references=(),
    )
    assert classify_severity(evidence) is None


def test_false_verified_impact_cannot_omit_required_facts():
    with pytest.raises(PolicyError,match="complete factual"):
        ProductionRiskEvidence(
            verified=EvidenceState.VERIFIED,known_material_shortage=False,
            threatened_published_operation=None,active_production_stoppage=False,
            source_references=("PCP:PLAN-1",),
        )

def test_exception_severity_cannot_be_spoofed_from_impact_evidence():
    impact=ProductionRiskEvidence(
        verified=EvidenceState.VERIFIED,known_material_shortage=True,
        threatened_published_operation=False,active_production_stoppage=False,
        source_references=("PCP:PLAN-1",),
    )
    with pytest.raises(PolicyError,match="severity conflicts"):
        open_exception(uuid4(),scenario(),severity=Severity.STOPPAGE,
            reason_code="FALSE-STOPPAGE",creator_id=MAKER,created_at=T,
            source_references=("PCP:PLAN-1",),impact=impact)


def test_exception_requires_verified_impact_not_partial_evidence():
    impact=ProductionRiskEvidence(
        verified=EvidenceState.PARTIAL,known_material_shortage=True,
        threatened_published_operation=None,active_production_stoppage=None,
        source_references=("PCP:PLAN-1",),
    )
    with pytest.raises(PolicyError,match="unverified production impact"):
        open_exception(uuid4(),scenario(),severity=Severity.SHORTAGE,
            reason_code="INCOMPLETE",creator_id=MAKER,created_at=T,
            source_references=("PCP:PLAN-1",),impact=impact)

def test_independent_acknowledgement_cannot_be_replaced_before_director_decision():
    c=case()
    with pytest.raises(PolicyError,match="only be acknowledged once"):
        replay_governance(c,(submitted(c),acknowledged(c),
            event(c,3,DecisionKind.ACKNOWLEDGE,OTHER,GovernanceRole.QUALITY)))
