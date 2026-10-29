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

PASSWORD = "Mop-G2-Product-Config-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-config-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G2 Product Configuration Administrator",
                password=PASSWORD,
            )
        )
        admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert admin_role is not None
        identity.assign_role(
            user.id,
            RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"),
        )

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert login.status_code == 200


def _create_article(
    client: TestClient,
    suffix: str,
    *,
    kind: str,
) -> str:
    response = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "SYNTHETIC",
            "external_code": f"CFG-{kind}-{suffix}",
            "canonical_description": f"Synthetic {kind} article",
            "article_kind": kind,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_finished_article_configuration_flow_and_audit() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        length_uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"MM-{suffix}",
                "dimension": "LENGTH",
                "canonical": True,
                "active": True,
            },
        )
        assert length_uom.status_code == 201

        article_id = _create_article(
            client,
            suffix,
            kind="FINISHED_PRODUCT",
        )

        configuration = client.post(
            "/api/v1/master-data/product-configurations",
            json={
                "article_id": article_id,
                "family_code": "SEAT-FAMILY",
                "family_name": "Passenger Seat Family",
                "model_code": "MODEL-A",
                "model_name": "Model A",
                "product_class": "Premium",
                "width": "440.0000",
                "width_uom_id": length_uom.json()["id"],
                "configuration_string": "Model A / 440 / premium / synthetic",
                "active": True,
            },
        )
        assert configuration.status_code == 201
        assert configuration.json()["article_id"] == article_id
        assert configuration.json()["family_code"] == "SEAT-FAMILY"

        duplicate = client.post(
            "/api/v1/master-data/product-configurations",
            json={
                **configuration.json(),
                "configuration_string": "Duplicate configuration",
            },
        )
        assert duplicate.status_code == 409

        listed = client.get(
            "/api/v1/master-data/product-configurations",
            params={"family_code": "seat-family", "model_code": "model-a"},
        )
        assert listed.status_code == 200
        assert [item["article_id"] for item in listed.json()] == [article_id]

        exact = client.get(
            f"/api/v1/master-data/articles/{article_id}/product-configuration"
        )
        assert exact.status_code == 200
        assert exact.json()["configuration_string"].startswith("Model A")

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.product_configuration.create"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == configuration.json()["id"] for item in audit.json())


def test_product_configuration_requires_finished_product() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        article_id = _create_article(client, suffix, kind="MANUFACTURED")

        response = client.post(
            "/api/v1/master-data/product-configurations",
            json={
                "article_id": article_id,
                "family_code": "COMPONENT",
                "family_name": "Component",
                "model_code": "COMP-A",
                "model_name": "Component A",
                "product_class": "Internal",
                "configuration_string": "Not a sellable finished configuration",
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == (
            "product configuration requires a FINISHED_PRODUCT article"
        )


def test_width_rejects_non_length_uom() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        count_uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"EA-{suffix}",
                "dimension": "COUNT",
                "canonical": True,
                "active": True,
            },
        )
        assert count_uom.status_code == 201
        article_id = _create_article(client, suffix, kind="FINISHED_PRODUCT")

        response = client.post(
            "/api/v1/master-data/product-configurations",
            json={
                "article_id": article_id,
                "family_code": "SEAT-FAMILY",
                "family_name": "Passenger Seat Family",
                "model_code": "MODEL-B",
                "model_name": "Model B",
                "product_class": "Standard",
                "width": "450",
                "width_uom_id": count_uom.json()["id"],
                "configuration_string": "Synthetic invalid width unit",
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == (
            "width unit must be an active canonical LENGTH unit"
        )
