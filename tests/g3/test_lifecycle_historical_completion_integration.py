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
ADMIN_PASSWORD = "Mop-G3-Historical-2026!"


def _login_admin(client, database, suffix):
    username = f"g3-hist-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G3 Historical Administrator",
                password=ADMIN_PASSWORD,
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
        json={"username": username, "password": ADMIN_PASSWORD},
    ).status_code == 200


def _plan(client, suffix, count=2):
    plan = client.post(
        "/api/v1/demand/plans",
        json={"plan_number": f"HIST-{suffix}"},
    )
    assert plan.status_code == 201
    rows = []
    for index in range(1, count + 1):
        response = client.post(
            f"/api/v1/demand/plans/{plan.json()['id']}/taquillas",
            json={
                "taquilla_code": f"H-{suffix}-{index}",
                "sequence_no": index,
            },
        )
        assert response.status_code == 201
        rows.append(response.json())
    return plan.json(), rows


def test_historical_completion_closes_plan_and_classifies_without_mes_actuals():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan, rows = _plan(client, suffix)
        assert client.post(
            f"/api/v1/demand/taquillas/{rows[1]['id']}/cancel",
            json={"reason": "Erroneous legacy row"},
        ).status_code == 200

        completed = client.post(
            f"/api/v1/demand/plans/{plan['id']}/historical-completion",
            json={
                "classification": "DELAYED",
                "note": "Legacy statistical baseline",
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"
        assert (
            completed.json()["historical_completion_classification"]
            == "DELAYED"
        )

        listed = client.get(
            f"/api/v1/demand/plans/{plan['id']}/taquillas"
        ).json()
        by_id = {item["id"]: item for item in listed}
        assert by_id[rows[0]["id"]]["status"] == "COMPLETED"
        assert (
            by_id[rows[0]["id"]]["historical_completion_classification"]
            == "DELAYED"
        )
        assert by_id[rows[1]["id"]]["status"] == "CANCELLED"

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "demand.plan.historical_completion"},
        )
        event = next(
            item for item in audit.json()
            if item["object_id"] == plan["id"]
        )
        assert event["details"]["mes_actuals_created"] is False


def test_on_time_completion_and_mixed_live_completion_rejection():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        first, _ = _plan(client, suffix + "A", 1)
        response = client.post(
            f"/api/v1/demand/plans/{first['id']}/historical-completion",
            json={"classification": "ON_TIME"},
        )
        assert response.status_code == 200
        assert (
            response.json()["historical_completion_classification"]
            == "ON_TIME"
        )

        second, rows = _plan(client, suffix + "B", 1)
        assert client.post(
            f"/api/v1/demand/taquillas/{rows[0]['id']}/status",
            json={"status": "READY"},
        ).status_code == 200
        assert client.post(
            f"/api/v1/demand/taquillas/{rows[0]['id']}/status",
            json={"status": "COMPLETED"},
        ).status_code == 200
        rejected = client.post(
            f"/api/v1/demand/plans/{second['id']}/historical-completion",
            json={"classification": "DELAYED"},
        )
        assert rejected.status_code == 422


def test_cancellation_is_reasoned_and_generic_cancel_is_blocked():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan, rows = _plan(client, suffix, 1)
        taquilla_id = rows[0]["id"]

        assert client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/cancel",
            json={"reason": "   "},
        ).status_code == 422

        cancelled = client.post(
            f"/api/v1/demand/taquillas/{taquilla_id}/cancel",
            json={"reason": "Loaded by mistake"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["id"] == taquilla_id
        assert cancelled.json()["status"] == "CANCELLED"

        assert client.post(
            f"/api/v1/demand/plans/{plan['id']}/status",
            json={"status": "CANCELLED"},
        ).status_code == 422


def test_safe_draft_delete_requires_no_product_dependencies():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _, rows = _plan(client, suffix, 2)

        assert client.delete(
            f"/api/v1/demand/taquillas/{rows[0]['id']}"
        ).status_code == 204

        article = client.post(
            "/api/v1/master-data/articles",
            json={
                "external_system": "G3HIST",
                "external_code": f"FP-{suffix}",
                "canonical_description": "Finished product",
                "article_kind": "FINISHED_PRODUCT",
            },
        )
        assert article.status_code == 201
        assert client.post(
            f"/api/v1/demand/taquillas/{rows[1]['id']}/products",
            json={
                "article_id": article.json()["id"],
                "sequence_no": 1,
                "requested_quantity": "1",
            },
        ).status_code == 201

        blocked = client.delete(
            f"/api/v1/demand/taquillas/{rows[1]['id']}"
        )
        assert blocked.status_code == 422


def test_normal_plan_completion_requires_terminal_taquillas():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan, rows = _plan(client, suffix, 1)

        assert client.post(
            f"/api/v1/demand/plans/{plan['id']}/status",
            json={"status": "OPEN"},
        ).status_code == 200
        assert client.post(
            f"/api/v1/demand/plans/{plan['id']}/status",
            json={"status": "COMPLETED"},
        ).status_code == 422

        assert client.post(
            f"/api/v1/demand/taquillas/{rows[0]['id']}/status",
            json={"status": "READY"},
        ).status_code == 200
        assert client.post(
            f"/api/v1/demand/taquillas/{rows[0]['id']}/status",
            json={"status": "COMPLETED"},
        ).status_code == 200
        assert client.post(
            f"/api/v1/demand/plans/{plan['id']}/status",
            json={"status": "COMPLETED"},
        ).status_code == 200
