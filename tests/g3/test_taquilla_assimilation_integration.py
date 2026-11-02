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

ADMIN_PASSWORD = "Mop-G3-Assimilation-2026!"


def _login_admin(client, database, suffix):
    username = f"g3-assim-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G3 Assimilation Administrator",
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


def _plan(client, suffix):
    response = client.post(
        "/api/v1/demand/plans",
        json={"plan_number": f"ASSIM-{suffix}"},
    )
    assert response.status_code == 201
    return response.json()


def _article(client, suffix, code):
    response = client.post(
        "/api/v1/master-data/articles",
        json={
            "external_system": "TAQUILLA",
            "external_code": f"{code}-{suffix}",
            "canonical_description": f"Product {code}",
            "article_kind": "FINISHED_PRODUCT",
        },
    )
    assert response.status_code == 201
    return response.json()


def _simple_payload(plan_id, suffix, article_code, *, sha=None, taquilla_code=None):
    source_sha = sha or (uuid4().hex + uuid4().hex)
    return {
        "schema_version": "1.0.0",
        "source_system": "TAQUILLA",
        "parser_version": "integration-1",
        "mapping_version": "mapping-1",
        "plan_id": plan_id,
        "taquilla_code": taquilla_code or f"26-{suffix}",
        "sequence_no": 1,
        "vehicle_topology": "SIMPLE",
        "documents": [
            {
                "source_document_key": "DOC-1",
                "filename": f"taquilla-{suffix}.pdf",
                "sha256": source_sha,
            }
        ],
        "lines": [
            {
                "source_document_key": "DOC-1",
                "source_line_key": "L-1",
                "article_code": article_code,
                "requested_quantity": "12.00000000",
                "deck_position": "SINGLE",
            }
        ],
    }


def test_simple_one_document_import_applies_and_replay_is_idempotent():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)
        article = _article(client, suffix, "MOON")
        payload = _simple_payload(
            plan["id"],
            suffix,
            article["external_code"],
        )

        first = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=payload,
        )
        assert first.status_code == 201
        body = first.json()
        assert body["batch"]["status"] == "APPLIED"
        assert body["batch"]["accepted_lines"] == 1
        assert body["batch"]["rejected_lines"] == 0
        assert body["issues"] == []
        assert body["target_taquilla_id"] is not None
        assert body["idempotent_replay"] is False

        target_id = body["target_taquilla_id"]
        lines = client.get(
            f"/api/v1/demand/taquillas/{target_id}/products"
        )
        assert lines.status_code == 200
        assert len(lines.json()) == 1
        assert lines.json()[0]["article_id"] == article["id"]
        assert lines.json()[0]["source_line_key"] == "L-1"
        assert lines.json()[0]["source_document_key"] == "DOC-1"
        assert lines.json()[0]["deck_position"] == "SINGLE"

        replay = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=payload,
        )
        assert replay.status_code == 201
        assert replay.json()["batch"]["id"] == body["batch"]["id"]
        assert replay.json()["target_taquilla_id"] == target_id
        assert replay.json()["idempotent_replay"] is True


def test_double_deck_two_documents_applies_without_document_floor_inference():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)
        upper = _article(client, suffix, "UP")
        lower = _article(client, suffix, "LOW")

        payload = {
            "schema_version": "1.0.0",
            "source_system": "TAQUILLA",
            "parser_version": "integration-1",
            "mapping_version": "mapping-1",
            "plan_id": plan["id"],
            "taquilla_code": f"DD-{suffix}",
            "sequence_no": 1,
            "vehicle_topology": "DOUBLE_DECK",
            "documents": [
                {
                    "source_document_key": "DOC-A",
                    "filename": "first.pdf",
                    "sha256": uuid4().hex + uuid4().hex,
                },
                {
                    "source_document_key": "DOC-B",
                    "filename": "second.pdf",
                    "sha256": uuid4().hex + uuid4().hex,
                },
            ],
            "lines": [
                {
                    "source_document_key": "DOC-B",
                    "source_line_key": "UP-1",
                    "article_code": upper["external_code"],
                    "requested_quantity": "10",
                    "deck_position": "UPPER",
                },
                {
                    "source_document_key": "DOC-A",
                    "source_line_key": "LOW-1",
                    "article_code": lower["external_code"],
                    "requested_quantity": "12",
                    "deck_position": "LOWER",
                },
            ],
        }

        response = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=payload,
        )
        assert response.status_code == 201
        assert response.json()["batch"]["status"] == "APPLIED"

        target_id = response.json()["target_taquilla_id"]
        lines = client.get(
            f"/api/v1/demand/taquillas/{target_id}/products"
        ).json()
        assert [line["deck_position"] for line in lines] == ["UPPER", "LOWER"]
        assert lines[0]["source_document_key"] == "DOC-B"
        assert lines[1]["source_document_key"] == "DOC-A"


def test_double_deck_single_document_can_explicitly_contain_both_decks():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)
        upper = _article(client, suffix, "ONE-UP")
        lower = _article(client, suffix, "ONE-LOW")

        payload = {
            "schema_version": "1.0.0",
            "source_system": "TAQUILLA",
            "parser_version": "integration-1",
            "mapping_version": "mapping-1",
            "plan_id": plan["id"],
            "taquilla_code": f"ONE-{suffix}",
            "sequence_no": 1,
            "vehicle_topology": "DOUBLE_DECK",
            "documents": [
                {
                    "source_document_key": "UNIFIED",
                    "filename": "unified.pdf",
                    "sha256": uuid4().hex + uuid4().hex,
                }
            ],
            "lines": [
                {
                    "source_document_key": "UNIFIED",
                    "source_line_key": "U",
                    "article_code": upper["external_code"],
                    "requested_quantity": "8",
                    "deck_position": "UPPER",
                },
                {
                    "source_document_key": "UNIFIED",
                    "source_line_key": "L",
                    "article_code": lower["external_code"],
                    "requested_quantity": "9",
                    "deck_position": "LOWER",
                },
            ],
        }

        response = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=payload,
        )
        assert response.status_code == 201
        assert response.json()["batch"]["status"] == "APPLIED"


def test_unmapped_product_is_staged_for_review_and_creates_no_taquilla():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)
        payload = _simple_payload(
            plan["id"],
            suffix,
            f"MISSING-{suffix}",
        )

        response = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=payload,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["batch"]["status"] == "REVIEW_REQUIRED"
        assert body["batch"]["accepted_lines"] == 0
        assert body["batch"]["rejected_lines"] == 1
        assert body["target_taquilla_id"] is None
        assert any(
            issue["rule_code"] == "TAQ_PRODUCT_UNMAPPED"
            and issue["severity"] == "BLOCKER"
            for issue in body["issues"]
        )

        taquillas = client.get(
            f"/api/v1/demand/plans/{plan['id']}/taquillas"
        )
        assert taquillas.status_code == 200
        assert taquillas.json() == []


def test_distinct_source_cannot_recreate_existing_taquilla_or_reuse_document():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)
        article = _article(client, suffix, "DUP")
        first_sha = uuid4().hex + uuid4().hex
        first_payload = _simple_payload(
            plan["id"],
            suffix,
            article["external_code"],
            sha=first_sha,
            taquilla_code=f"DUP-{suffix}",
        )
        first = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=first_payload,
        )
        assert first.status_code == 201
        assert first.json()["batch"]["status"] == "APPLIED"

        second_payload = _simple_payload(
            plan["id"],
            suffix + "X",
            article["external_code"],
            sha=first_sha,
            taquilla_code=f"DUP-{suffix}",
        )
        second_payload["sequence_no"] = 2
        second = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=second_payload,
        )
        assert second.status_code == 201
        assert second.json()["batch"]["status"] == "REVIEW_REQUIRED"
        codes = {item["rule_code"] for item in second.json()["issues"]}
        assert "TAQ_SOURCE_DOCUMENT_REUSED" in codes
        assert (
            "TAQ_DUPLICATE_CODE" in codes
            or "TAQ_DUPLICATE_ASSIMILATION_IDENTITY" in codes
        )


def test_competing_review_batches_with_same_identity_are_blocked():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)

        first = _simple_payload(
            plan["id"],
            suffix,
            f"MISSING-A-{suffix}",
            taquilla_code=f"PENDING-{suffix}",
        )
        first_response = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=first,
        )
        assert first_response.status_code == 201
        assert first_response.json()["batch"]["status"] == "REVIEW_REQUIRED"

        second = _simple_payload(
            plan["id"],
            suffix + "B",
            f"MISSING-B-{suffix}",
            taquilla_code=f"PENDING-{suffix}",
        )
        second_response = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=second,
        )
        assert second_response.status_code == 201
        assert second_response.json()["batch"]["status"] == "REVIEW_REQUIRED"
        assert any(
            issue["rule_code"] == "TAQ_DUPLICATE_ASSIMILATION_IDENTITY"
            for issue in second_response.json()["issues"]
        )


def test_assimilation_audit_and_issue_listing_are_available():
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        plan = _plan(client, suffix)
        payload = _simple_payload(
            plan["id"],
            suffix,
            f"UNKNOWN-{suffix}",
        )
        result = client.post(
            "/api/v1/demand/assimilation/taquillas/import",
            json=payload,
        )
        assert result.status_code == 201
        batch_id = result.json()["batch"]["id"]

        issues = client.get(
            f"/api/v1/demand/assimilation/batches/{batch_id}/issues"
        )
        assert issues.status_code == 200
        assert len(issues.json()) >= 1

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "demand.taquilla.assimilation.import"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == batch_id for item in audit.json())
