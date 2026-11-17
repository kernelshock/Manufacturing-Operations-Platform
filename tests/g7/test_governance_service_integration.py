"""PostgreSQL tests of transaction ownership, retries and independent decisions."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from mop.application import create_app
from mop.audit.models import AuditEntry
from mop.core.models import Plant
from mop.iam.models import User
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.materials.models import MaterialMovement
from mop.config import Settings
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
            data, _, uom, _ = fixtures.prepared(client, db, suffix, plant_id, initial="20")
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


def test_governance_http_enforces_plant_scope_and_resolves_ledger_evidence(governance_case):
    db, case, reviewer, director, outsider = governance_case
    password = "G65-Tests-Only-Do-Not-Reuse-2026!"
    settings = Settings(environment="test", _env_file=None)
    root = "/api/v1/planning/governance/cases"
    case_url = f"{root}/{case.case_id}"

    with db.session() as session:
        submit(session, case)
        session.commit()
        iam = IdentityService(session)
        same_organization = session.get(Plant, case.plant_id).organization_id
        other_plant = Plant(
            organization_id=same_organization, code=f"G76-{uuid4().hex[:12]}",
            name="G76 unrelated plant",
        )
        session.add(other_plant)
        session.commit()
        role_suffix = uuid4().hex[:10]
        roles = (
            (reviewer, case.plant_id, "quality"),
            (director, case.plant_id, "direction"),
            (outsider, other_plant.id, "quality"),
        )
        usernames = {}
        for user_id, plant_id, capability in roles:
            role = iam.create_role(RoleCreate(
                code=f"G76-{capability}-{user_id.hex[:8]}-{role_suffix}",
                name="G76 scoped governance",
            ))
            iam.grant_permission(role.id, "planning.governance.read")
            iam.grant_permission(role.id, f"planning.governance.{capability}")
            iam.assign_role(user_id, RoleAssignmentCreate(
                role_id=role.id, scope_type="plant", scope_id=plant_id,
            ))
            usernames[user_id] = session.get(User, user_id).username
        movement_id = session.scalar(select(MaterialMovement.id).where(
            MaterialMovement.article_id == case.article_id,
        ))
        assert movement_id is not None

    with TestClient(create_app(settings, database=db)) as client:
        def login(user_id):
            assert client.post("/api/v1/auth/login", json={
                "username": usernames[user_id], "password": password,
            }).status_code == 200

        assert client.get(case_url).status_code == 401
        login(outsider)
        assert client.get(case_url).status_code == 404
        assert client.get(root, params={"plant_id": str(case.plant_id)}).status_code == 403
        login(reviewer)
        assert client.get(root, params={"plant_id": str(case.plant_id)}).json() == [str(case.case_id)]
        detail = client.get(case_url)
        assert detail.status_code == 200
        assert detail.headers["Cache-Control"] == "no-store"
        transition = f"{case_url}/transitions"
        command = {
            "action": "ACKNOWLEDGE", "reason": "Checked ledger", "expected_revision": 1,
            "idempotency_key": "http-review", "movement_ids": [str(uuid4())],
        }
        assert client.post(transition, json=command).status_code == 422
        command["movement_ids"] = [str(movement_id)]
        assert client.post(transition, json={**command, "actor_role": "DIRECTOR"}).status_code == 422
        reviewed = client.post(transition, json=command)
        assert reviewed.status_code == 200, reviewed.text
        event = reviewed.json()["event_log"][-1]
        assert event["actor_role"] == "QUALITY"
        assert event["evidence_refs"] == [f"G6:MOVEMENT:{movement_id}"]
        assert client.post(transition, json=command).json()["revision"] == 2
        rejected = {
            "action": "REJECT", "reason": "Do not proceed", "expected_revision": 2,
            "idempotency_key": "http-reject",
        }
        assert client.post(transition, json=rejected).status_code == 403
        login(director)
        assert client.post(transition, json={**rejected, "action": "APPROVE"}).status_code == 422
        response = client.post(transition, json=rejected)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REJECTED"
        closed = client.post(transition, json={
            "action": "CLOSE", "reason": "Review complete", "expected_revision": 3,
            "idempotency_key": "http-close",
        })
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "CLOSED"


def test_submit_stoppage_requires_source_and_replays_after_source_changes(governance_case, monkeypatch):
    from types import SimpleNamespace
    from mop.api.v1 import planning_governance

    db, case, _, _, _ = governance_case
    settings = Settings(environment="test", _env_file=None)
    root = "/api/v1/planning/governance/cases"
    with db.session() as session:
        iam = IdentityService(session)
        role = iam.create_role(RoleCreate(code=f"G76-OPEN-{uuid4().hex}", name="Scoped intake"))
        iam.grant_permission(role.id, "planning.governance.read")
        iam.assign_role(case.creator_id, RoleAssignmentCreate(
            role_id=role.id, scope_type="plant", scope_id=case.plant_id,
        ))
        username = session.get(User, case.creator_id).username
        role_id = role.id

    command = {
        "plant_id": str(case.plant_id), "article_id": str(case.article_id),
        "location_id": str(uuid4()), "interruption_id": str(uuid4()),
        "idempotency_key": "stoppage-intake",
    }
    with TestClient(create_app(settings, database=db)) as client:
        assert client.post(root, json=command).status_code == 401
        assert client.post("/api/v1/auth/login", json={
            "username": username, "password": "G65-Tests-Only-Do-Not-Reuse-2026!",
        }).status_code == 200
        assert client.post(root, json=command).status_code == 403
        with db.session() as session:
            IdentityService(session).grant_permission(role_id, "planning.governance.planner")

        missing = client.post(root, json=command)
        assert missing.status_code == 422
        assert "no active MES interruption" in missing.json()["detail"]

        original_resolver = planning_governance.resolve_material_stoppage
        monkeypatch.setattr(
            planning_governance, "resolve_material_stoppage",
            lambda *args, **kwargs: SimpleNamespace(taquilla_id=uuid4(), uom_id=case.uom_id),
        )
        opened = client.post(root, json=command)
        assert opened.status_code == 201, opened.text
        body = opened.json()
        assert body["case"]["severity"] == "STOPPAGE"
        assert body["case"]["scenario_state"] == "BLOCKED"
        assert body["status"] == "UNDER_REVIEW"
        assert body["revision"] == 1

        monkeypatch.setattr(planning_governance, "resolve_material_stoppage", original_resolver)
        repeated = client.post(root, json=command)
        assert repeated.status_code == 201, repeated.text
        assert repeated.json() == body
        assert client.post(root, json={**command, "location_id": str(uuid4())}).status_code == 409


def test_open_stoppage_from_persisted_mes_and_g6():
    from mop.aps.service import APSService
    from mop.mes.schemas import ExecutionDispatchCreate, ExecutionStartCreate, InterruptionStartCreate
    from mop.mes.service import MESService

    tests = Path(__file__).resolve().parents[1]

    def load_fixture(group, name):
        spec = importlib.util.spec_from_file_location(f"g76_{name}", tests / group / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    dispatch_fixture = load_fixture("g5", "test_dispatch_integration")
    reservations = load_fixture("g6", "test_reservations_integration")
    materials = reservations.fixture_module()
    settings, db, suffix, username, _, actor_id = reservations.setup()
    try:
        with db.session() as session:
            (_, _, _, _, _, _, _, run, start_at, _, plant,
             article_revision) = dispatch_fixture.seed_dispatch_schedule(session, suffix)
            plant_id, revision_id = plant.id, article_revision.id
            publication, _, _ = APSService(session).publish_schedule(run.id, "G7.6 test schedule", actor_id)
            mes = MESService(session)
            dispatch, _, _ = mes.create_dispatch(ExecutionDispatchCreate(
                publication_id=publication.id, dispatch_code=f"G76-{suffix}",
            ), actor_id)
            mes.release_dispatch(dispatch.id)
            operation = list(mes.list_operations(dispatch.id))[0]
            operation_id = operation.id
            mes.start_operation(operation_id, ExecutionStartCreate(occurred_at=start_at), actor_id)

            identity = IdentityService(session)
            role = identity.create_role(RoleCreate(code=f"G76-REAL-{suffix}", name="Scoped planning"))
            identity.grant_permission(role.id, "planning.governance.read")
            identity.grant_permission(role.id, "planning.governance.planner")
            identity.assign_role(actor_id, RoleAssignmentCreate(
                role_id=role.id, scope_type="plant", scope_id=plant_id,
            ))

        with TestClient(create_app(settings, database=db)) as client:
            reservations.auth(client, username)
            uom = materials.write(client, "/api/v1/master-data/uoms", {
                "code": f"G76-UN-{suffix}", "dimension": "COUNT", "canonical": True,
            })["id"]
            material = materials.new_article(client, suffix, "G76-STEEL", "PURCHASED", uom)
            materials.bom(client, str(revision_id), datetime.now(timezone.utc) - timedelta(days=1), [
                (material, "2", uom, None, None),
            ])
            warehouse = reservations.post(client, "/api/v1/materials/warehouses", {
                "plant_id": str(plant_id), "code": "CENTRAL", "name": "Central",
            })
            location = reservations.post(client, "/api/v1/materials/locations", {
                "warehouse_id": warehouse["id"], "code": "A1", "name": "Rack A1",
            })
            with db.session() as session:
                _, interruption, _ = MESService(session).pause_operation(
                    operation_id, InterruptionStartCreate(
                        reason_code=f"MATERIAL_SHORTAGE:{material}",
                        occurred_at=start_at + timedelta(minutes=20),
                    ), actor_id,
                )
                interruption_id = str(interruption.id)

            root = "/api/v1/planning/governance/cases"
            command = {
                "plant_id": str(plant_id), "article_id": material,
                "location_id": location["id"], "interruption_id": interruption_id,
                "idempotency_key": f"G76-REAL-{suffix}",
            }
            unknown = client.post(root, json=command)
            assert unknown.status_code == 422, unknown.text
            assert "does not corroborate a known shortage" in unknown.json()["detail"]

            reservations.post(client, "/api/v1/materials/movements", {
                "article_id": material, "location_id": location["id"], "uom_id": uom,
                "kind": "OPENING_ZERO", "quantity": "0", "source_system": "G76_TEST",
                "source_reference": "INITIAL", "idempotency_key": f"G76-ZERO-{suffix}",
            })
            response = client.post(root, json=command)
            assert response.status_code == 201, response.text
            result = response.json()
            assert result["status"] == "UNDER_REVIEW"
            assert result["case"]["severity"] == "STOPPAGE"
            assert result["case"]["scenario_state"] == "BLOCKED"
            assert f"MES:INTERRUPTION:{interruption_id}" in result["case"]["source_references"]
            assert client.post(root, json=command).json() == result
    finally:
        db.dispose()


def test_receipt_lot_persists_with_g6_and_protects_quarantine(governance_case):
    from decimal import Decimal

    from mop.materials.models import MaterialLocation
    from mop.materials.receipt_disposition import LotAction, LotBucket, ReceiptDispositionError
    from mop.materials.receipt_service import ReceiptService
    from mop.materials.reservation_service import ReservationService
    from mop.materials.schemas import MovementCreate
    from mop.materials.service import MaterialsRule, MaterialsService

    db, case, _, _, _ = governance_case
    with db.session() as session:
        location_id = session.scalar(select(MaterialMovement.location_id).where(
            MaterialMovement.article_id == case.article_id,
        ))
        warehouse_id = session.get(MaterialLocation, location_id).warehouse_id
        location = MaterialLocation(
            warehouse_id=warehouse_id, code=f"G76-{uuid4().hex[:10]}", name="Lot-managed stock",
        )
        session.add(location)
        session.flush()
        actor = session.get(User, case.creator_id)
        actor_fields = {"actor_id": actor.id, "username": actor.username}
        stock_fields = {"article_id": case.article_id, "location_id": location.id, "uom_id": case.uom_id}
        receipt = ReceiptService(session)
        inbound = dict(
            receipt_line_ref=f"RECEIPT-{uuid4()}", lot_ref="BATCH-1", quantity=Decimal("10"),
            **stock_fields, **actor_fields,
        )
        lot = receipt.receive(**inbound)
        assert receipt.receive(**inbound).id == lot.id
        stock = MaterialsService(session)
        assert stock.balance(case.article_id, location.id).on_hand == Decimal("10")
        availability = ReservationService(session).availability(case.article_id, location.id)
        assert availability.unallocated_on_hand is None
        assert receipt.balances(lot.id).available == 0
        with pytest.raises(ReceiptDispositionError):
            receipt.decide(
                lot.id, action=LotAction.ISSUE, source=LotBucket.QUARANTINE,
                quantity=Decimal("1"), decision_ref="PREMATURE-ISSUE", expected_revision=0,
                **actor_fields,
            )
        with pytest.raises(MaterialsRule, match="lot-managed"):
            stock.post(MovementCreate(
                **stock_fields, kind="ISSUE", quantity="1", source_system="G76_TEST",
                source_reference=str(lot.id), idempotency_key=str(lot.id),
            ), **actor_fields)

        release = dict(
            action=LotAction.RELEASE, source=LotBucket.QUARANTINE, quantity=Decimal("4"),
            decision_ref="RELEASE-1", expected_revision=0, verified_release_quantity=Decimal("4"),
            **actor_fields,
        )
        decision = receipt.decide(lot.id, **release)
        assert receipt.decide(lot.id, **release).id == decision.id
        assert stock.balance(case.article_id, location.id).on_hand == Decimal("10")
        receipt.decide(
            lot.id, action=LotAction.ISSUE, source=LotBucket.AVAILABLE, quantity=Decimal("3"),
            decision_ref="ISSUE-1", expected_revision=1, **actor_fields,
        )
        balances = receipt.balances(lot.id)
        assert (balances.available, balances.quarantine) == (1, 6)
        assert stock.balance(case.article_id, location.id).on_hand == balances.physical == 7
        session.rollback()


def test_receipt_http_enforces_scope_and_posts_quarantine_once(governance_case):
    from decimal import Decimal
    from mop.materials.models import MaterialLocation

    db, case, _, _, outsider = governance_case
    settings = Settings(environment="test", _env_file=None)
    root = "/api/v1/materials/receipt-lots"
    with db.session() as session:
        stock_location = session.scalar(select(MaterialMovement.location_id).where(
            MaterialMovement.article_id == case.article_id,
        ))
        location = MaterialLocation(
            warehouse_id=session.get(MaterialLocation, stock_location).warehouse_id,
            code=f"G76-HTTP-{uuid4().hex[:10]}", name="Receipt API quarantine",
        )
        session.add(location)
        session.commit()
        iam = IdentityService(session)
        role = iam.create_role(RoleCreate(code=f"G76-REC-{uuid4().hex}", name="Plant receiving"))
        for code in ("materials.receipt.receive", "materials.receipt.read"):
            iam.grant_permission(role.id, code)
        iam.assign_role(case.creator_id, RoleAssignmentCreate(
            role_id=role.id, scope_type="plant", scope_id=case.plant_id,
        ))
        receiver = session.get(User, case.creator_id).username
        outsider_username = session.get(User, outsider).username
        location_id = location.id

    command = {
        "receipt_line_ref": f"G76-RECEIPT-{uuid4()}", "lot_ref": "BATCH-1",
        "article_id": str(case.article_id), "location_id": str(location_id),
        "uom_id": str(case.uom_id), "quantity": "10",
    }
    with TestClient(create_app(settings, database=db)) as client:
        def login(username):
            response = client.post("/api/v1/auth/login", json={
                "username": username, "password": "G65-Tests-Only-Do-Not-Reuse-2026!",
            })
            assert response.status_code == 200, response.text

        assert client.post(root, json=command).status_code == 401
        login(outsider_username)
        assert client.post(root, json=command).status_code == 404
        login(receiver)
        assert client.post(root, json={**command, "quantity": 1.5}).status_code == 422
        received = client.post(root, json=command)
        assert received.status_code == 201, received.text
        lot = received.json()
        assert Decimal(lot["physical"]) == Decimal(lot["quarantine"]) == 10
        assert Decimal(lot["available"]) == 0
        assert client.post(root, json=command).json() == lot
        assert client.post(root, json={**command, "quantity": "11"}).status_code == 409
        url = f"{root}/{lot['id']}"
        assert client.get(url).json() == lot
        login(outsider_username)
        assert client.get(url).status_code == 404

    with db.session() as session:
        assert session.scalar(select(func.count(MaterialMovement.id)).where(
            MaterialMovement.article_id == case.article_id,
            MaterialMovement.location_id == location_id,
        )) == 1
