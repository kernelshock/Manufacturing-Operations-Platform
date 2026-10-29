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

PASSWORD = "Mop-G2-Supplier-2026!"


def _login_admin(client: TestClient, database: DatabaseManager, suffix: str) -> None:
    username = f"g2-supplier-admin-{suffix}".lower()
    with database.session() as session:
        identity = IdentityService(session)
        user = identity.create_user(
            UserCreate(
                username=username,
                display_name="G2 Supplier Administrator",
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


def test_supplier_identity_source_mappings_and_audit() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        supplier = client.post(
            "/api/v1/master-data/suppliers",
            json={
                "code": f"SUP-{suffix}",
                "legal_name": "Synthetic Supplier S.A.",
                "trade_name": "Synthetic Supplier",
                "supply_category": "PRODUCT",
            },
        )
        assert supplier.status_code == 201
        supplier_id = supplier.json()["id"]

        prolowin = client.post(
            "/api/v1/master-data/supplier-source-mappings",
            json={
                "supplier_id": supplier_id,
                "external_system": "PROLOWIN",
                "external_code": f"P-{suffix}",
                "source_name": "Synthetic Supplier SA",
                "source_category_raw": "INSUMOS",
                "mapping_status": "MAPPED",
            },
        )
        assert prolowin.status_code == 201
        assert prolowin.json()["approved_by"] is not None

        crm = client.post(
            "/api/v1/master-data/supplier-source-mappings",
            json={
                "supplier_id": supplier_id,
                "external_system": "CRM",
                "external_code": f"C-{suffix}",
                "source_name": "Synthetic Supplier",
                "mapping_status": "MAPPED",
            },
        )
        assert crm.status_code == 201

        duplicate_source = client.post(
            "/api/v1/master-data/supplier-source-mappings",
            json={
                "supplier_id": supplier_id,
                "external_system": "PROLOWIN",
                "external_code": f"P-{suffix}",
                "mapping_status": "MAPPED",
            },
        )
        assert duplicate_source.status_code == 409

        mappings = client.get(
            "/api/v1/master-data/supplier-source-mappings",
            params={"mapping_status": "MAPPED"},
        )
        assert mappings.status_code == 200
        mapped_systems = {
            item["external_system"]
            for item in mappings.json()
            if item["supplier_id"] == supplier_id
        }
        assert mapped_systems == {"PROLOWIN", "CRM"}

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.supplier.create"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == supplier_id for item in audit.json())


def test_review_required_source_can_exist_before_consolidation() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        mapping = client.post(
            "/api/v1/master-data/supplier-source-mappings",
            json={
                "external_system": "IMPORT",
                "external_code": f"UNRESOLVED-{suffix}",
                "source_name": "Possible Duplicate Supplier",
                "source_category_raw": "SERVICIO",
                "mapping_status": "REVIEW_REQUIRED",
            },
        )
        assert mapping.status_code == 201
        assert mapping.json()["supplier_id"] is None
        assert mapping.json()["approved_at"] is None


def test_supplier_article_captures_lead_time_moq_and_order_uom() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()

    with TestClient(create_app(settings, database=database)) as client:
        _login_admin(client, database, suffix)

        supplier = client.post(
            "/api/v1/master-data/suppliers",
            json={
                "code": f"MAT-{suffix}",
                "legal_name": "Material Supplier S.A.",
                "supply_category": "PRODUCT",
            },
        )
        assert supplier.status_code == 201

        uom = client.post(
            "/api/v1/master-data/uoms",
            json={
                "code": f"ROLL-{suffix}",
                "dimension": "OTHER",
                "canonical": True,
                "active": True,
            },
        )
        assert uom.status_code == 201

        article = client.post(
            "/api/v1/master-data/articles",
            json={
                "external_system": "SYNTHETIC",
                "external_code": f"FABRIC-{suffix}",
                "canonical_description": "Synthetic upholstery fabric",
                "article_kind": "PURCHASED",
            },
        )
        assert article.status_code == 201

        sourcing = client.post(
            "/api/v1/master-data/supplier-articles",
            json={
                "supplier_id": supplier.json()["id"],
                "article_id": article.json()["id"],
                "supplier_article_code": f"SUP-FAB-{suffix}",
                "preferred": True,
                "lead_time_days": 21,
                "minimum_order_quantity": "50.00000000",
                "order_uom_id": uom.json()["id"],
            },
        )
        assert sourcing.status_code == 201
        assert sourcing.json()["lead_time_days"] == 21
        assert sourcing.json()["minimum_order_quantity"] == "50.00000000"

        listed = client.get(
            "/api/v1/master-data/supplier-articles",
            params={"supplier_id": supplier.json()["id"], "active": True},
        )
        assert listed.status_code == 200
        assert any(item["id"] == sourcing.json()["id"] for item in listed.json())

        audit = client.get(
            "/api/v1/audit/events",
            params={"action": "masterdata.supplier_article.create"},
        )
        assert audit.status_code == 200
        assert any(item["object_id"] == sourcing.json()["id"] for item in audit.json())
