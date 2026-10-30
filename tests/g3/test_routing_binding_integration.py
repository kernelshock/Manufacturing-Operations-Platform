import os
from datetime import datetime, timedelta, timezone
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

ADMIN_PASSWORD = "Mop-G3-Routing-Binding-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g3-routing-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G3 Routing Administrator",
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


def _article_revision(client: TestClient, suffix: str, code: str, marker: str) -> tuple[str, str]:
    article = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "G3ROUTE",
            "external_code": f"{code}-{suffix}",
            "canonical_description": f"Finished product {code}",
            "article_kind": "FINISHED_PRODUCT",
        },
    )
    assert article.status_code == 201
    revision = client.post(
        f"/api/v1/master-data/articles/{article.json()['id']}/revisions",
        json={
            "revision_label": marker,
            "source_fingerprint": marker * 64,
        },
    )
    assert revision.status_code == 201
    return article.json()["id"], revision.json()["id"]


def _additional_revision(client: TestClient, article_id: str, marker: str) -> str:
    response = client.post(
        f"/api/v1/master-data/articles/{article_id}/revisions",
        json={
            "revision_label": marker,
            "source_fingerprint": marker * 64,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _published_routing(
    client: TestClient,
    revision_id: str,
    revision_no: int,
    marker: str,
    valid_from: datetime,
    valid_to: datetime | None = None,
) -> str:
    routing = client.post(
        "/api/v1/master-data/routing-revisions",
        json={
            "article_revision_id": revision_id,
            "revision_no": revision_no,
            "valid_from": valid_from.isoformat(),
            "valid_to": valid_to.isoformat() if valid_to else None,
            "source_system": "G3ROUTE",
            "source_fingerprint": marker * 64,
        },
    )
    assert routing.status_code == 201
    routing_id = routing.json()["id"]
    operation = client.post(
        f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
        json={
            "source_operation_code": f"FIN-{marker}",
            "sequence_no": 999,
            "source_description": "Completion marker",
            "operation_kind": "COMPLETION_MARKER",
            "schedulable": False,
            "completion_marker": True,
        },
    )
    assert operation.status_code == 201
    publish = client.post(
        f"/api/v1/master-data/routing-revisions/{routing_id}/publish"
    )
    assert publish.status_code == 200
    return routing_id


def _product_line(client: TestClient, suffix: str, article_id: str, marker: str) -> str:
    plan = client.post(
        "/api/v1/demand/plans",
        json={"plan_number": f"ROUTE-{marker}-{suffix}"},
    )
    assert plan.status_code == 201
    taquilla = client.post(
        f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
        json={
            "taquilla_code": f"TQ-{marker}-{suffix}",
            "sequence_no": 1,
        },
    )
    assert taquilla.status_code == 201
    line = client.post(
        f"/api/v1/demand/taquillas/{taquilla.json()['id']}/products",
        json={
            "article_id": article_id,
            "sequence_no": 1,
            "requested_quantity": "8",
        },
    )
    assert line.status_code == 201
    return line.json()["id"]


def test_resolve_binds_exact_effective_route_for_same_article() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    now = datetime.now(timezone.utc)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        article_id, revision_id = _article_revision(client, suffix, "A", "a")
        routing_id = _published_routing(
            client, revision_id, 1, "b", now - timedelta(hours=1)
        )
        line_id = _product_line(client, suffix, article_id, "A")

        resolved = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/resolve",
            json={"effective_at": now.isoformat()},
        )
        assert resolved.status_code == 200
        body = resolved.json()
        assert body["routing_revision_id"] == routing_id
        assert body["routing_binding_mode"] == "RESOLVED"
        assert body["routing_override_reason"] is None
        assert body["routing_bound_by"] is not None

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "demand.taquilla_product.routing.resolve"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == line_id for item in audit.json())


def test_resolve_rejects_missing_and_ambiguous_effective_routes() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    now = datetime.now(timezone.utc)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        article_id, revision_1 = _article_revision(client, suffix, "B", "c")
        line_id = _product_line(client, suffix, article_id, "B")

        missing = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/resolve",
            json={"effective_at": now.isoformat()},
        )
        assert missing.status_code == 404

        revision_2 = _additional_revision(client, article_id, "d")
        _published_routing(
            client, revision_1, 1, "e", now - timedelta(hours=1)
        )
        _published_routing(
            client, revision_2, 1, "f", now - timedelta(hours=1)
        )

        ambiguous = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/resolve",
            json={"effective_at": now.isoformat()},
        )
        assert ambiguous.status_code == 422
        assert "multiple effective active routing revisions" in ambiguous.json()["detail"]


def test_override_disambiguates_but_cannot_bypass_article_status_or_effectivity() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    now = datetime.now(timezone.utc)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        article_id, revision_1 = _article_revision(client, suffix, "C", "1")
        revision_2 = _additional_revision(client, article_id, "2")
        route_1 = _published_routing(
            client, revision_1, 1, "3", now - timedelta(hours=1)
        )
        route_2 = _published_routing(
            client, revision_2, 1, "4", now - timedelta(hours=1)
        )
        line_id = _product_line(client, suffix, article_id, "C")

        override = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/override",
            json={
                "routing_revision_id": route_2,
                "effective_at": now.isoformat(),
                "reason": "Engineering-approved product revision selection",
            },
        )
        assert override.status_code == 200
        assert override.json()["routing_revision_id"] == route_2
        assert override.json()["routing_binding_mode"] == "OVERRIDE"
        assert (
            override.json()["routing_override_reason"]
            == "Engineering-approved product revision selection"
        )

        other_article, other_revision = _article_revision(
            client, suffix, "OTHER", "5"
        )
        assert other_article != article_id
        other_route = _published_routing(
            client, other_revision, 1, "6", now - timedelta(hours=1)
        )
        wrong_article = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/override",
            json={
                "routing_revision_id": other_route,
                "effective_at": now.isoformat(),
                "reason": "Must fail",
            },
        )
        assert wrong_article.status_code == 422

        future_revision = _additional_revision(client, article_id, "7")
        future_route = _published_routing(
            client, future_revision, 1, "8", now + timedelta(days=1)
        )
        future = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/override",
            json={
                "routing_revision_id": future_route,
                "effective_at": now.isoformat(),
                "reason": "Must also fail",
            },
        )
        assert future.status_code == 422

        draft_revision = _additional_revision(client, article_id, "9")
        draft_route = client.post(
            "/api/v1/master-data/routing-revisions",
            json={
                "article_revision_id": draft_revision,
                "revision_no": 1,
                "valid_from": (now - timedelta(hours=1)).isoformat(),
                "source_system": "G3ROUTE",
                "source_fingerprint": "0" * 64,
            },
        )
        assert draft_route.status_code == 201
        inactive = client.post(
            f"/api/v1/demand/taquilla-products/{line_id}/routing/override",
            json={
                "routing_revision_id": draft_route.json()["id"],
                "effective_at": now.isoformat(),
                "reason": "Draft routes cannot bind",
            },
        )
        assert inactive.status_code == 422


def test_routing_binding_is_frozen_after_taquilla_ready() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    now = datetime.now(timezone.utc)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        article_id, revision_id = _article_revision(client, suffix, "D", "a")
        routing_id = _published_routing(
            client, revision_id, 1, "b", now - timedelta(hours=1)
        )

        plan = client.post(
            "/api/v1/demand/plans",
            json={"plan_number": f"FREEZE-{suffix}"},
        )
        taquilla = client.post(
            f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
            json={"taquilla_code": f"FREEZE-{suffix}", "sequence_no": 1},
        )
        line = client.post(
            f"/api/v1/demand/taquillas/{taquilla.json()['id']}/products",
            json={
                "article_id": article_id,
                "sequence_no": 1,
                "requested_quantity": "1",
            },
        )
        ready = client.post(
            f"/api/v1/demand/taquillas/{taquilla.json()['id']}/status",
            json={"status": "READY"},
        )
        assert ready.status_code == 200

        frozen = client.post(
            f"/api/v1/demand/taquilla-products/{line.json()['id']}/routing/override",
            json={
                "routing_revision_id": routing_id,
                "effective_at": now.isoformat(),
                "reason": "Too late",
            },
        )
        assert frozen.status_code == 422
