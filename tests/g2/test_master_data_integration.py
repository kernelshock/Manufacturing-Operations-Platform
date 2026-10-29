import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mop.application import create_app
from mop.config import Settings
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.persistence.database import DatabaseManager


pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)

ADMIN_PASSWORD = "Mop-G2-Admin-Integration-2026!"
READER_PASSWORD = "Mop-G2-Reader-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-admin-{suffix}".lower()
    with database.session() as session:
        service = IdentityService(session)
        user = service.create_user(
            UserCreate(username=username, display_name="G2 Administrator", password=ADMIN_PASSWORD)
        )
        admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert admin_role is not None
        service.assign_role(user.id, RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"))
    response = client.post("/api/v1/auth/login", json={"username": username, "password": ADMIN_PASSWORD})
    assert response.status_code == 200


def test_article_uom_revision_flow_and_audit() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        uom = client.post(
            "/api/v1/master-data/uoms",
            json={"code": f"UN-{suffix}", "dimension": "COUNT", "canonical": True},
        )
        assert uom.status_code == 201
        uom_id = uom.json()["id"]

        alias = client.post(
            "/api/v1/master-data/uom-aliases",
            json={
                "source_system": "PROLOWIN",
                "raw_value": f"UNID-{suffix}",
                "uom_id": uom_id,
                "mapping_status": "MAPPED",
                "conversion_factor": "1",
            },
        )
        assert alias.status_code == 201
        assert alias.json()["approved_by"] is not None

        article = client.post(
            "/api/v1/master-data/articles",
            json={
                "external_system": "PROLOWIN",
                "external_code": f"14027-{suffix}",
                "canonical_description": "ALAMBRE CHICO RESPALDO MB F10",
                "article_kind": "PURCHASED",
                "default_uom_id": uom_id,
            },
        )
        assert article.status_code == 201
        article_id = article.json()["id"]

        duplicate = client.post(
            "/api/v1/master-data/articles",
            json={
                "external_system": "PROLOWIN",
                "external_code": f"14027-{suffix}",
                "canonical_description": "Duplicate",
                "article_kind": "UNKNOWN",
            },
        )
        assert duplicate.status_code == 409

        revision = client.post(
            f"/api/v1/master-data/articles/{article_id}/revisions",
            json={"source_fingerprint": "a" * 64, "revision_label": "source-1"},
        )
        assert revision.status_code == 201
        assert revision.json()["status"] == "DRAFT"

        articles = client.get(
            "/api/v1/master-data/articles",
            params={"external_system": "PROLOWIN", "article_kind": "PURCHASED"},
        )
        assert articles.status_code == 200
        assert any(item["id"] == article_id for item in articles.json())

        revisions = client.get(f"/api/v1/master-data/articles/{article_id}/revisions")
        assert revisions.status_code == 200
        assert len(revisions.json()) == 1

        audit = client.get("/api/v1/audit/events", params={"action": "masterdata.article.create"})
        assert audit.status_code == 200
        assert any(item["object_id"] == article_id for item in audit.json())


def test_masterdata_read_role_cannot_edit() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        role = client.post(
            "/api/v1/iam/roles",
            json={"code": f"MD-READ-{suffix}", "name": "Master Data Reader"},
        )
        assert role.status_code == 201
        role_id = role.json()["id"]
        grant = client.post(f"/api/v1/iam/roles/{role_id}/permissions/masterdata.read")
        assert grant.status_code == 204

        reader = client.post(
            "/api/v1/iam/users",
            json={
                "username": f"md-reader-{suffix.lower()}",
                "display_name": "Master Data Reader",
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
            json={"username": f"md-reader-{suffix.lower()}", "password": READER_PASSWORD},
        )
        assert login.status_code == 200

        read = client.get("/api/v1/master-data/uoms")
        assert read.status_code == 200
        denied = client.post(
            "/api/v1/master-data/uoms",
            json={"code": f"NO-{suffix}", "dimension": "OTHER"},
        )
        assert denied.status_code == 403


def test_masterdata_requires_authentication() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)

    with TestClient(create_app(settings, database=database)) as client:
        response = client.get("/api/v1/master-data/articles")
        assert response.status_code == 401
