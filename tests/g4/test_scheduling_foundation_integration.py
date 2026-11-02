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

pytestmark = pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ, reason="requires an explicit PostgreSQL integration database")
ADMIN_PASSWORD = "Mop-G4-Admin-Integration-2026!"
READER_PASSWORD = "Mop-G4-Reader-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g4-admin-{suffix}".lower()
    with database.session() as session:
        service = IdentityService(session)
        user = service.create_user(UserCreate(username=username, display_name="G4 Administrator", password=ADMIN_PASSWORD))
        admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert admin_role is not None
        service.assign_role(user.id, RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"))
    assert client.post("/api/v1/auth/login", json={"username": username, "password": ADMIN_PASSWORD}).status_code == 200


def _create_plan(client: TestClient, suffix: str) -> str:
    r = client.post("/api/v1/demand/plans", json={"plan_number": f"G4-PLAN-{suffix}"})
    assert r.status_code == 201
    return r.json()["id"]


def test_scenario_run_identity_lifecycle_and_audit() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan_id = _create_plan(client, suffix)
        created = client.post("/api/v1/aps/scenarios", json={
            "plan_id": plan_id,
            "scenario_code": f"APS-{suffix}",
            "name": "Baseline schedule",
            "horizon_start": "2026-11-02T07:00:00-03:00",
            "horizon_end": "2026-11-06T15:00:00-03:00",
            "planning_timezone": "America/Argentina/Cordoba",
        })
        assert created.status_code == 201
        scenario_id = created.json()["id"]
        assert created.json()["status"] == "DRAFT"

        ready = client.post(f"/api/v1/aps/scenarios/{scenario_id}/status", json={"status": "READY"})
        assert ready.status_code == 200
        run1 = client.post(f"/api/v1/aps/scenarios/{scenario_id}/runs", json={"algorithm_key": "foundation-placeholder", "algorithm_version": "g4.1"})
        run2 = client.post(f"/api/v1/aps/scenarios/{scenario_id}/runs", json={"algorithm_key": "foundation-placeholder", "algorithm_version": "g4.1"})
        assert run1.status_code == 201 and run2.status_code == 201
        assert [run1.json()["run_number"], run2.json()["run_number"]] == [1, 2]
        assert run1.json()["status"] == "CREATED"

        frozen = client.post(f"/api/v1/aps/scenarios/{scenario_id}/status", json={"status": "DRAFT"})
        assert frozen.status_code == 422
        cancelled = client.post(f"/api/v1/aps/runs/{run1.json()['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"

        audit = client.get("/api/v1/audit/events", params={"action": "aps.run.create"})
        assert audit.status_code == 200
        assert any(item["object_id"] == run2.json()["id"] for item in audit.json())


def test_aps_read_permission_cannot_mutate() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        role = client.post("/api/v1/iam/roles", json={"code": f"APS-READ-{suffix}", "name": "APS Reader"})
        assert role.status_code == 201
        role_id = role.json()["id"]
        assert client.post(f"/api/v1/iam/roles/{role_id}/permissions/aps.read").status_code == 204
        reader = client.post("/api/v1/iam/users", json={"username": f"aps-reader-{suffix.lower()}", "display_name": "APS Reader", "password": READER_PASSWORD})
        assert reader.status_code == 201
        assert client.post(f"/api/v1/iam/users/{reader.json()['id']}/roles", json={"role_id": role_id, "scope_type": "global"}).status_code == 201
        client.post("/api/v1/auth/logout")
        assert client.post("/api/v1/auth/login", json={"username": f"aps-reader-{suffix.lower()}", "password": READER_PASSWORD}).status_code == 200
        assert client.get("/api/v1/aps/scenarios").status_code == 200
        denied = client.post("/api/v1/aps/scenarios", json={"plan_id": str(uuid4()), "scenario_code": "NO", "name": "No", "horizon_start": "2026-11-02T07:00:00-03:00", "horizon_end": "2026-11-03T07:00:00-03:00", "planning_timezone": "America/Argentina/Cordoba"})
        assert denied.status_code == 403


def test_aps_requires_authentication() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    with TestClient(create_app(settings, database=database)) as client:
        assert client.get("/api/v1/aps/scenarios").status_code == 401
