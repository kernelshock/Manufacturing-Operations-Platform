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

ADMIN_PASSWORD = "Mop-Admin-Integration-2026!"
OPERATOR_PASSWORD = "Mop-Operator-Integration-2026!"


def _bootstrap_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"rbac-admin-{suffix}".lower()
    with database.session() as session:
        service = IdentityService(session)
        user = service.create_user(
            UserCreate(
                username=username,
                display_name="RBAC Administrator",
                password=ADMIN_PASSWORD,
            )
        )
        admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert admin_role is not None
        service.assign_role(
            user.id,
            RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"),
        )

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200


def test_login_me_logout_and_admin_management() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].lower()

    with TestClient(create_app(settings, database=database)) as client:
        _bootstrap_admin(client, database, suffix)

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert "admin.users" in me.json()["permissions"]
        assert "core.organization.write" in me.json()["permissions"]

        created_user = client.post(
            "/api/v1/iam/users",
            json={
                "username": f"operator-{suffix}",
                "display_name": "Operator",
                "password": OPERATOR_PASSWORD,
            },
        )
        assert created_user.status_code == 201
        assert "password" not in created_user.json()
        assert "password_hash" not in created_user.json()

        roles = client.get("/api/v1/iam/roles")
        assert roles.status_code == 200
        assert any(item["code"] == "ADMIN" and item["system"] for item in roles.json())

        logout = client.post("/api/v1/auth/logout")
        assert logout.status_code == 204

        after_logout = client.get("/api/v1/auth/me")
        assert after_logout.status_code == 401


def test_scoped_role_cannot_escape_assigned_organization() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _bootstrap_admin(client, database, suffix.lower())

        org_a = client.post(
            "/api/v1/core/organizations",
            json={"code": f"ORGA-{suffix}", "name": "Organization A"},
        )
        org_b = client.post(
            "/api/v1/core/organizations",
            json={"code": f"ORGB-{suffix}", "name": "Organization B"},
        )
        assert org_a.status_code == 201
        assert org_b.status_code == 201

        role = client.post(
            "/api/v1/iam/roles",
            json={
                "code": f"PLANT-OP-{suffix}",
                "name": "Plant Operator",
                "description": "Scoped plant read/write role",
            },
        )
        assert role.status_code == 201
        role_id = role.json()["id"]

        for permission in ("core.plant.read", "core.plant.write"):
            granted = client.post(f"/api/v1/iam/roles/{role_id}/permissions/{permission}")
            assert granted.status_code == 204

        operator = client.post(
            "/api/v1/iam/users",
            json={
                "username": f"scoped-{suffix.lower()}",
                "display_name": "Scoped Operator",
                "password": OPERATOR_PASSWORD,
            },
        )
        assert operator.status_code == 201

        assignment = client.post(
            f"/api/v1/iam/users/{operator.json()['id']}/roles",
            json={
                "role_id": role_id,
                "scope_type": "organization",
                "scope_id": org_a.json()["id"],
            },
        )
        assert assignment.status_code == 201

        client.post("/api/v1/auth/logout")
        login = client.post(
            "/api/v1/auth/login",
            json={
                "username": f"scoped-{suffix.lower()}",
                "password": OPERATOR_PASSWORD,
            },
        )
        assert login.status_code == 200

        allowed = client.post(
            "/api/v1/core/plants",
            json={
                "organization_id": org_a.json()["id"],
                "code": "P1",
                "name": "Allowed Plant",
            },
        )
        assert allowed.status_code == 201

        denied = client.post(
            "/api/v1/core/plants",
            json={
                "organization_id": org_b.json()["id"],
                "code": "P2",
                "name": "Denied Plant",
            },
        )
        assert denied.status_code == 403

        scoped_list = client.get(
            "/api/v1/core/plants",
            params={"organization_id": org_a.json()["id"]},
        )
        assert scoped_list.status_code == 200

        global_list = client.get("/api/v1/core/plants")
        assert global_list.status_code == 403

        create_org = client.post(
            "/api/v1/core/organizations",
            json={"code": f"NO-{suffix}", "name": "Not Allowed"},
        )
        assert create_org.status_code == 403
