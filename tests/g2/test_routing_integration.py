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

PASSWORD = "Mop-G2-Routing-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-routing-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G2 Routing Administrator",
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


def _article_revision(client: TestClient, suffix: str, marker: str) -> tuple[str, str]:
    article = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "SYNTHETIC",
            "external_code": f"ROUTE-{marker}-{suffix}",
            "canonical_description": f"Synthetic routing article {marker}",
            "article_kind": "MANUFACTURED",
        },
    )
    assert article.status_code == 201

    revision = client.post(
        f"/api/v1/master-data/articles/{article.json()['id']}/revisions",
        json={
            "revision_label": marker,
            "source_fingerprint": marker.lower()[0] * 64,
        },
    )
    assert revision.status_code == 201
    return article.json()["id"], revision.json()["id"]


def _core_resource(
    client: TestClient,
    suffix: str,
    marker: str,
) -> tuple[str, str, str]:
    organization = client.post(
        "/api/v1/core/organizations",
        json={
            "code": f"ORG-{marker}-{suffix}",
            "name": f"Organization {marker}",
        },
    )
    assert organization.status_code == 201

    plant = client.post(
        "/api/v1/core/plants",
        json={
            "organization_id": organization.json()["id"],
            "code": f"PLANT-{marker}-{suffix}",
            "name": f"Plant {marker}",
        },
    )
    assert plant.status_code == 201

    area = client.post(
        "/api/v1/core/areas",
        json={
            "plant_id": plant.json()["id"],
            "code": f"AREA-{marker}-{suffix}",
            "name": f"Area {marker}",
        },
    )
    assert area.status_code == 201

    work_center = client.post(
        "/api/v1/core/work-centers",
        json={
            "area_id": area.json()["id"],
            "code": f"WC-{marker}-{suffix}",
            "name": f"Work Center {marker}",
        },
    )
    assert work_center.status_code == 201

    resource = client.post(
        "/api/v1/core/resources",
        json={
            "work_center_id": work_center.json()["id"],
            "code": f"RES-{marker}-{suffix}",
            "name": f"Resource {marker}",
            "resource_type": "machine",
        },
    )
    assert resource.status_code == 201

    return area.json()["id"], work_center.json()["id"], resource.json()["id"]


def _routing(
    client: TestClient,
    revision_id: str,
    revision_no: int,
    marker: str,
    valid_from: datetime,
) -> str:
    response = client.post(
        "/api/v1/master-data/routing-revisions",
        json={
            "article_revision_id": revision_id,
            "revision_no": revision_no,
            "valid_from": valid_from.isoformat(),
            "source_system": "SYNTHETIC",
            "source_fingerprint": marker * 64,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    return response.json()["id"]


def test_routing_definition_references_g1_resources_and_effective_lookup() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(minutes=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _, article_revision_id = _article_revision(client, suffix, "a")
        area_id, work_center_id, resource_id = _core_resource(
            client, suffix, "A"
        )
        routing_id = _routing(
            client,
            article_revision_id,
            1,
            "b",
            valid_from,
        )

        operation = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
            json={
                "source_operation_code": "030",
                "sequence_no": 30,
                "source_description": "Robotized welding",
                "area_id": area_id,
                "work_center_id": work_center_id,
                "operation_kind": "PHYSICAL_PRODUCTION",
                "schedulable": True,
                "nominal_rate": "2.00000000",
                "rate_uom": "parts/min",
            },
        )
        assert operation.status_code == 201
        operation_id = operation.json()["id"]

        assignment = client.post(
            f"/api/v1/master-data/routing-operations/{operation_id}/resources",
            json={
                "resource_id": resource_id,
                "principal": True,
                "capacity_factor": "1.00000000",
            },
        )
        assert assignment.status_code == 201

        finish = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
            json={
                "source_operation_code": "FIN",
                "sequence_no": 999,
                "source_description": "Completion marker",
                "operation_kind": "COMPLETION_MARKER",
                "schedulable": False,
                "completion_marker": True,
            },
        )
        assert finish.status_code == 201

        publish = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/publish"
        )
        assert publish.status_code == 200
        assert publish.json()["status"] == "ACTIVE"

        definition = client.get(
            f"/api/v1/master-data/routing-revisions/{routing_id}/definition"
        )
        assert definition.status_code == 200
        assert [
            item["operation"]["sequence_no"]
            for item in definition.json()["operations"]
        ] == [30, 999]
        assert definition.json()["operations"][0]["resources"][0]["resource_id"] == resource_id

        effective = client.get(
            "/api/v1/master-data/routing-revisions/effective",
            params={"article_revision_id": article_revision_id},
        )
        assert effective.status_code == 200
        assert effective.json()["id"] == routing_id

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.routing_revision.publish"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == routing_id for item in audit.json())


def test_routing_rejects_resource_outside_operation_work_center() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(minutes=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _, revision_id = _article_revision(client, suffix, "c")
        area_id, work_center_id, _ = _core_resource(client, suffix, "B")
        _, _, foreign_resource_id = _core_resource(client, suffix, "C")
        routing_id = _routing(client, revision_id, 1, "d", valid_from)

        operation = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
            json={
                "source_operation_code": "020",
                "sequence_no": 20,
                "source_description": "Welding",
                "area_id": area_id,
                "work_center_id": work_center_id,
                "operation_kind": "PHYSICAL_PRODUCTION",
                "schedulable": True,
            },
        )
        assert operation.status_code == 201

        assignment = client.post(
            f"/api/v1/master-data/routing-operations/{operation.json()['id']}/resources",
            json={
                "resource_id": foreign_resource_id,
                "principal": True,
            },
        )
        assert assignment.status_code == 422
        assert assignment.json()["detail"] == (
            "resource does not belong to routing work center"
        )


def test_routing_is_immutable_after_publish_and_sequence_is_unique() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(minutes=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _, revision_id = _article_revision(client, suffix, "e")
        _, work_center_id, _ = _core_resource(client, suffix, "D")
        routing_id = _routing(client, revision_id, 1, "f", valid_from)

        payload = {
            "source_operation_code": "010",
            "sequence_no": 10,
            "source_description": "Cutting",
            "work_center_id": work_center_id,
            "operation_kind": "PHYSICAL_PRODUCTION",
            "schedulable": True,
        }
        operation = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
            json=payload,
        )
        assert operation.status_code == 201
        assert operation.json()["area_id"] is not None

        duplicate = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
            json={
                **payload,
                "source_operation_code": "011",
            },
        )
        assert duplicate.status_code == 409

        assert client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/publish"
        ).status_code == 200

        mutation = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_id}/operations",
            json={
                **payload,
                "sequence_no": 20,
            },
        )
        assert mutation.status_code == 422
        assert mutation.json()["detail"] == (
            "operations can only be added to a DRAFT routing revision"
        )


def test_routing_supersede_preserves_history() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    valid_from = datetime.now(timezone.utc) - timedelta(hours=1)

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        article_id, revision_1 = _article_revision(client, suffix, "g")

        revision_2_response = client.post(
            f"/api/v1/master-data/articles/{article_id}/revisions",
            json={
                "revision_label": "h",
                "source_fingerprint": "h" * 64,
            },
        )
        assert revision_2_response.status_code == 201
        revision_2 = revision_2_response.json()["id"]

        _, work_center_id, _ = _core_resource(client, suffix, "E")

        routing_1 = _routing(client, revision_1, 1, "1", valid_from)
        operation_1 = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_1}/operations",
            json={
                "source_operation_code": "010",
                "sequence_no": 10,
                "source_description": "Assembly V1",
                "work_center_id": work_center_id,
                "operation_kind": "PHYSICAL_PRODUCTION",
                "schedulable": True,
            },
        )
        assert operation_1.status_code == 201
        assert client.post(
            f"/api/v1/master-data/routing-revisions/{routing_1}/publish"
        ).status_code == 200

        routing_2 = _routing(client, revision_2, 1, "2", valid_from)
        operation_2 = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_2}/operations",
            json={
                "source_operation_code": "010",
                "sequence_no": 10,
                "source_description": "Assembly V2",
                "work_center_id": work_center_id,
                "operation_kind": "PHYSICAL_PRODUCTION",
                "schedulable": True,
            },
        )
        assert operation_2.status_code == 201

        effective_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        supersede = client.post(
            f"/api/v1/master-data/routing-revisions/{routing_1}/supersede",
            json={
                "replacement_routing_revision_id": routing_2,
                "effective_at": effective_at.isoformat(),
            },
        )
        assert supersede.status_code == 200
        assert supersede.json()["id"] == routing_2
        assert supersede.json()["status"] == "ACTIVE"

        old = client.get(
            "/api/v1/master-data/routing-revisions",
            params={"article_revision_id": revision_1},
        )
        assert old.status_code == 200
        assert old.json()[0]["status"] == "SUPERSEDED"
        assert old.json()[0]["valid_to"] is not None

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.routing_revision.supersede"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == routing_1 for item in audit.json())
