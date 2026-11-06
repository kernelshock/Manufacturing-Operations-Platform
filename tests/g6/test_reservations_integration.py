"""G6.5 live PostgreSQL & API acceptance for taquilla stock commitments."""
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from mop.application import create_app
from mop.config import Settings
from mop.core.models import Organization, Plant
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.master_data.models import Article
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent
from mop.materials.reservation_schemas import ReservationCreate
from mop.materials.reservation_service import ReservationService
from mop.materials.schemas import MovementCreate
from mop.materials.service import MaterialsRule, MaterialsService
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ,
                                reason="requires disposable PostgreSQL database")
PASSWORD = "G65-Tests-Only-Do-Not-Reuse-2026!"

def fixture_module():
    path = Path(__file__).with_name("test_material_requirements_integration.py")
    spec = importlib.util.spec_from_file_location("g65_g63_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def setup():
    settings=Settings(environment="test", _env_file=None)
    db=DatabaseManager(settings.database_url)
    suffix=uuid4().hex[:9].upper()
    username="g65-admin-"+suffix.lower()
    with db.session() as session:
        org=Organization(code="G65ORG-"+suffix,name="G65 synthetic organization")
        session.add(org);session.flush()
        plant=Plant(organization_id=org.id,code="G65PLANT-"+suffix,name="G65 synthetic plant")
        session.add(plant)
        iam=IdentityService(session)
        user=iam.create_user(UserCreate(username=username,display_name="G65 admin",password=PASSWORD))
        role=session.scalar(select(Role).where(Role.code=="ADMIN"))
        assert role
        iam.assign_role(user.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
        session.commit()
        plant_id=plant.id
        actor_id=user.id
    return settings,db,suffix,username,plant_id,actor_id

def auth(client, username):
    response=client.post("/api/v1/auth/login",json={"username":username,"password":PASSWORD})
    assert response.status_code==200,response.text

def post(client, path, value):
    response=client.post(path,json=value)
    assert response.status_code==201,(path,response.status_code,response.text)
    return response.json()

def prepared(client,db,suffix,plant_id,initial="20"):
    g63=fixture_module()
    bom_at=datetime.now(timezone.utc)-timedelta(minutes=4)
    data=g63.fixture(client,suffix,bom_at)
    t=bom_at+timedelta(minutes=2)
    with db.session() as session:
        article=session.get(Article,UUID(data["material_x"]))
        uom=article.default_uom_id
    wh=post(client,"/api/v1/materials/warehouses",
            {"plant_id":str(plant_id),"code":"CENTRAL","name":"G65 central"})
    loc=post(client,"/api/v1/materials/locations",
             {"warehouse_id":wh["id"],"code":"A1","name":"Rack A1"})
    if initial is not None:
        post(client,"/api/v1/materials/movements",{
            "article_id":data["material_x"],"location_id":loc["id"],"uom_id":str(uom),
            "kind":"OPENING" if Decimal(initial)>0 else "OPENING_ZERO",
            "quantity":initial,"source_system":"G65_TEST",
            "source_reference":"INITIAL","idempotency_key":"OPEN-"+suffix,
        })
    return data,loc["id"],str(uom),t

def hold_payload(data,loc,uom,when,taquilla,qty,key):
    return {
        "taquilla_id":taquilla["id"],"article_id":data["material_x"],
        "location_id":loc,"uom_id":uom,"quantity":qty,
        "bom_effective_at":when.isoformat(),"idempotency_key":key,
        "source_reference":"G65-ALLOC-"+key,
    }

def availability(client,data,loc):
    r=client.get("/api/v1/materials/availability",params={
        "article_id":data["material_x"],"location_id":loc})
    assert r.status_code==200,r.text
    return r.json()

def test_reserve_partial_release_availability_bom_risk_and_rbac():
    settings,db,suffix,username,plant_id,actor_id=setup()
    with TestClient(create_app(settings,database=db)) as client:
        assert client.get("/api/v1/materials/availability").status_code==401
        auth(client,username)
        data,loc,uom,effective=prepared(client,db,suffix,plant_id)
        with db.session() as session:
            before_movement=session.scalar(select(func.count(MaterialMovement.id)))
        held=post(client,"/api/v1/materials/reservations",hold_payload(
            data,loc,uom,effective,data["t1"],"6","HOLD-"+suffix))
        assert not held["idempotent_replay"]
        assert Decimal(held["reservation"]["signed_quantity"])==6
        assert client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,effective,data["t1"],"6","HOLD-"+suffix)).json()["idempotent_replay"]
        repeated=client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,effective,data["t1"],"7","HOLD-"+suffix))
        assert repeated.status_code==409
        held_t2=post(client,"/api/v1/materials/reservations",hold_payload(
            data,loc,uom,effective,data["t2"],"10","HOLD-2-"+suffix))
        state=availability(client,data,loc)
        assert Decimal(state["on_hand"])==20
        assert Decimal(state["reserved"])==16
        assert Decimal(state["unallocated_on_hand"])==4
        assert state["state"]=="PHYSICAL_UNALLOCATED_NOT_QUALITY_CERTIFIED"
        covered=client.get(f"/api/v1/materials/taquillas/{data['t1']['id']}/coverage",params={
            "article_id":data["material_x"],"location_id":loc,
            "effective_at":effective.isoformat(),
        })
        assert covered.status_code==200,covered.text
        assert Decimal(covered.json()["theoretical_required"])==Decimal("17.2")
        assert Decimal(covered.json()["held_for_taquilla"])==6
        assert Decimal(covered.json()["shortage"])==Decimal("7.2")
        assert covered.json()["quality_status"]=="NOT_VERIFIED"
        insufficient=client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,effective,data["t1"],"5","TOO-MUCH-"+suffix))
        assert insufficient.status_code==422
        oversized=client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,effective,data["t1"],"12","OVER-BOM-"+suffix))
        assert oversized.status_code==422
        assert "demand" in oversized.json()["detail"]
        cancelled=client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,effective,data["t3"],"1","CANCEL-"+suffix))
        assert cancelled.status_code==422
        # An ISSUE or receipt reversal cannot consume a commitment of another taquilla.
        issue=client.post("/api/v1/materials/movements",json={
            "article_id":data["material_x"],"location_id":loc,"uom_id":uom,
            "kind":"ISSUE","quantity":"5","source_system":"G65_TEST",
            "source_reference":"UNALLOCATED-ISSUE","idempotency_key":"ISSUE-"+suffix,
        })
        assert issue.status_code==422 and "reserved" in issue.json()["detail"]
        release={"quantity":"2","source_reference":"RECOVERY","reason_code":"PLAN_CHANGE",
                 "idempotency_key":"RELEASE-"+suffix}
        first=post(client,f"/api/v1/materials/reservations/{held['reservation']['id']}/release",release)
        assert Decimal(first["reservation"]["signed_quantity"])==-2
        assert client.post(f"/api/v1/materials/reservations/{held['reservation']['id']}/release",
                           json=release).json()["idempotent_replay"]
        excessive=client.post(f"/api/v1/materials/reservations/{held['reservation']['id']}/release",
            json={**release,"quantity":"5","idempotency_key":"RELEASE-MORE-"+suffix})
        assert excessive.status_code==409
        stock=availability(client,data,loc)
        assert Decimal(stock["on_hand"])==20
        assert Decimal(stock["reserved"])==14
        assert Decimal(stock["unallocated_on_hand"])==6
        events=client.get(f"/api/v1/materials/taquillas/{data['t1']['id']}/reservations")
        assert events.status_code==200 and len(events.json())==2
        assert {entry["kind"] for entry in events.json()}=={"HOLD","RELEASE"}
        # Stock posting has not changed because reservation/release is NOT an ISSUE.
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==before_movement
            audit=session.execute(text(
                "SELECT count(*) FROM audit_event WHERE action LIKE 'materials.reservation.%' "
                "AND actor_user_id=:actor"
            ),{"actor":actor_id}).scalar_one()
            assert audit==3
            with pytest.raises(DBAPIError,match="append-only"):
                session.execute(text("UPDATE mat_reservation_event SET quantity=9 WHERE id=:id"),
                                {"id":UUID(held["reservation"]["id"])})
            session.rollback()
            # PostgreSQL must also reject a forged HOLD bearing a negative sign.
            with pytest.raises(DBAPIError,match="ck_mat_res_signed"):
                session.execute(text("""
                    INSERT INTO mat_reservation_event
                    (id, kind, plan_id, taquilla_id, article_id, location_id,
                     uom_id, quantity, signed_quantity, bom_effective_at,
                     idempotency_key, source_reference, recorded_by)
                    SELECT :id, 'HOLD', plan_id, taquilla_id, article_id, location_id,
                           uom_id, quantity, -quantity, bom_effective_at,
                           :key, 'FORGED', recorded_by
                    FROM mat_reservation_event WHERE id = :hold_id
                """), {
                    "id":uuid4(), "key":"FORGED-"+suffix,
                    "hold_id":UUID(held["reservation"]["id"]),
                })
            session.rollback()

        # materials.read has no edit permission or inherited demand/master rights.
        viewer_name="g65-viewer-"+suffix.lower()
        viewer=post(client,"/api/v1/iam/users",{
            "username":viewer_name,"display_name":"Materials reader","password":PASSWORD})
        role=post(client,"/api/v1/iam/roles",{
            "code":"G65VIEW-"+suffix,"name":"G65 read-only"})
        granted=client.post(f"/api/v1/iam/roles/{role['id']}/permissions/materials.read")
        assert granted.status_code==204,granted.text
        assert client.post(f"/api/v1/iam/users/{viewer['id']}/roles",
            json={"role_id":role["id"],"scope_type":"global"}).status_code==201
        assert client.post("/api/v1/auth/logout").status_code==204
        auth(client,viewer_name)
        assert client.get("/api/v1/materials/availability",params={
            "article_id":data["material_x"],"location_id":loc}).status_code==200
        assert client.get(f"/api/v1/materials/taquillas/{data['t1']['id']}/reservations").status_code==200
        assert client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,effective,data["t1"],"1","NO-EDIT-"+suffix)).status_code==403
        assert client.post(f"/api/v1/materials/reservations/{held['reservation']['id']}/release",
                           json=release).status_code==403
        assert client.get("/api/v1/demand/plans").status_code==403

def test_reservation_rejects_unknown_stock_without_inference():
    settings,db,suffix,username,plant,_=setup()
    with TestClient(create_app(settings,database=db)) as client:
        auth(client,username)
        data,loc,uom,at=prepared(client,db,suffix,plant,initial=None)
        state=availability(client,data,loc)
        assert state["on_hand"] is None and state["unallocated_on_hand"] is None
        assert Decimal(state["reserved"])==0
        response=client.post("/api/v1/materials/reservations",json=hold_payload(
            data,loc,uom,at,data["t1"],"1","UNKNOWN-"+suffix))
        assert response.status_code==422
        assert "UNKNOWN" in response.json()["detail"]
        coverage=client.get(f"/api/v1/materials/taquillas/{data['t1']['id']}/coverage",
            params={"article_id":data["material_x"],"location_id":loc,
                    "effective_at":at.isoformat()})
        assert coverage.status_code==200
        assert coverage.json()["shortage"] is None and coverage.json()["stock_state"]=="UNKNOWN"

def test_concurrent_holds_cannot_exceed_stock_or_taquilla_demand():
    settings,db,suffix,username,plant,actor=setup()
    with TestClient(create_app(settings,database=db)) as client:
        auth(client,username)
        data,loc,uom,at=prepared(client,db,suffix,plant,initial="20")
    def attempt(key):
        with db.session() as session:
            svc=ReservationService(session)
            try:
                result=svc.hold(ReservationCreate(**hold_payload(
                    data,loc,uom,at,data["t1"],"12",key
                )),actor,username)
                return result.reservation.quantity
            except MaterialsRule:
                session.rollback()
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(attempt,["CONCURRENT-A-"+suffix,"CONCURRENT-B-"+suffix]))
    assert outcomes.count(Decimal("12"))==1, outcomes
    assert outcomes.count(None)==1,outcomes
    with db.session() as session:
        stock=ReservationService(session).availability(UUID(data["material_x"]),UUID(loc))
        assert stock.on_hand==Decimal("20")
        assert stock.reserved==Decimal("12")
        assert stock.unallocated_on_hand==Decimal("8")
