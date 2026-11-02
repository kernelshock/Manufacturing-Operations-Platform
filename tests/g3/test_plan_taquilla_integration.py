import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mop.application import create_app
from mop.config import Settings
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, UserCreate
from mop.iam.service import IdentityService
from mop.persistence.database import DatabaseManager


pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)

ADMIN_PASSWORD = "Mop-G3-Admin-Integration-2026!"
READER_PASSWORD = "Mop-G3-Reader-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g3-admin-{suffix}".lower()
    with database.session() as session:
        service = IdentityService(session)
        user = service.create_user(
            UserCreate(
                username=username,
                display_name="G3 Administrator",
                password=ADMIN_PASSWORD,
            )
        )
        admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert admin_role is not None
        service.assign_role(
            user.id,
            RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"),
        )

    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200


def test_plan_and_multiple_taquillas_keep_stable_identity_and_audit() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        created = client.post(
            "/api/v1/demand/plans",
            json={
                "plan_number": f"PLAN-{suffix}",
                "description": "Production plan integration fixture",
            },
        )
        assert created.status_code == 201
        plan_id = created.json()["id"]
        assert created.json()["status"] == "DRAFT"

        first = client.post(
            f"/api/v1/demand/plans/{plan_id}/taquillas",
            json={
                "taquilla_code": f"26-{suffix[:3]}A",
                "sequence_no": 1,
                "description": "First Taquilla",
            },
        )
        second = client.post(
            f"/api/v1/demand/plans/{plan_id}/taquillas",
            json={
                "taquilla_code": f"26-{suffix[:3]}B",
                "sequence_no": 2,
                "description": "Second Taquilla",
            },
        )
        assert first.status_code == 201
        assert second.status_code == 201

        renamed = client.patch(
            f"/api/v1/demand/plans/{plan_id}/number",
            json={"plan_number": f"PLAN-EDIT-{suffix}"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["id"] == plan_id
        assert renamed.json()["plan_number"] == f"PLAN-EDIT-{suffix}"

        listed = client.get(f"/api/v1/demand/plans/{plan_id}/taquillas")
        assert listed.status_code == 200
        assert [item["sequence_no"] for item in listed.json()] == [1, 2]
        assert {item["plan_id"] for item in listed.json()} == {plan_id}

        opened = client.post(
            f"/api/v1/demand/plans/{plan_id}/status",
            json={"status": "OPEN"},
        )
        assert opened.status_code == 200
        assert opened.json()["status"] == "OPEN"

        ready = client.post(
            f"/api/v1/demand/taquillas/{first.json()['id']}/status",
            json={"status": "READY"},
        )
        assert ready.status_code == 200
        assert ready.json()["status"] == "READY"

        invalid = client.post(
            f"/api/v1/demand/taquillas/{first.json()['id']}/status",
            json={"status": "DRAFT"},
        )
        assert invalid.status_code == 422

        duplicate_sequence = client.post(
            f"/api/v1/demand/plans/{plan_id}/taquillas",
            json={
                "taquilla_code": f"26-{suffix[:3]}C",
                "sequence_no": 2,
            },
        )
        assert duplicate_sequence.status_code == 409

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "demand.plan.number.update"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == plan_id for item in audit.json())


def test_demand_read_role_cannot_mutate() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        role = client.post(
            "/api/v1/iam/roles",
            json={"code": f"DEMAND-READ-{suffix}", "name": "Demand Reader"},
        )
        assert role.status_code == 201
        role_id = role.json()["id"]
        grant = client.post(
            f"/api/v1/iam/roles/{role_id}/permissions/demand.read"
        )
        assert grant.status_code == 204

        reader = client.post(
            "/api/v1/iam/users",
            json={
                "username": f"demand-reader-{suffix.lower()}",
                "display_name": "Demand Reader",
                "password": READER_PASSWORD,
            },
        )
        assert reader.status_code == 201
        assignment = client.post(
            f"/api/v1/iam/users/{reader.json()['id']}/roles",
            json={"role_id": role_id, "scope_type": "global"},
        )
        assert assignment.status_code == 201

        client.post("/api/v1/auth/logout")
        login = client.post(
            "/api/v1/auth/login",
            json={
                "username": f"demand-reader-{suffix.lower()}",
                "password": READER_PASSWORD,
            },
        )
        assert login.status_code == 200

        read = client.get("/api/v1/demand/plans")
        assert read.status_code == 200

        denied = client.post(
            "/api/v1/demand/plans",
            json={"plan_number": f"NO-{suffix}"},
        )
        assert denied.status_code == 403


def test_demand_requires_authentication() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)

    with TestClient(create_app(settings, database=database)) as client:
        response = client.get("/api/v1/demand/plans")
        assert response.status_code == 401
