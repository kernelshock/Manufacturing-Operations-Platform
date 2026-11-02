import os
from decimal import Decimal
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

ADMIN_PASSWORD = "Mop-G3-Composition-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g3-comp-admin-{suffix}".lower()
    with database.session() as session:
        service = IdentityService(session)
        user = service.create_user(
            UserCreate(
                username=username,
                display_name="G3 Composition Administrator",
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


def _create_finished_article(client: TestClient, suffix: str, code: str) -> str:
    response = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "G3TEST",
            "external_code": f"{code}-{suffix}",
            "canonical_description": f"Finished product {code}",
            "article_kind": "FINISHED_PRODUCT",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_taquilla(client: TestClient, suffix: str) -> str:
    plan = client.post(
        "/api/v1/demand/plans",
        json={"plan_number": f"COMP-{suffix}"},
    )
    assert plan.status_code == 201
    taquilla = client.post(
        f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
        json={
            "taquilla_code": f"TQ-{suffix}",
            "sequence_no": 1,
        },
    )
    assert taquilla.status_code == 201
    return taquilla.json()["id"]


def test_multiple_products_decimal_order_and_stable_line_identity() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        taquilla_id = _create_taquilla(client, suffix)
        article_a = _create_finished_article(client, suffix, "A")
        article_b = _create_finished_article(client, suffix, "B")

        first = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_a,
                "sequence_no": 1,
                "requested_quantity": "12.50000000",
                "source_line_key": "SRC-1",
            },
        )
        second = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_b,
                "sequence_no": 2,
                "requested_quantity": "8.25",
                "source_line_key": "SRC-2",
            },
        )
        assert first.status_code == 201
        assert second.status_code == 201
        first_id = first.json()["id"]
        assert Decimal(first.json()["requested_quantity"]) == Decimal("12.5")

        replay = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_a,
                "sequence_no": 1,
                "requested_quantity": "12.5",
                "source_line_key": "SRC-1",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == first_id

        conflict = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_b,
                "sequence_no": 3,
                "requested_quantity": "99",
                "source_line_key": "SRC-1",
            },
        )
        assert conflict.status_code == 409

        listed = client.get(f"/api/v1/demand/taquillas/{taquilla_id}/products")
        assert listed.status_code == 200
        assert [line["sequence_no"] for line in listed.json()] == [1, 2]
        assert {line["article_id"] for line in listed.json()} == {article_a, article_b}

        updated = client.patch(
            f"/api/v1/demand/taquilla-products/{first_id}",
            json={"sequence_no": 1, "requested_quantity": "13.75"},
        )
        assert updated.status_code == 200
        assert updated.json()["id"] == first_id
        assert Decimal(updated.json()["requested_quantity"]) == Decimal("13.75")

        ready = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/status",
            json={"status": "READY"},
        )
        assert ready.status_code == 200

        frozen = client.patch(
            f"/api/v1/demand/taquilla-products/{first_id}",
            json={"sequence_no": 1, "requested_quantity": "14"},
        )
        assert frozen.status_code == 422

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "demand.taquilla_product.update"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == first_id for item in audit.json())


def test_non_finished_or_missing_article_is_rejected() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        taquilla_id = _create_taquilla(client, suffix)

        purchased = client.post(
            "/api/v1/master-data/articles",
            json={
                "external_system": "G3TEST",
                "external_code": f"MAT-{suffix}",
                "canonical_description": "Purchased material",
                "article_kind": "PURCHASED",
            },
        )
        assert purchased.status_code == 201

        invalid = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": purchased.json()["id"],
                "sequence_no": 1,
                "requested_quantity": "1",
            },
        )
        assert invalid.status_code == 422

        missing = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": str(uuid4()),
                "sequence_no": 1,
                "requested_quantity": "1",
            },
        )
        assert missing.status_code == 404


def test_duplicate_sequence_and_nonpositive_quantity_are_rejected() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        taquilla_id = _create_taquilla(client, suffix)
        article_a = _create_finished_article(client, suffix, "SEQ-A")
        article_b = _create_finished_article(client, suffix, "SEQ-B")

        first = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_a,
                "sequence_no": 1,
                "requested_quantity": "1",
            },
        )
        assert first.status_code == 201

        duplicate_sequence = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_b,
                "sequence_no": 1,
                "requested_quantity": "2",
            },
        )
        assert duplicate_sequence.status_code == 409

        nonpositive = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_b,
                "sequence_no": 2,
                "requested_quantity": "0",
            },
        )
        assert nonpositive.status_code == 422
