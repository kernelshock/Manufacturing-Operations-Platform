import os
from datetime import datetime, timedelta, timezone
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

PASSWORD = "Mop-G2-BOM-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-bom-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G2 BOM Administrator",
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


def _article(client: TestClient, suffix: str, code: str, kind: str) -> str:
    response = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "SYNTHETIC",
            "external_code": f"{code}-{suffix}",
            "canonical_description": f"Synthetic {code}",
            "article_kind": kind,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _revision(client: TestClient, article_id: str, marker: str) -> str:
    response = client.post(
        f"/api/v1/master-data/articles/{article_id}/revisions",
        json={
            "revision_label": marker,
            "source_fingerprint": (marker.lower()[0] * 64),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _bom(
    client: TestClient,
    revision_id: str,
    revision_no: int,
    marker: str,
    valid_from: datetime,
) -> str:
    response = client.post(
        "/api/v1/master-data/bom-revisions",
        json={
            "parent_article_revision_id": revision_id,
            "revision_no": revision_no,
            "valid_from": valid_from.isoformat(),
            "source_system": "SYNTHETIC",
            "source_fingerprint": marker * 64,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    return response.json()["id"]


def _component(
    client: TestClient,
    bom_id: str,
    child_article_id: str,
    *,
    quantity: str,
    relation_key: str,
    uom_id: str,
    child_revision_id: str | None = None,
    scrap_factor: str | None = None,
) -> str:
    payload = {
        "child_article_id": child_article_id,
        "child_revision_id": child_revision_id,
        "quantity": quantity,
        "source_uom_raw": "UNID.",
        "uom_id": uom_id,
        "source_relation_key": relation_key,
    }
    if scrap_factor is not None:
        payload["scrap_factor"] = scrap_factor
    response = client.post(
        f"/api/v1/master-data/bom-revisions/{bom_id}/components",
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_recursive_bom_explosion_multiplies_quantities_and_retains_paths() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(minutes=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"EA-{suffix}",
                "dimension": "COUNT",
                "canonical": True,
                "active": True,
            },
        )
        assert uom.status_code == 201
        uom_id = uom.json()["id"]

        root_article = _article(client, suffix, "ROOT", "FINISHED_PRODUCT")
        sub_article = _article(client, suffix, "SUB", "MANUFACTURED")
        material_article = _article(client, suffix, "MAT", "PURCHASED")

        root_revision = _revision(client, root_article, "a")
        sub_revision = _revision(client, sub_article, "b")

        sub_bom = _bom(client, sub_revision, 1, "c", valid_from)
        _component(
            client,
            sub_bom,
            material_article,
            quantity="3.00000000",
            relation_key=f"SUB-MAT-{suffix}",
            uom_id=uom_id,
            scrap_factor="0.10000000",
        )
        publish_sub = client.post(
            f"/api/v1/master-data/bom-revisions/{sub_bom}/publish"
        )
        assert publish_sub.status_code == 200

        root_bom = _bom(client, root_revision, 1, "d", valid_from)
        sub_component_id = _component(
            client,
            root_bom,
            sub_article,
            quantity="2.00000000",
            relation_key=f"ROOT-SUB-{suffix}",
            uom_id=uom_id,
            child_revision_id=sub_revision,
        )
        publish_root = client.post(
            f"/api/v1/master-data/bom-revisions/{root_bom}/publish"
        )
        assert publish_root.status_code == 200

        explosion = client.get(
            f"/api/v1/master-data/bom-revisions/{root_bom}/explode",
            params={"quantity": "2"},
        )
        assert explosion.status_code == 200
        payload = explosion.json()
        assert payload["root_quantity"] == "2"

        sub_line = next(
            line for line in payload["paths"]
            if line["article_id"] == sub_article
        )
        material_line = next(
            line for line in payload["paths"]
            if line["article_id"] == material_article
        )

        assert sub_line["quantity"] == "4.00000000"
        assert sub_line["leaf"] is False
        assert sub_line["path_component_ids"] == [sub_component_id]

        assert Decimal(material_line["quantity"]) == Decimal("13.2")
        assert material_line["leaf"] is True
        assert material_line["path_article_codes"] == [
            f"ROOT-{suffix}",
            f"SUB-{suffix}",
            f"MAT-{suffix}",
        ]

        aggregate = {
            line["article_id"]: Decimal(line["quantity"])
            for line in payload["aggregate"]
        }
        assert aggregate[sub_article] == Decimal("4")
        assert aggregate[material_article] == Decimal("13.2")


def test_bom_publish_detects_indirect_cycle() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(minutes=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"PC-{suffix}",
                "dimension": "COUNT",
                "canonical": True,
                "active": True,
            },
        )
        assert uom.status_code == 201
        uom_id = uom.json()["id"]

        article_a = _article(client, suffix, "CYCLE-A", "MANUFACTURED")
        article_b = _article(client, suffix, "CYCLE-B", "MANUFACTURED")
        revision_a = _revision(client, article_a, "e")
        revision_b = _revision(client, article_b, "f")

        bom_b = _bom(client, revision_b, 1, "1", valid_from)
        _component(
            client,
            bom_b,
            article_a,
            quantity="1",
            relation_key=f"B-A-{suffix}",
            uom_id=uom_id,
            child_revision_id=revision_a,
        )
        assert client.post(
            f"/api/v1/master-data/bom-revisions/{bom_b}/publish"
        ).status_code == 200

        bom_a = _bom(client, revision_a, 1, "2", valid_from)
        _component(
            client,
            bom_a,
            article_b,
            quantity="1",
            relation_key=f"A-B-{suffix}",
            uom_id=uom_id,
            child_revision_id=revision_b,
        )

        publish = client.post(
            f"/api/v1/master-data/bom-revisions/{bom_a}/publish"
        )
        assert publish.status_code == 422
        assert publish.json()["detail"] == "BOM cycle detected"


def test_published_bom_is_immutable_and_relation_key_is_idempotent() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(minutes=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"UN-{suffix}",
                "dimension": "COUNT",
                "canonical": True,
                "active": True,
            },
        )
        uom_id = uom.json()["id"]

        root = _article(client, suffix, "IMM-ROOT", "FINISHED_PRODUCT")
        child = _article(client, suffix, "IMM-CHILD", "PURCHASED")
        revision = _revision(client, root, "3")
        bom = _bom(client, revision, 1, "4", valid_from)

        _component(
            client,
            bom,
            child,
            quantity="1",
            relation_key=f"REL-{suffix}",
            uom_id=uom_id,
        )
        duplicate = client.post(
            f"/api/v1/master-data/bom-revisions/{bom}/components",
            json={
                "child_article_id": child,
                "quantity": "2",
                "source_uom_raw": "UNID.",
                "uom_id": uom_id,
                "source_relation_key": f"REL-{suffix}",
            },
        )
        assert duplicate.status_code == 409

        assert client.post(
            f"/api/v1/master-data/bom-revisions/{bom}/publish"
        ).status_code == 200

        mutation = client.post(
            f"/api/v1/master-data/bom-revisions/{bom}/components",
            json={
                "child_article_id": child,
                "quantity": "2",
                "source_uom_raw": "UNID.",
                "uom_id": uom_id,
                "source_relation_key": f"AFTER-{suffix}",
            },
        )
        assert mutation.status_code == 422
        assert mutation.json()["detail"] == (
            "components can only be added to a DRAFT BOM revision"
        )


def test_bom_supersede_preserves_history_and_activates_replacement() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(hours=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"PCS-{suffix}",
                "dimension": "COUNT",
                "canonical": True,
                "active": True,
            },
        )
        uom_id = uom.json()["id"]

        root = _article(client, suffix, "REV-ROOT", "FINISHED_PRODUCT")
        child = _article(client, suffix, "REV-CHILD", "PURCHASED")
        revision_1 = _revision(client, root, "5")
        revision_2 = _revision(client, root, "6")

        bom_1 = _bom(client, revision_1, 1, "7", valid_from)
        _component(
            client,
            bom_1,
            child,
            quantity="1",
            relation_key=f"V1-{suffix}",
            uom_id=uom_id,
        )
        assert client.post(
            f"/api/v1/master-data/bom-revisions/{bom_1}/publish"
        ).status_code == 200

        bom_2 = _bom(client, revision_2, 1, "8", valid_from)
        _component(
            client,
            bom_2,
            child,
            quantity="2",
            relation_key=f"V2-{suffix}",
            uom_id=uom_id,
        )

        effective_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        supersede = client.post(
            f"/api/v1/master-data/bom-revisions/{bom_1}/supersede",
            json={
                "replacement_bom_revision_id": bom_2,
                "effective_at": effective_at.isoformat(),
            },
        )
        assert supersede.status_code == 200
        assert supersede.json()["id"] == bom_2
        assert supersede.json()["status"] == "ACTIVE"

        old = client.get(
            "/api/v1/master-data/bom-revisions",
            params={"parent_article_revision_id": revision_1},
        )
        assert old.status_code == 200
        assert old.json()[0]["status"] == "SUPERSEDED"
        assert old.json()[0]["valid_to"] is not None

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.bom_revision.supersede"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == bom_1 for item in audit.json())
