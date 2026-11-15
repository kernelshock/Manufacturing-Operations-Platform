"""PostgreSQL tests of transaction ownership, retries and independent decisions."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from mop.application import create_app
from mop.audit.models import AuditEntry
from mop.iam.models import User
from mop.iam.schemas import UserCreate
from mop.iam.service import IdentityService
from mop.planning.governance import (
    DecisionKind, ExceptionCase, ExceptionStatus, GovernanceRole, ProductionRiskEvidence, Severity,
)
from mop.planning.governance_service import GovernanceConflict, GovernanceService
from mop.planning.policy_contracts import EvidenceState, PolicyError, RecommendationState

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ, reason="requires disposable PostgreSQL"
)


@pytest.fixture
def governance_case():
    path = Path(__file__).resolve().parents[1] / "g6" / "test_reservations_integration.py"
    spec = importlib.util.spec_from_file_location("g76_reservation_fixtures", path)
    assert spec and spec.loader
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    settings, db, suffix, username, plant_id, maker_id = fixtures.setup()
    try:
        with TestClient(create_app(settings, database=db)) as client:
            fixtures.auth(client, username)
            data, _, uom, _ = fixtures.prepared(client, db, suffix, plant_id, initial=None)
        with db.session() as session:
            identity = IdentityService(session)
            reviewer, director, other = (
                identity.create_user(UserCreate(
                    username=f"g76-{role}-{suffix.lower()}", display_name=role,
                    password=fixtures.PASSWORD,
                )).id
                for role in ("reviewer", "director", "other")
            )
        references = ("PCP:G76-SYNTHETIC",)
        case = ExceptionCase(
            case_id=uuid4(), plant_id=plant_id, article_id=UUID(data["material_x"]), uom_id=UUID(uom),
            scenario_key=f"G76-{suffix}", scenario_state=RecommendationState.READY_FOR_REVIEW,
            severity=Severity.SHORTAGE, reason_code="SHORTAGE",
            creator_id=maker_id, created_at=datetime.now(timezone.utc),
            source_references=references,
            impact=ProductionRiskEvidence(EvidenceState.VERIFIED, True, False, False, references),
        )
        yield db, case, reviewer, director, other
    finally:
        db.dispose()


def submit(session, case, **context):
    return GovernanceService(session).submit(
        case, actor=session.get(User, case.creator_id), role=GovernanceRole.PLANNER,
        reason="Report shortage", idempotency_key="submit", **context,
    )


def test_case_and_audit_are_atomic_and_retry_returns_original_revision(governance_case):
    db, case, reviewer, _, _ = governance_case
    with db.session() as session:
        # Deliberately exceed the audit column size to exercise savepoint rollback.
        with pytest.raises(DBAPIError):
            submit(session, case, request_id="x" * 65)
        session.commit()
        assert submit(session, case).revision == 1
        session.commit()

    with db.session() as session:
        service = GovernanceService(session)
        assert service.get(case.case_id).case == case
        assert service.transition(
            case.case_id, DecisionKind.ACKNOWLEDGE, actor=session.get(User, reviewer),
            role=GovernanceRole.QUALITY, reason="Checked facts", expected_revision=1,
            idempotency_key="review",
        ).revision == 2
        session.commit()
        assert submit(session, case).revision == 1
        assert service.get(case.case_id).revision == 2
        assert session.scalar(select(func.count()).select_from(AuditEntry).where(
            AuditEntry.object_id == str(case.case_id),
        )) == 2


def test_concurrent_direction_decisions_append_only_once(governance_case):
    db, case, reviewer, director, other = governance_case
    with db.session() as session:
        submit(session, case)
        service = GovernanceService(session)
        review = dict(role=GovernanceRole.QUALITY, reason="Checked facts",
                      expected_revision=1, idempotency_key="review")
        with pytest.raises(PolicyError, match="independent operational reviewer"):
            service.transition(case.case_id, DecisionKind.ACKNOWLEDGE,
                               actor=session.get(User, case.creator_id), **review)
        service.transition(case.case_id, DecisionKind.ACKNOWLEDGE,
                           actor=session.get(User, reviewer), **review)
        session.commit()

    def decide(actor_id):
        with db.session() as session:
            try:
                result = GovernanceService(session).transition(
                    case.case_id, DecisionKind.APPROVE, actor=session.get(User, actor_id),
                    role=GovernanceRole.DIRECTOR, reason="Verified shortage",
                    expected_revision=2, idempotency_key="decision",
                    evidence_refs=case.source_references,
                )
            except GovernanceConflict:
                return "conflict"
            session.commit()
            return result.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert set(executor.map(decide, (director, other))) == {
            ExceptionStatus.APPROVED_FOR_MANUAL_ACTION, "conflict"
        }
    with db.session() as session:
        assert GovernanceService(session).get(case.case_id).revision == 3
        assert session.scalar(select(func.count()).select_from(AuditEntry).where(
            AuditEntry.object_id == str(case.case_id),
        )) == 3
