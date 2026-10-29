import os
from datetime import date
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

PASSWORD = "Mop-G2-Calendar-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-calendar-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G2 Calendar Administrator",
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


def _core_chain(
    client: TestClient,
    suffix: str,
    marker: str,
) -> tuple[str, str, str, str]:
    organization = client.post(
        "/api/v1/core/organizations",
        json={
            "code": f"CAL-ORG-{marker}-{suffix}",
            "name": f"Calendar Organization {marker}",
        },
    )
    assert organization.status_code == 201

    plant = client.post(
        "/api/v1/core/plants",
        json={
            "organization_id": organization.json()["id"],
            "code": f"CAL-PLANT-{marker}-{suffix}",
            "name": f"Calendar Plant {marker}",
        },
    )
    assert plant.status_code == 201

    area = client.post(
        "/api/v1/core/areas",
        json={
            "plant_id": plant.json()["id"],
            "code": f"CAL-AREA-{marker}-{suffix}",
            "name": f"Calendar Area {marker}",
        },
    )
    assert area.status_code == 201

    work_center = client.post(
        "/api/v1/core/work-centers",
        json={
            "area_id": area.json()["id"],
            "code": f"CAL-WC-{marker}-{suffix}",
            "name": f"Calendar Work Center {marker}",
        },
    )
    assert work_center.status_code == 201

    resource = client.post(
        "/api/v1/core/resources",
        json={
            "work_center_id": work_center.json()["id"],
            "code": f"CAL-RES-{marker}-{suffix}",
            "name": f"Calendar Resource {marker}",
            "resource_type": "machine",
        },
    )
    assert resource.status_code == 201

    return (
        plant.json()["id"],
        area.json()["id"],
        work_center.json()["id"],
        resource.json()["id"],
    )


def _calendar(
    client: TestClient,
    *,
    code: str,
    revision_no: int,
    target_field: str,
    target_id: str,
    valid_from: str = "2026-11-01",
) -> str:
    response = client.post(
        "/api/v1/master-data/calendars",
        json={
            "code": code,
            "name": f"{code} revision {revision_no}",
            "revision_no": revision_no,
            "timezone": "America/Argentina/Cordoba",
            target_field: target_id,
            "valid_from": valid_from,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    return response.json()["id"]


def _window(
    client: TestClient,
    calendar_id: str,
    weekday: int,
    start_minute: int,
    end_minute: int,
    *,
    capacity_factor: str = "1.00000000",
) -> str:
    response = client.post(
        f"/api/v1/master-data/calendars/{calendar_id}/weekly-windows",
        json={
            "weekday": weekday,
            "start_minute": start_minute,
            "end_minute": end_minute,
            "capacity_factor": capacity_factor,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_plant_calendar_resolves_through_resource_and_preserves_lunch_gap() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plant_id, _, _, resource_id = _core_chain(client, suffix, "A")

        calendar_id = _calendar(
            client,
            code=f"FAIC-BASE-{suffix}",
            revision_no=1,
            target_field="plant_id",
            target_id=plant_id,
        )
        morning_id = _window(client, calendar_id, 0, 420, 720)
        afternoon_id = _window(client, calendar_id, 0, 750, 960)

        publish = client.post(
            f"/api/v1/master-data/calendars/{calendar_id}/publish"
        )
        assert publish.status_code == 200

        morning = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-02T10:00:00-03:00",
            },
        )
        assert morning.status_code == 200
        assert morning.json()["available"] is True
        assert morning.json()["weekly_window_id"] == morning_id
        assert morning.json()["target_scope"] == "plant"

        lunch = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-02T12:15:00-03:00",
            },
        )
        assert lunch.status_code == 200
        assert lunch.json()["available"] is False
        assert lunch.json()["source"] == "NO_WINDOW"

        afternoon = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-02T12:45:00-03:00",
            },
        )
        assert afternoon.status_code == 200
        assert afternoon.json()["weekly_window_id"] == afternoon_id


def test_resource_calendar_overrides_plant_and_exception_precedes_weekly_window() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plant_id, _, _, resource_id = _core_chain(client, suffix, "B")

        plant_calendar = _calendar(
            client,
            code=f"PLANT-{suffix}",
            revision_no=1,
            target_field="plant_id",
            target_id=plant_id,
        )
        _window(client, plant_calendar, 0, 420, 960)
        assert client.post(
            f"/api/v1/master-data/calendars/{plant_calendar}/publish"
        ).status_code == 200

        resource_calendar = _calendar(
            client,
            code=f"RESOURCE-{suffix}",
            revision_no=1,
            target_field="resource_id",
            target_id=resource_id,
        )
        _window(
            client,
            resource_calendar,
            0,
            420,
            960,
            capacity_factor="0.80000000",
        )
        closed = client.post(
            f"/api/v1/master-data/calendars/{resource_calendar}/exceptions",
            json={
                "local_date": "2026-11-02",
                "exception_kind": "CLOSED",
                "start_minute": 600,
                "end_minute": 660,
                "reason": "Planned maintenance",
            },
        )
        assert closed.status_code == 201

        extra = client.post(
            f"/api/v1/master-data/calendars/{resource_calendar}/exceptions",
            json={
                "local_date": "2026-11-07",
                "exception_kind": "AVAILABLE_OVERRIDE",
                "start_minute": 480,
                "end_minute": 720,
                "capacity_factor": "0.50000000",
                "reason": "Saturday recovery shift",
            },
        )
        assert extra.status_code == 201

        assert client.post(
            f"/api/v1/master-data/calendars/{resource_calendar}/publish"
        ).status_code == 200

        maintenance = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-02T10:30:00-03:00",
            },
        )
        assert maintenance.status_code == 200
        assert maintenance.json()["available"] is False
        assert maintenance.json()["source"] == "EXCEPTION_CLOSED"
        assert maintenance.json()["target_scope"] == "resource"

        after_maintenance = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-02T11:30:00-03:00",
            },
        )
        assert after_maintenance.status_code == 200
        assert after_maintenance.json()["available"] is True
        assert after_maintenance.json()["capacity_factor"] == "0.80000000"

        saturday = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-07T09:00:00-03:00",
            },
        )
        assert saturday.status_code == 200
        assert saturday.json()["available"] is True
        assert saturday.json()["source"] == "EXCEPTION_OVERRIDE"
        assert saturday.json()["capacity_factor"] == "0.50000000"


def test_calendar_rejects_overlaps_and_is_immutable_after_publish() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plant_id, _, _, _ = _core_chain(client, suffix, "C")
        calendar_id = _calendar(
            client,
            code=f"OVERLAP-{suffix}",
            revision_no=1,
            target_field="plant_id",
            target_id=plant_id,
        )
        _window(client, calendar_id, 0, 420, 720)

        overlap = client.post(
            f"/api/v1/master-data/calendars/{calendar_id}/weekly-windows",
            json={
                "weekday": 0,
                "start_minute": 700,
                "end_minute": 800,
            },
        )
        assert overlap.status_code == 422
        assert overlap.json()["detail"] == (
            "calendar weekly windows cannot overlap"
        )

        assert client.post(
            f"/api/v1/master-data/calendars/{calendar_id}/publish"
        ).status_code == 200

        mutation = client.post(
            f"/api/v1/master-data/calendars/{calendar_id}/weekly-windows",
            json={
                "weekday": 1,
                "start_minute": 420,
                "end_minute": 720,
            },
        )
        assert mutation.status_code == 422
        assert mutation.json()["detail"] == (
            "weekly windows can only be added to a DRAFT calendar"
        )


def test_calendar_supersede_preserves_history_and_changes_effective_revision() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plant_id, _, _, resource_id = _core_chain(client, suffix, "D")
        code = f"REV-CAL-{suffix}"

        first = _calendar(
            client,
            code=code,
            revision_no=1,
            target_field="plant_id",
            target_id=plant_id,
        )
        _window(client, first, 0, 420, 960, capacity_factor="1.00000000")
        assert client.post(
            f"/api/v1/master-data/calendars/{first}/publish"
        ).status_code == 200

        second = _calendar(
            client,
            code=code,
            revision_no=2,
            target_field="plant_id",
            target_id=plant_id,
        )
        _window(client, second, 0, 420, 960, capacity_factor="0.90000000")

        supersede = client.post(
            f"/api/v1/master-data/calendars/{first}/supersede",
            json={
                "replacement_calendar_id": second,
                "effective_on": "2026-12-01",
            },
        )
        assert supersede.status_code == 200
        assert supersede.json()["id"] == second
        assert supersede.json()["status"] == "ACTIVE"
        assert supersede.json()["valid_from"] == "2026-12-01"

        before = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-11-30T10:00:00-03:00",
            },
        )
        assert before.status_code == 200
        assert before.json()["calendar_id"] == first
        assert before.json()["capacity_factor"] == "1.00000000"

        after = client.get(
            "/api/v1/master-data/calendars/resolve",
            params={
                "resource_id": resource_id,
                "at": "2026-12-07T10:00:00-03:00",
            },
        )
        assert after.status_code == 200
        assert after.json()["calendar_id"] == second
        assert after.json()["capacity_factor"] == "0.90000000"

        historical = client.get(
            "/api/v1/master-data/calendars",
            params={"code": code},
        )
        assert historical.status_code == 200
        by_revision = {
            item["revision_no"]: item for item in historical.json()
        }
        assert by_revision[1]["status"] == "SUPERSEDED"
        assert by_revision[1]["valid_to"] == "2026-12-01"
        assert by_revision[2]["status"] == "ACTIVE"

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.calendar.supersede"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == first for item in audit.json())
