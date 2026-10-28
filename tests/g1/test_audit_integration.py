import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from mop.application import create_app
from mop.audit.models import AuditEntry
from mop.config import Settings
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, UserCreate
from mop.iam.service import IdentityService
from mop.persistence.database import DatabaseManager


pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)

ADMIN_PASSWORD = "Mop-Audit-Admin-2026!"


def _bootstrap_admin(client: TestClient, database: DatabaseManager, suffix: str) -> str:
    username = f"audit-admin-{suffix}".lower()
    with database.session() as session:
        service = IdentityService(session)
        user = service.create_user(
            UserCreate(
                username=username,
                display_name="Audit Administrator",
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
        headers={"x-request-id": f"login-{suffix}"},
    )
    assert login.status_code == 200
    return username


def test_auth_iam_and_core_mutations_are_audited_without_secrets() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].lower()

    with TestClient(create_app(settings, database=database)) as client:
        failed = client.post(
            "/api/v1/auth/login",
            json={"username": f"missing-{suffix}", "password": "Never-Persist-This-Password!"},
            headers={"x-request-id": f"failed-{suffix}"},
        )
        assert failed.status_code == 401

        admin_username = _bootstrap_admin(client, database, suffix)

        organization = client.post(
            "/api/v1/core/organizations",
            json={"code": f"AUD-{suffix}", "name": "Audited Organization"},
            headers={"x-request-id": f"org-{suffix}"},
        )
        assert organization.status_code == 201

        created_user = client.post(
            "/api/v1/iam/users",
            json={
                "username": f"audit-user-{suffix}",
                "display_name": "Audited User",
                "password": "Never-Persist-This-Other-Password!",
            },
            headers={"x-request-id": f"user-{suffix}"},
        )
        assert created_user.status_code == 201

        response = client.get("/api/v1/audit/events", params={"limit": 50})
        assert response.status_code == 200
        events = response.json()
        actions = {item["action"] for item in events}
        assert "auth.login.failure" in actions
        assert "auth.login.success" in actions
        assert "core.organization.create" in actions
        assert "iam.user.create" in actions

        admin_events = [item for item in events if item["actor_username"] == admin_username]
        assert admin_events

        serialized = repr(events)
        assert "Never-Persist-This-Password!" not in serialized
        assert "Never-Persist-This-Other-Password!" not in serialized

        organization_event = next(
            item for item in events if item["action"] == "core.organization.create"
        )
        assert organization_event["request_id"] == f"org-{suffix}"
        assert organization_event["object_id"] == organization.json()["id"]


def test_audit_table_rejects_update_and_delete() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].lower()

    with TestClient(create_app(settings, database=database)) as client:
        _bootstrap_admin(client, database, suffix)

    with database.session() as session:
        entry = session.scalar(
            select(AuditEntry).where(AuditEntry.action == "auth.login.success").order_by(
                AuditEntry.occurred_at.desc()
            )
        )
        assert entry is not None
        entry_id = entry.id

    with pytest.raises(DBAPIError):
        with database.engine.begin() as connection:
            connection.execute(
                text("UPDATE audit_event SET outcome='tampered' WHERE id=:id"),
                {"id": entry_id},
            )

    with pytest.raises(DBAPIError):
        with database.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM audit_event WHERE id=:id"),
                {"id": entry_id},
            )


def test_audit_api_requires_explicit_permission() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)

    with TestClient(create_app(settings, database=database)) as client:
        response = client.get("/api/v1/audit/events")
        assert response.status_code == 401
