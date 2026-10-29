import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from mop.application import create_app
from mop.config import Settings
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, UserCreate
from mop.iam.service import IdentityService
from mop.master_data.models import Article
from mop.persistence.database import DatabaseManager
from mop.prolowin.models import (
    ImportBatch,
    ProlowinDirectRelation,
    ProlowinStructureRow,
)


pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)

PASSWORD = "Mop-G2-Prolowin-Integration-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-prolowin-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G2 Prolowin Administrator",
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


def _create_count_uom_mapping(client: TestClient, suffix: str) -> None:
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

    alias = client.post(
        "/api/v1/master-data/uom-aliases",
        json={
            "source_system": "PROLOWIN",
            "raw_value": f"UNID-{suffix}",
            "uom_id": uom.json()["id"],
            "mapping_status": "MAPPED",
            "conversion_factor": "1",
        },
    )
    assert alias.status_code == 201


def _complete_payload(
    suffix: str,
    *,
    root: str = "X-6111",
    source_sha: str,
    uom_raw: str,
    material_quantity: str = "6.0000",
) -> dict:
    return {
        "schema_version": "1.0.0",
        "source_system": "PROLOWIN",
        "report_type": "COMPLETE_ARTICLE_STRUCTURE",
        "source": {
            "filename": f"{root}-{suffix}.json",
            "sha256": source_sha,
            "exported_at": "2026-10-28T09:46:00-03:00",
            "parser_version": "integration-1",
        },
        "root_article": {
            "code": f"{root}-{suffix}",
            "description": "Synthetic root",
            "quantity": "1.0000",
            "uom_raw": uom_raw,
        },
        "rows": [
            {
                "row_no": 1,
                "article_code": f"{root}-{suffix}",
                "operation_code": "FIN",
                "description_raw": "Synthetic root",
                "quantity": "1.0000",
                "uom_raw": uom_raw,
            },
            {
                "row_no": 2,
                "article_code": f"A-621-{suffix}",
                "operation_code": "030",
                "description_raw": "Synthetic backrest",
                "quantity": "2.0000",
                "uom_raw": uom_raw,
            },
            {
                "row_no": 3,
                "article_code": f"A-621-{suffix}",
                "operation_code": "FIN",
                "description_raw": "Synthetic backrest",
                "quantity": "2.0000",
                "uom_raw": uom_raw,
            },
            {
                "row_no": 4,
                "article_code": f"14027-{suffix}",
                "operation_code": "FIN",
                "description_raw": "ALAMBRE CHICO RESPALDO MB F10",
                "quantity": material_quantity,
                "uom_raw": uom_raw,
            },
        ],
    }


def _direct_payload(
    suffix: str,
    *,
    source_sha: str,
    uom_raw: str,
) -> dict:
    return {
        "schema_version": "1.0.0",
        "source_system": "PROLOWIN",
        "report_type": "DIRECT_ARTICLE_STRUCTURE",
        "source": {
            "filename": f"direct-{suffix}.json",
            "sha256": source_sha,
            "exported_at": "2026-10-28T09:46:00-03:00",
            "parser_version": "integration-direct-1",
        },
        "root_article_code": f"X-6111-{suffix}",
        "relations": [
            {
                "row_no": 1,
                "sequence_no": 10,
                "parent_article_code": f"X-6111-{suffix}",
                "parent_description_raw": "Synthetic root",
                "child_article_code": f"A-621-{suffix}",
                "child_description_raw": "Synthetic backrest",
                "quantity": "2.0000",
                "uom_raw": uom_raw,
            },
            {
                "row_no": 2,
                "sequence_no": 10,
                "parent_article_code": f"A-621-{suffix}",
                "parent_description_raw": "Synthetic backrest",
                "child_article_code": f"14027-{suffix}",
                "child_description_raw": "ALAMBRE CHICO RESPALDO MB F10",
                "quantity": "3.0000",
                "uom_raw": uom_raw,
            },
        ],
    }


def test_complete_report_normalizes_fin_and_operation_rows_idempotently() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    uom_raw = f"UNID-{suffix}"
    source_sha = uuid4().hex + uuid4().hex

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _create_count_uom_mapping(client, suffix)

        payload = _complete_payload(
            suffix,
            source_sha=source_sha,
            uom_raw=uom_raw,
        )
        first = client.post(
            "/api/v1/master-data/prolowin/complete-structures/import",
            json=payload,
        )
        assert first.status_code == 201
        assert first.json()["batch"]["status"] == "APPLIED"
        assert first.json()["flat_requirements"] == 3
        assert first.json()["operation_states"] == 1
        assert first.json()["idempotent_replay"] is False

        projection = client.get(
            f"/api/v1/master-data/prolowin/import-batches/{first.json()['batch']['id']}/projection"
        )
        assert projection.status_code == 200
        flat = {
            item["article_code"]: item
            for item in projection.json()["flat_requirements"]
        }
        assert flat[f"X-6111-{suffix}"]["is_root"] is True
        assert flat[f"14027-{suffix}"]["quantity"] == "6.00000000"
        assert len(projection.json()["operation_states"]) == 1
        assert projection.json()["operation_states"][0]["source_operation_code"] == "030"

        replay = client.post(
            "/api/v1/master-data/prolowin/complete-structures/import",
            json=payload,
        )
        assert replay.status_code == 201
        assert replay.json()["batch"]["id"] == first.json()["batch"]["id"]
        assert replay.json()["idempotent_replay"] is True

        with database.session() as session:
            articles = session.scalars(
                select(Article).where(
                    Article.external_system == "PROLOWIN",
                    Article.external_code.in_(
                        (
                            f"X-6111-{suffix}",
                            f"A-621-{suffix}",
                            f"14027-{suffix}",
                        )
                    ),
                )
            ).all()
            assert len(articles) == 3


def test_fin_anomaly_is_quarantined_and_does_not_apply_articles() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    uom_raw = f"UNID-BAD-{suffix}"
    source_sha = uuid4().hex + uuid4().hex

    payload = {
        "schema_version": "1.0.0",
        "source_system": "PROLOWIN",
        "report_type": "COMPLETE_ARTICLE_STRUCTURE",
        "source": {
            "filename": f"bad-{suffix}.json",
            "sha256": source_sha,
            "parser_version": "integration-bad-1",
        },
        "root_article": {
            "code": f"X-BAD-{suffix}",
            "quantity": "1.0000",
            "uom_raw": uom_raw,
        },
        "rows": [
            {
                "row_no": 1,
                "article_code": f"X-BAD-{suffix}",
                "operation_code": "FIN",
                "description_raw": "Bad root",
                "quantity": "1.0000",
                "uom_raw": uom_raw,
            },
            {
                "row_no": 2,
                "article_code": f"COMP-{suffix}",
                "operation_code": "030",
                "description_raw": "Missing FIN",
                "quantity": "2.0000",
                "uom_raw": uom_raw,
            },
        ],
    }

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        response = client.post(
            "/api/v1/master-data/prolowin/complete-structures/import",
            json=payload,
        )
        assert response.status_code == 201
        assert response.json()["batch"]["status"] == "REJECTED"
        assert response.json()["snapshot_id"] is None
        assert any(
            issue["rule_code"] == "PLW_FIN_MISSING"
            and issue["severity"] == "BLOCKER"
            for issue in response.json()["data_quality_issues"]
        )

        with database.session() as session:
            article = session.scalar(
                select(Article).where(
                    Article.external_system == "PROLOWIN",
                    Article.external_code == f"X-BAD-{suffix}",
                )
            )
            assert article is None


def test_direct_structure_builds_candidate_boms_and_reconciles_x6111_trace() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    uom_raw = f"UNID-{suffix}"
    complete_sha = uuid4().hex + uuid4().hex
    direct_sha = uuid4().hex + uuid4().hex

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _create_count_uom_mapping(client, suffix)

        complete = client.post(
            "/api/v1/master-data/prolowin/complete-structures/import",
            json=_complete_payload(
                suffix,
                source_sha=complete_sha,
                uom_raw=uom_raw,
            ),
        )
        assert complete.status_code == 201
        assert complete.json()["batch"]["status"] == "APPLIED"

        direct = client.post(
            "/api/v1/master-data/prolowin/direct-structures/import",
            json=_direct_payload(
                suffix,
                source_sha=direct_sha,
                uom_raw=uom_raw,
            ),
        )
        assert direct.status_code == 201
        assert direct.json()["batch"]["status"] == "APPLIED"
        assert len(direct.json()["candidate_article_revision_ids"]) == 2
        assert len(direct.json()["candidate_bom_revision_ids"]) == 2

        root_code = f"X-6111-{suffix}"
        with database.session() as session:
            root_article = session.scalar(
                select(Article).where(
                    Article.external_system == "PROLOWIN",
                    Article.external_code == root_code,
                )
            )
            assert root_article is not None

        candidate_ids = direct.json()["candidate_bom_revision_ids"]
        root_bom_id = None
        for candidate_id in candidate_ids:
            # Candidate root is the one whose projection contains A-621.
            # Reconciliation itself will reject a non-root selection.
            trial = client.post(
                "/api/v1/master-data/prolowin/reconciliations",
                json={
                    "complete_batch_id": complete.json()["batch"]["id"],
                    "bom_revision_id": candidate_id,
                    "tolerance": "0",
                },
            )
            assert trial.status_code == 201
            if trial.json()["run"]["status"] != "BLOCKED":
                root_bom_id = candidate_id
                reconciliation = trial
                break

        assert root_bom_id is not None
        assert reconciliation.json()["run"]["status"] == "MATCH_WITH_WARNINGS"
        assert reconciliation.json()["run"]["mismatching_items"] == 0
        by_code = {
            item["article_code"]: item
            for item in reconciliation.json()["items"]
        }
        trace = by_code[f"14027-{suffix}"]
        assert Decimal(trace["source_fin_quantity"]) == Decimal("6")
        assert Decimal(trace["calculated_quantity"]) == Decimal("6")
        assert trace["result"] == "MATCH"


def test_direct_cycle_is_blocked_before_candidate_bom_creation() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    source_sha = uuid4().hex + uuid4().hex
    uom_raw = f"UNID-CYCLE-{suffix}"

    payload = {
        "schema_version": "1.0.0",
        "source_system": "PROLOWIN",
        "report_type": "DIRECT_ARTICLE_STRUCTURE",
        "source": {
            "filename": f"cycle-{suffix}.json",
            "sha256": source_sha,
            "parser_version": "integration-cycle-1",
        },
        "root_article_code": f"A-{suffix}",
        "relations": [
            {
                "row_no": 1,
                "parent_article_code": f"A-{suffix}",
                "child_article_code": f"B-{suffix}",
                "quantity": "1.0000",
                "uom_raw": uom_raw,
            },
            {
                "row_no": 2,
                "parent_article_code": f"B-{suffix}",
                "child_article_code": f"A-{suffix}",
                "quantity": "1.0000",
                "uom_raw": uom_raw,
            },
        ],
    }

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        response = client.post(
            "/api/v1/master-data/prolowin/direct-structures/import",
            json=payload,
        )
        assert response.status_code == 201
        assert response.json()["batch"]["status"] == "REJECTED"
        assert response.json()["candidate_bom_revision_ids"] == []
        assert any(
            issue["rule_code"] == "PLW_BOM_CYCLE"
            and issue["severity"] == "BLOCKER"
            for issue in response.json()["data_quality_issues"]
        )


def test_source_staging_rows_are_append_only_in_postgresql() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    uom_raw = f"UNID-{suffix}"
    source_sha = uuid4().hex + uuid4().hex

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)
        _create_count_uom_mapping(client, suffix)
        complete = client.post(
            "/api/v1/master-data/prolowin/complete-structures/import",
            json=_complete_payload(
                suffix,
                source_sha=source_sha,
                uom_raw=uom_raw,
            ),
        )
        assert complete.status_code == 201
        batch_id = complete.json()["batch"]["id"]

        with database.session() as session:
            row = session.scalar(
                select(ProlowinStructureRow).where(
                    ProlowinStructureRow.batch_id == batch_id
                )
            )
            assert row is not None
            with pytest.raises(Exception):
                session.execute(
                    text(
                        "UPDATE int_prolowin_structure_row "
                        "SET description_raw='tampered' WHERE id=:id"
                    ),
                    {"id": row.id},
                )
                session.commit()
            session.rollback()
