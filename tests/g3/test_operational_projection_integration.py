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

PASSWORD = "Mop-G3-Projection-2026!"


def _login_admin(client, database, suffix):
    username = f"g3-projection-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G3 Projection Administrator",
                password=PASSWORD,
            )
        )
        role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert role is not None
        identity.assign_role(
            user.id,
            RoleAssignmentCreate(role_id=role.id, scope_type="global"),
        )
    assert client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    ).status_code == 200


def _article(client, suffix, code):
    response = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "G3VIEW",
            "external_code": f"{code}-{suffix}",
            "canonical_description": f"Projection product {code}",
            "article_kind": "FINISHED_PRODUCT",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_operational_projection_aggregates_plan_taquillas_products_and_blockers():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        plan = client.post(
            "/api/v1/demand/plans",
            json={"plan_number": f"VIEW-{suffix}"},
        )
        assert plan.status_code == 201

        first = client.post(
            f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
            json={"taquilla_code": f"26-{suffix}-A", "sequence_no": 1},
        )
        second = client.post(
            f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
            json={"taquilla_code": f"26-{suffix}-B", "sequence_no": 2},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        topology = client.patch(
            f"/api/v1/demand/taquillas/{first.json()['id']}/topology",
            json={"vehicle_topology": "DOUBLE_DECK"},
        )
        assert topology.status_code == 200

        upper = _article(client, suffix, "UP")
        lower = _article(client, suffix, "LOW")

        assert client.post(
            f"/api/v1/demand/taquillas/{first.json()['id']}/products",
            json={
                "article_id": upper["id"],
                "sequence_no": 1,
                "requested_quantity": "10",
                "deck_position": "UPPER",
                "source_document_key": "DOC-B",
                "source_line_key": "UP-1",
            },
        ).status_code == 201
        assert client.post(
            f"/api/v1/demand/taquillas/{first.json()['id']}/products",
            json={
                "article_id": lower["id"],
                "sequence_no": 2,
                "requested_quantity": "12",
                "deck_position": "LOWER",
                "source_document_key": "DOC-A",
                "source_line_key": "LOW-1",
            },
        ).status_code == 201

        projection = client.get(
            f"/api/v1/demand/plans/{plan.json()['id']}/projection"
        )
        assert projection.status_code == 200
        body = projection.json()

        assert body["plan_number"] == f"VIEW-{suffix}"
        assert body["taquilla_count"] == 2
        assert body["product_line_count"] == 2
        assert body["routing_missing_count"] == 2
        assert body["blocked_taquilla_count"] == 2

        first_projection = body["taquillas"][0]
        assert first_projection["taquilla_code"] == f"26-{suffix}-A"
        assert first_projection["vehicle_topology"] == "DOUBLE_DECK"
        assert first_projection["product_count"] == 2
        assert first_projection["total_requested_quantity"] == "22.00000000"
        assert first_projection["routing_bound_count"] == 0
        assert first_projection["routing_missing_count"] == 2

        products = first_projection["products"]
        assert [item["article_code"] for item in products] == [
            upper["external_code"],
            lower["external_code"],
        ]
        assert [item["deck_position"] for item in products] == [
            "UPPER",
            "LOWER",
        ]
        assert products[0]["source_document_key"] == "DOC-B"
        assert products[1]["source_document_key"] == "DOC-A"
        assert products[0]["routing"]["routing_revision_id"] is None


def test_operational_projection_requires_demand_read_permission():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)

    with TestClient(create_app(settings, database=database)) as client:
        response = client.get(
            "/api/v1/demand/plans/00000000-0000-0000-0000-000000000001/projection"
        )
        assert response.status_code == 401
