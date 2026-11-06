"""G6.2 API acceptance: authentication, segregated RBAC, audit and balances."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mop.application import create_app
from mop.config import Settings
from mop.core.models import Organization, Plant
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.master_data.models import Article, UnitOfMeasure
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires disposable PostgreSQL",
)

PASSWORD = "G6-Test-Rbac-Temporary-2026!"


def test_materials_api_permissions_and_atomic_audit():
    settings=Settings(environment="test",_env_file=None)
    database=DatabaseManager(settings.database_url)
    suffix=uuid4().hex[:8].upper()
    with database.session() as session:
        org=Organization(code=f"G62API-O-{suffix}",name="G6 Test")
        session.add(org)
        session.flush()
        plant=Plant(organization_id=org.id,code=f"G62API-P-{suffix}",name="Test plant")
        uom=UnitOfMeasure(code=f"G62API-UN-{suffix}",dimension="COUNT",canonical=True)
        session.add_all([plant,uom])
        session.flush()
        article=Article(external_system="G6_TEST",external_code=f"G62API-{suffix}",
                        canonical_description="Material API test",article_kind="PURCHASED",
                        default_uom_id=uom.id)
        session.add(article)
        session.commit()
        ids={"plant":str(plant.id),"uom":str(uom.id),"article":str(article.id)}
        identity=IdentityService(session)
        admin=identity.create_user(UserCreate(username=f"g62admin-{suffix.lower()}",display_name="Admin",password=PASSWORD))
        role=session.scalar(select(Role).where(Role.code=="ADMIN"))
        assert role is not None
        identity.assign_role(admin.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
        viewer=identity.create_user(UserCreate(username=f"g62viewer-{suffix.lower()}",display_name="Viewer",password=PASSWORD))
        viewrole=identity.create_role(RoleCreate(code=f"G62VIEW-{suffix}",name="Materials Viewer"))
        identity.grant_permission(viewrole.id,"materials.read")
        identity.assign_role(viewer.id,RoleAssignmentCreate(role_id=viewrole.id,scope_type="global"))

    with TestClient(create_app(settings,database=database)) as client:
        path="/api/v1/materials"
        assert client.get(path+"/warehouses").status_code==401
        assert client.post("/api/v1/auth/login",json={"username":f"g62admin-{suffix.lower()}","password":PASSWORD}).status_code==200
        wh=client.post(path+"/warehouses",json={"plant_id":ids["plant"],"code":"CENTRAL","name":"Principal"})
        assert wh.status_code==201,wh.text
        loc=client.post(path+"/locations",json={"warehouse_id":wh.json()["id"],"code":"A1","name":"Estante"})
        assert loc.status_code==201,loc.text
        balance_url=path+"/balances"
        params={"article_id":ids["article"],"location_id":loc.json()["id"]}
        unknown=client.get(balance_url,params=params)
        assert unknown.status_code==200 and unknown.json()["initialized"] is False and unknown.json()["on_hand"] is None
        movement={
            **params,"uom_id":ids["uom"],"kind":"RECEIPT","quantity":"4.5",
            "source_system":"G6_TEST","source_reference":"RECEIPT-1","idempotency_key":f"RX-{suffix}",
        }
        for invalid_kind in ("RECEIPT", "ISSUE", "OPENING", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"):
            invalid = client.post(path+"/movements",json={
                **movement, "kind": invalid_kind, "quantity": "0",
                "idempotency_key": f"ZERO-{invalid_kind}-{suffix}",
            })
            assert invalid.status_code == 422, (invalid_kind, invalid.status_code, invalid.text)
        first=client.post(path+"/movements",json=movement)
        assert first.status_code==201,first.text
        assert first.json()["idempotent_replay"] is False
        same=client.post(path+"/movements",json=movement)
        assert same.status_code==201 and same.json()["idempotent_replay"] is True
        assert first.json()["movement"]["id"]==same.json()["movement"]["id"]
        assert client.get(balance_url,params=params).json()["on_hand"]=="4.50000000"
        audit=client.get("/api/v1/audit/events",params={"action":"materials.movement.post"})
        assert audit.status_code==200
        assert any(item["object_id"]==first.json()["movement"]["id"] for item in audit.json())
        assert client.post("/api/v1/auth/logout").status_code==204
        assert client.post("/api/v1/auth/login",json={"username":f"g62viewer-{suffix.lower()}","password":PASSWORD}).status_code==200
        assert client.get(balance_url,params=params).status_code==200
        assert client.get(path+"/movements",params=params).status_code==200
        assert client.post(path+"/movements",json={**movement,"idempotency_key":"unallowed"}).status_code==403
        assert client.post(path+"/locations",json={"warehouse_id":wh.json()["id"],"code":"A2","name":"No"}).status_code==403
        assert client.get("/api/v1/iam/users").status_code==403
