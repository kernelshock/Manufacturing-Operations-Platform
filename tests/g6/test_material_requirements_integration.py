"""G6.3 PostgreSQL/HTTP: traceable BOM leaf demand by plan and taquilla."""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mop.application import create_app
from mop.audit.models import AuditEntry
from mop.config import Settings
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, UserCreate
from mop.iam.service import IdentityService
from mop.materials.models import MaterialMovement
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ, reason="G6.3 uses disposable PostgreSQL"
)
PASSWORD = "G6-BOM-Projection-Integration-2026!"


def write(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code in (200, 201), (path, response.status_code, response.text)
    return response.json()


def new_article(client, suffix, name, kind, uom_id):
    return write(client, "/api/v1/master-data/articles", {
        "external_system": "G6_SYNTH", "external_code": f"{name}-{suffix}",
        "canonical_description": name, "article_kind": kind, "default_uom_id": uom_id,
    })["id"]


def rev(client, article_id):
    return write(client, f"/api/v1/master-data/articles/{article_id}/revisions", {
        "source_fingerprint": uuid4().hex * 2, "revision_label": "SYNTHETIC",
    })["id"]


def bom(client, revision_id, at, components):
    bom_id = write(client, "/api/v1/master-data/bom-revisions", {
        "parent_article_revision_id": revision_id,
        "revision_no": 1, "valid_from": at.isoformat(),
        "source_system": "G6_SYNTH", "source_fingerprint": uuid4().hex * 2,
    })["id"]
    for idx, (child, amount, uom, scrap, child_rev) in enumerate(components, start=1):
        payload = {
            "child_article_id": child, "quantity": amount,
            "source_uom_raw": "UN", "uom_id": uom,
            "source_relation_key": f"{uuid4().hex}-{idx}",
        }
        if scrap is not None:
            payload["scrap_factor"] = scrap
        if child_rev:
            payload["child_revision_id"] = child_rev
        write(client, f"/api/v1/master-data/bom-revisions/{bom_id}/components", payload)
    write(client, f"/api/v1/master-data/bom-revisions/{bom_id}/publish", {})
    return bom_id


def add_line(client, taquilla_id, article_id, sequence, qty):
    return write(client, f"/api/v1/demand/taquillas/{taquilla_id}/products", {
        "article_id": article_id, "sequence_no": sequence,
        "requested_quantity": qty, "deck_position": "SINGLE",
        "source_line_key": f"TEST-{sequence}",
    })


def fixture(client, suffix, at):
    uom = write(client, "/api/v1/master-data/uoms", {
        "code": f"UN-{suffix}", "dimension": "COUNT", "canonical": True,
    })["id"]
    root_a = new_article(client,suffix,"MOONRAKER","FINISHED_PRODUCT",uom)
    root_b = new_article(client,suffix,"APOLLO","FINISHED_PRODUCT",uom)
    sub = new_article(client,suffix,"SUBASSEMBLY","MANUFACTURED",uom)
    material_x = new_article(client,suffix,"STEEL","PURCHASED",uom)
    material_y = new_article(client,suffix,"FABRIC","CONSUMABLE",uom)
    root_rev_a = rev(client,root_a)
    root_rev_b = rev(client,root_b)
    sub_rev = rev(client,sub)
    sub_bom = bom(client,sub_rev,at,[(material_x,"3",uom,"0.1",None)])
    bom_a = bom(client,root_rev_a,at,[
        (sub,"2",uom,None,sub_rev),
        (material_y,"5",uom,None,None),
    ])
    bom_b = bom(client,root_rev_b,at,[(material_x,"4",uom,None,None)])
    plan = write(client,"/api/v1/demand/plans",{
        "plan_number":f"G6-PLAN-{suffix}", "description":"G6 synthetic mix",
    })
    taquillas=[]
    for n in (1,2,3):
        t=write(client,f"/api/v1/demand/plans/{plan['id']}/taquillas",{
            "taquilla_code":f"G6-TQ-{suffix}-{n}", "sequence_no":n,
        })
        taquillas.append(t)
    t1,t2,t3 = taquillas
    line_a = add_line(client,t1["id"],root_a,1,"2")
    add_line(client,t1["id"],root_b,2,"1")
    add_line(client,t2["id"],root_a,1,"3")
    add_line(client,t3["id"],root_a,1,"100")
    write(client,f"/api/v1/demand/taquillas/{t3['id']}/cancel",{
        "reason":"explicit cancelled synthetic order",
    })
    return {
        "plan":plan, "t1":t1, "t2":t2, "t3":t3,
        "root_a":root_a, "root_b":root_b,
        "material_x":material_x, "material_y":material_y,
        "sub":sub, "bom_a":bom_a, "sub_bom":sub_bom,
        "line_a":line_a,
    }


def test_theoretical_bom_demand_multilevel_mix_effectivity_and_rbac():
    settings = Settings(environment="test",_env_file=None)
    db = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].upper()
    username = f"g63-admin-{suffix.lower()}"
    with db.session() as session:
        iam=IdentityService(session)
        user=iam.create_user(UserCreate(username=username,display_name="G6 Admin",password=PASSWORD))
        role=session.scalar(select(Role).where(Role.code=="ADMIN"))
        assert role is not None
        iam.assign_role(user.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
    with TestClient(create_app(settings,database=db)) as client:
        assert client.get("/api/v1/materials/plans/"+str(uuid4())+"/requirements").status_code == 401
        assert client.post("/api/v1/auth/login",json={"username":username,"password":PASSWORD}).status_code==200
        at = datetime.now(timezone.utc) - timedelta(minutes=3)
        data = fixture(client,suffix,at)
        effective = at + timedelta(minutes=2)
        params = {"effective_at": effective.isoformat()}
        endpoint = f"/api/v1/materials/plans/{data['plan']['id']}/requirements"
        with db.session() as session:
            before_movement=session.scalar(select(func.count(MaterialMovement.id)))
            before_audit=session.scalar(select(func.count(AuditEntry.id)))
        response = client.get(endpoint,params=params)
        assert response.status_code==200,response.text
        result=response.json()
        assert result["classification"]=="THEORETICAL_ONLY"
        assert result["stock_effect"]=="NONE"
        assert result["source_product_lines"]==3
        assert result["excluded_cancelled_taquillas"]==[data["t3"]["id"]]
        assert len(result["paths"])==5
        assert all(item["material_article_id"]!=data["sub"] for item in result["paths"])
        totals={item["material_article_id"]:Decimal(item["theoretical_quantity"])
                for item in result["aggregate"]}
        assert totals=={data["material_x"]:Decimal("37"),data["material_y"]:Decimal("25")}
        x_from_a=next(p for p in result["paths"] if p["product_line_id"]==data["line_a"]["id"]
                      and p["material_article_id"]==data["material_x"])
        assert Decimal(x_from_a["theoretical_quantity"])==Decimal("13.2")
        assert x_from_a["bom_revision_id"]==data["bom_a"]
        assert x_from_a["component_bom_revision_id"]==data["sub_bom"]
        assert len(x_from_a["path_component_ids"])==2
        assert len(x_from_a["path_article_ids"])==3
        assert x_from_a["deck_position"]=="SINGLE"
        scoped=client.get(
            f"/api/v1/materials/taquillas/{data['t1']['id']}/requirements",
            params=params,
        )
        assert scoped.status_code==200,scoped.text
        assert scoped.json()["scope"]=="TAQUILLA"
        assert scoped.json()["source_product_lines"]==2
        partial={x["material_article_id"]:Decimal(x["theoretical_quantity"])
                 for x in scoped.json()["aggregate"]}
        assert partial=={data["material_x"]:Decimal("17.2"),data["material_y"]:Decimal("10")}
        assert client.get(endpoint,params={"effective_at":(at-timedelta(seconds=1)).isoformat()}).status_code==422
        assert client.get(endpoint,params={"effective_at":"2026-11-03T11:00:00"}).status_code==422
        assert client.get(endpoint).status_code==422
        assert client.get(
            f"/api/v1/materials/taquillas/{data['t3']['id']}/requirements",params=params
        ).status_code==422
        assert client.get(f"/api/v1/materials/taquillas/{uuid4()}/requirements",params=params).status_code==404
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==before_movement
            assert session.scalar(select(func.count(AuditEntry.id)))==before_audit

        # Only materials.read is necessary for a synthesized read projection,
        # without granting masterdata.read, demand.read or materials.edit.
        viewrole = write(client,"/api/v1/iam/roles",{
            "code":f"G63VIEW-{suffix}","name":"G6.3 materials viewer",
        })
        assert client.post(
            f"/api/v1/iam/roles/{viewrole['id']}/permissions/materials.read"
        ).status_code==204
        viewer=write(client,"/api/v1/iam/users",{
            "username":f"g63-viewer-{suffix.lower()}", "display_name":"G6 Reader", "password":PASSWORD,
        })
        write(client,f"/api/v1/iam/users/{viewer['id']}/roles",{
            "role_id":viewrole["id"],"scope_type":"global",
        })
        assert client.post("/api/v1/auth/logout").status_code==204
        assert client.post("/api/v1/auth/login",json={
            "username":f"g63-viewer-{suffix.lower()}","password":PASSWORD,
        }).status_code==200
        assert client.get(endpoint,params=params).status_code==200
        assert client.get("/api/v1/master-data/bom-revisions").status_code==403
        assert client.get("/api/v1/demand/plans").status_code==403
        assert client.post("/api/v1/materials/warehouses",json={
            "plant_id":str(uuid4()),"code":"NA","name":"No"
        }).status_code==403


def test_projection_rejects_unapproved_root_and_incomplete_sources():
    settings=Settings(environment="test",_env_file=None)
    db=DatabaseManager(settings.database_url)
    suffix=uuid4().hex[:8].upper()
    username=f"g63-invalid-{suffix.lower()}"
    with db.session() as session:
        iam=IdentityService(session)
        user=iam.create_user(UserCreate(username=username,display_name="G6 Admin",password=PASSWORD))
        role=session.scalar(select(Role).where(Role.code=="ADMIN"))
        iam.assign_role(user.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
    with TestClient(create_app(settings,database=db)) as client:
        assert client.post("/api/v1/auth/login",json={"username":username,"password":PASSWORD}).status_code==200
        uom=write(client,"/api/v1/master-data/uoms",{
            "code":f"G63-{suffix}","dimension":"COUNT","canonical":True,
        })["id"]
        product=new_article(client,suffix,"UNAPPROVED","FINISHED_PRODUCT",uom)
        plan=write(client,"/api/v1/demand/plans",{"plan_number":f"G63-INVALID-{suffix}"})
        t=write(client,f"/api/v1/demand/plans/{plan['id']}/taquillas",{
            "taquilla_code":f"G63-INCOMPLETE-{suffix}","sequence_no":1,
        })
        line=add_line(client,t["id"],product,1,"1")
        endpoint=f"/api/v1/materials/plans/{plan['id']}/requirements"
        at=datetime.now(timezone.utc)
        response=client.get(endpoint,params={"effective_at":at.isoformat()})
        assert response.status_code==422
        assert "no effective ACTIVE BOM" in response.json()["detail"]
        # G6 must never manufacture a partial balance from incomplete BOM.
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==0
