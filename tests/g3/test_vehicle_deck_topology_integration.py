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

ADMIN_PASSWORD = "Mop-G3-Deck-Topology-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g3-deck-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G3 Deck Administrator",
                password=ADMIN_PASSWORD,
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
        json={"username": username, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200


def _create_finished_article(client: TestClient, suffix: str, code: str) -> str:
    response = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "G3DECK",
            "external_code": f"{code}-{suffix}",
            "canonical_description": f"Finished product {code}",
            "article_kind": "FINISHED_PRODUCT",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_taquilla(client: TestClient, suffix: str, code: str) -> str:
    plan = client.post(
        "/api/v1/demand/plans",
        json={"plan_number": f"DECK-{code}-{suffix}"},
    )
    assert plan.status_code == 201
    taquilla = client.post(
        f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
        json={"taquilla_code": f"TQ-{code}-{suffix}", "sequence_no": 1},
    )
    assert taquilla.status_code == 201
    assert taquilla.json()["vehicle_topology"] == "SIMPLE"
    return taquilla.json()["id"]


def test_simple_taquilla_uses_single_deck_and_rejects_upper_lower() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        taquilla_id = _create_taquilla(client, suffix, "S")
        article_id = _create_finished_article(client, suffix, "SINGLE")

        valid = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_id,
                "sequence_no": 1,
                "requested_quantity": "20",
                "deck_position": "SINGLE",
                "source_document_key": "DOC-SIMPLE",
            },
        )
        assert valid.status_code == 201
        assert valid.json()["deck_position"] == "SINGLE"
        assert valid.json()["source_document_key"] == "DOC-SIMPLE"

        invalid = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_id,
                "sequence_no": 2,
                "requested_quantity": "1",
                "deck_position": "UPPER",
            },
        )
        assert invalid.status_code == 422

        too_late = client.patch(
            f"/api/v1/demand/taquillas/{taquilla_id}/topology",
            json={"vehicle_topology": "DOUBLE_DECK"},
        )
        assert too_late.status_code == 422


def test_double_deck_requires_explicit_upper_lower_and_document_does_not_infer_deck() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        taquilla_id = _create_taquilla(client, suffix, "D")
        upper_article = _create_finished_article(client, suffix, "UP")
        lower_article = _create_finished_article(client, suffix, "LOW")

        topology = client.patch(
            f"/api/v1/demand/taquillas/{taquilla_id}/topology",
            json={"vehicle_topology": "DOUBLE_DECK"},
        )
        assert topology.status_code == 200
        assert topology.json()["vehicle_topology"] == "DOUBLE_DECK"

        missing_explicit_deck = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": upper_article,
                "sequence_no": 1,
                "requested_quantity": "10",
                "source_document_key": "DOC-A",
            },
        )
        assert missing_explicit_deck.status_code == 422

        upper = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": upper_article,
                "sequence_no": 1,
                "requested_quantity": "10",
                "deck_position": "UPPER",
                "source_document_key": "DOC-A",
            },
        )
        lower = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": lower_article,
                "sequence_no": 2,
                "requested_quantity": "12",
                "deck_position": "LOWER",
                "source_document_key": "DOC-B",
            },
        )
        assert upper.status_code == 201
        assert lower.status_code == 201

        same_document_other_deck = client.patch(
            f"/api/v1/demand/taquilla-products/{lower.json()['id']}",
            json={
                "sequence_no": 2,
                "requested_quantity": "12",
                "deck_position": "LOWER",
                "source_document_key": "DOC-A",
            },
        )
        assert same_document_other_deck.status_code == 200
        assert same_document_other_deck.json()["source_document_key"] == "DOC-A"
        assert same_document_other_deck.json()["deck_position"] == "LOWER"

        listed = client.get(f"/api/v1/demand/taquillas/{taquilla_id}/products")
        assert listed.status_code == 200
        assert [item["deck_position"] for item in listed.json()] == ["UPPER", "LOWER"]

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "demand.taquilla.topology.update"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == taquilla_id for item in audit.json())


def test_double_deck_rejects_single_position() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        taquilla_id = _create_taquilla(client, suffix, "R")
        article_id = _create_finished_article(client, suffix, "R")

        topology = client.patch(
            f"/api/v1/demand/taquillas/{taquilla_id}/topology",
            json={"vehicle_topology": "DOUBLE_DECK"},
        )
        assert topology.status_code == 200

        invalid = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/products",
            json={
                "article_id": article_id,
                "sequence_no": 1,
                "requested_quantity": "4",
                "deck_position": "SINGLE",
            },
        )
        assert invalid.status_code == 422
