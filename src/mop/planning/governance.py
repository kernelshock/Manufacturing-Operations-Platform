"""G7.6 exception governance contracts, deterministic and NO procurement writes.

Event log is an immutable *in-memory projection contract* for approval workflows.
It is not yet an authoritative persisted audit ledger. Database-backed append-only
workflow and IAM mappings are separate G7.6 production-readiness prerequisites.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from mop.planning.policy_contracts import EvidenceState, PolicyError, RecommendationState
from mop.planning.replenishment import ReplenishmentScenario


class Severity(StrEnum):
    WATCH = "WATCH"
    SHORTAGE = "SHORTAGE"
    PRODUCTION_RISK = "PRODUCTION_RISK"
    STOPPAGE = "STOPPAGE"


class ExceptionStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED_FOR_MANUAL_ACTION = "APPROVED_FOR_MANUAL_ACTION"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class DecisionKind(StrEnum):
    SUBMIT = "SUBMIT"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CLOSE = "CLOSE"


class GovernanceRole(StrEnum):
    PLANNER = "PLANNER"
    PURCHASING = "PURCHASING"
    QUALITY = "QUALITY"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER"
    DIRECTOR = "DIRECTOR"


@dataclass(frozen=True)
class ProductionRiskEvidence:
    """Explicit factual classification; no invented stoppage from an estimated PP."""
    verified: EvidenceState
    known_material_shortage: bool | None
    threatened_published_operation: bool | None
    active_production_stoppage: bool | None
    source_references: tuple[str, ...]

    def __post_init__(self):
        if self.verified == EvidenceState.VERIFIED and (
            self.known_material_shortage is None or
            self.threatened_published_operation is None or
            self.active_production_stoppage is None or
            not self.source_references
        ):
            raise PolicyError("verified production impact requires complete factual evidence")
        if any(not ref.strip() for ref in self.source_references):
            raise PolicyError("production impact provenance cannot be blank")


def classify_severity(evidence: ProductionRiskEvidence) -> Severity | None:
    """UNKNOWN and PARTIAL never silently become low-risk or no-shortage."""
    if evidence.verified != EvidenceState.VERIFIED:
        return None
    if evidence.active_production_stoppage:
        return Severity.STOPPAGE
    if evidence.threatened_published_operation:
        return Severity.PRODUCTION_RISK
    if evidence.known_material_shortage:
        return Severity.SHORTAGE
    return Severity.WATCH


@dataclass(frozen=True)
class SourcingAlternative:
    supplier_code: str
    terms_evidence: EvidenceState
    supplier_qualification: EvidenceState
    capacity_confirmation: EvidenceState
    evidence_keys: tuple[str, ...]

    def __post_init__(self):
        if not self.supplier_code.strip():
            raise PolicyError("alternative must name supplier")
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise PolicyError("duplicated alternative source references")
        if any(not key.strip() for key in self.evidence_keys):
            raise PolicyError("alternative evidence reference cannot be blank")


@dataclass(frozen=True)
class ExceptionCase:
    case_id: UUID
    plant_id: UUID
    article_id: UUID
    uom_id: UUID
    scenario_key: str
    scenario_state: RecommendationState
    severity: Severity
    reason_code: str
    creator_id: UUID
    created_at: datetime
    source_references: tuple[str, ...]
    impact: ProductionRiskEvidence
    alternative: SourcingAlternative | None = None

    def __post_init__(self):
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise PolicyError("case date must have timezone")
        if not self.scenario_key.strip() or not self.reason_code.strip():
            raise PolicyError("case requires scenario and reason")
        if not self.source_references or any(not r.strip() for r in self.source_references):
            raise PolicyError("case requires traceable source references")
        if len(self.source_references) != len(set(self.source_references)):
            raise PolicyError("duplicate source references")


@dataclass(frozen=True)
class GovernanceEvent:
    case_id: UUID
    revision: int
    kind: DecisionKind
    actor_id: UUID
    actor_role: GovernanceRole
    recorded_at: datetime
    reason: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.revision) is not int or self.revision < 1:
            raise PolicyError("event revision must be a positive integer")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise PolicyError("decision timestamp needs timezone")
        if not self.reason.strip():
            raise PolicyError("decision needs a reason")
        if any(not e.strip() for e in self.evidence_refs):
            raise PolicyError("empty decision evidence reference")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise PolicyError("duplicate decision evidence references")


@dataclass(frozen=True)
class GovernanceProjection:
    case: ExceptionCase
    status: ExceptionStatus
    revision: int
    submitter_id: UUID | None
    reviewer_id: UUID | None
    approved_by_id: UUID | None
    last_event_at: datetime | None
    warnings: tuple[str, ...]
    event_log: tuple[GovernanceEvent, ...]
    purchase_order_effect: Literal["NONE"] = "NONE"
    supplier_change_effect: Literal["NONE"] = "NONE"
    physical_inventory_effect: Literal["NONE"] = "NONE"


def open_exception(
    case_id: UUID,
    scenario: ReplenishmentScenario,
    *,
    severity: Severity,
    reason_code: str,
    creator_id: UUID,
    created_at: datetime,
    source_references: tuple[str, ...],
    impact: ProductionRiskEvidence,
    alternative: SourcingAlternative | None = None,
) -> ExceptionCase:
    observed = classify_severity(impact)
    if observed is None:
        raise PolicyError("unverified production impact cannot establish severity")
    if severity != observed:
        raise PolicyError("declared severity conflicts with verified production impact")
    if not set(impact.source_references).issubset(source_references):
        raise PolicyError("production impact references must be included in case provenance")
    if severity in (Severity.PRODUCTION_RISK, Severity.STOPPAGE) and not any(
        ref.startswith(("MES:", "G4:", "PRODUCTION:", "PCP:")) for ref in source_references
    ):
        raise PolicyError("production-critical escalation requires production/plan evidence")
    if alternative and alternative.supplier_code == scenario.supplier_code:
        raise PolicyError("alternative supplier must differ from primary supplier")
    return ExceptionCase(
        case_id=case_id, plant_id=scenario.plant_id, article_id=scenario.article_id,
        uom_id=scenario.uom_id, scenario_key=scenario.scenario_key,
        scenario_state=scenario.state, severity=severity, reason_code=reason_code,
        creator_id=creator_id, created_at=created_at,
        source_references=source_references, impact=impact, alternative=alternative,
    )


def replay_governance(
    case: ExceptionCase, events: tuple[GovernanceEvent, ...],
) -> GovernanceProjection:
    """Strict deterministic replay: no event mutation, no out-of-order approval.

    A governance approval authorizes *manual consideration* only, never an ERP
    order, supplier switch, quality release or inventory issue.
    """
    status = ExceptionStatus.OPEN
    submitter_id = reviewer_id = approved_by_id = last_event_at = None
    warnings = ["GOVERNANCE_APPROVAL_IS_NOT_PURCHASE_ORDER"]
    if case.scenario_state != RecommendationState.READY_FOR_REVIEW:
        warnings.append("SCENARIO_HAS_UNRESOLVED_SOURCE_WARNINGS_OR_BLOCKERS")
    if case.alternative is not None:
        warnings.append("ALTERNATIVE_SUPPLIER_REQUIRES_VERIFIED_TERMS_AND_QUALIFICATION")
    for index, event in enumerate(events, start=1):
        if event.case_id != case.case_id or event.revision != index:
            raise PolicyError("case/revision mismatch or missing append-only event")
        if event.recorded_at < case.created_at:
            raise PolicyError("governance event predates exception")
        if last_event_at is not None and event.recorded_at < last_event_at:
            raise PolicyError("governance event timestamps must be monotonic")
        if event.kind == DecisionKind.SUBMIT:
            if status != ExceptionStatus.OPEN or submitter_id is not None:
                raise PolicyError("case may only be submitted once")
            if event.actor_id != case.creator_id or event.actor_role not in (
                GovernanceRole.PLANNER, GovernanceRole.PURCHASING,
                GovernanceRole.PRODUCTION_MANAGER
            ):
                raise PolicyError("case submitter identity/role is invalid")
            submitter_id = event.actor_id
            status = ExceptionStatus.UNDER_REVIEW
        elif event.kind == DecisionKind.ACKNOWLEDGE:
            if status != ExceptionStatus.UNDER_REVIEW or reviewer_id is not None:
                raise PolicyError("case can only be acknowledged once by an independent reviewer")
            if event.actor_id == submitter_id or event.actor_role not in (
                GovernanceRole.PURCHASING, GovernanceRole.PRODUCTION_MANAGER,
                GovernanceRole.QUALITY, GovernanceRole.DIRECTOR,
            ):
                raise PolicyError("independent operational reviewer required")
            reviewer_id = event.actor_id
        elif event.kind in (DecisionKind.APPROVE, DecisionKind.REJECT):
            if status != ExceptionStatus.UNDER_REVIEW or reviewer_id is None:
                raise PolicyError("independent acknowledgement is required")
            if event.actor_id in (submitter_id, reviewer_id):
                raise PolicyError("maker, reviewer and final decision must be distinct")
            if event.actor_role != GovernanceRole.DIRECTOR:
                raise PolicyError("final decision reserved for Direction")
            if case.severity in (Severity.PRODUCTION_RISK, Severity.STOPPAGE) and (
                not any(ref.startswith(("MES:", "G4:", "PRODUCTION:", "PCP:")) for ref in
                        (*case.source_references, *event.evidence_refs))
            ):
                raise PolicyError("production-risk decision requires operational evidence")
            if event.kind == DecisionKind.APPROVE:
                if case.scenario_state != RecommendationState.READY_FOR_REVIEW:
                    raise PolicyError("blocked/provisional supply scenario cannot be approved")
                if case.alternative is not None:
                    alt = case.alternative
                    if not (alt.terms_evidence == alt.supplier_qualification ==
                            alt.capacity_confirmation == EvidenceState.VERIFIED):
                        raise PolicyError("alternate supplier verification incomplete")
                    if not alt.evidence_keys:
                        raise PolicyError("alternate supplier approvals require provenance")
                if not event.evidence_refs:
                    raise PolicyError("approval requires explicit supporting evidence")
                status = ExceptionStatus.APPROVED_FOR_MANUAL_ACTION
                approved_by_id = event.actor_id
            else:
                status = ExceptionStatus.REJECTED
        elif event.kind == DecisionKind.CLOSE:
            if status not in (ExceptionStatus.REJECTED, ExceptionStatus.APPROVED_FOR_MANUAL_ACTION):
                raise PolicyError("only decided case can be closed")
            if event.actor_role not in (GovernanceRole.DIRECTOR, GovernanceRole.PURCHASING):
                raise PolicyError("closure requires authorized purchasing/Direction role")
            status = ExceptionStatus.CLOSED
        else:
            raise PolicyError("unknown governance event")
        last_event_at = event.recorded_at
    return GovernanceProjection(
        case=case, status=status, revision=len(events),
        submitter_id=submitter_id, reviewer_id=reviewer_id,
        approved_by_id=approved_by_id, last_event_at=last_event_at,
        warnings=tuple(warnings), event_log=events,
    )
