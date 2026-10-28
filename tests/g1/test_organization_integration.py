import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mop.application import create_app
from mop.config import Settings
from mop.persistence.database import DatabaseManager


pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_full_organization_hierarchy_through_api() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        organization = client.post(
            "/api/v1/core/organizations",
            json={"code": f"ORG-{suffix}", "name": "FAIC Test Organization"},
        )
        assert organization.status_code == 201
        organization_id = organization.json()["id"]

        duplicate_organization = client.post(
            "/api/v1/core/organizations",
            json={"code": f"org-{suffix}", "name": "Duplicate"},
        )
        assert duplicate_organization.status_code == 409

        plant = client.post(
            "/api/v1/core/plants",
            json={
                "organization_id": organization_id,
                "code": "ROS",
                "name": "Rosario Plant",
            },
        )
        assert plant.status_code == 201
        plant_id = plant.json()["id"]

        area = client.post(
            "/api/v1/core/areas",
            json={"plant_id": plant_id, "code": "SOLD", "name": "Soldadura"},
        )
        assert area.status_code == 201
        area_id = area.json()["id"]

        work_center = client.post(
            "/api/v1/core/work-centers",
            json={"area_id": area_id, "code": "CELL-R1", "name": "Celda Robot 1"},
        )
        assert work_center.status_code == 201
        work_center_id = work_center.json()["id"]

        resource = client.post(
            "/api/v1/core/resources",
            json={
                "work_center_id": work_center_id,
                "code": "R1",
                "name": "Robot 1",
                "resource_type": "robot",
            },
        )
        assert resource.status_code == 201
        assert resource.json()["resource_type"] == "robot"

        plants = client.get(
            "/api/v1/core/plants",
            params={"organization_id": organization_id},
        )
        assert plants.status_code == 200
        assert [item["code"] for item in plants.json()] == ["ROS"]

        areas = client.get("/api/v1/core/areas", params={"plant_id": plant_id})
        assert areas.status_code == 200
        assert [item["code"] for item in areas.json()] == ["SOLD"]

        work_centers = client.get(
            "/api/v1/core/work-centers",
            params={"area_id": area_id},
        )
        assert work_centers.status_code == 200
        assert [item["code"] for item in work_centers.json()] == ["CELL-R1"]

        resources = client.get(
            "/api/v1/core/resources",
            params={"work_center_id": work_center_id},
        )
        assert resources.status_code == 200
        assert [item["code"] for item in resources.json()] == ["R1"]


def test_missing_parent_is_rejected() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)

    with TestClient(create_app(settings, database=database)) as client:
        response = client.post(
            "/api/v1/core/plants",
            json={
                "organization_id": str(uuid4()),
                "code": "ORPHAN",
                "name": "Invalid Plant",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "organization not found"
