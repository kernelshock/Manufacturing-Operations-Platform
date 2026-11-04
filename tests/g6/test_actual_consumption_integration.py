"""G6.4 integration: measured consumption, atomic stock issue, audit and RBAC."""
import importlib.util
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from mop.application import create_app
from mop.config import Settings
from mop.core.models import Area, Resource, WorkCenter
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.master_data.models import Article, UnitOfMeasure
from mop.materials.consumption_models import MaterialConsumption
from mop.materials.consumption_schemas import ConsumptionCreate, ConsumptionReverse
from mop.materials.consumption_service import MaterialConsumptionService
from mop.materials.models import MaterialMovement
from mop.materials.schemas import MovementCreate, MovementReverse, WarehouseCreate, LocationCreate
from mop.materials.service import MaterialsConflict, MaterialsRule, MaterialsService
from mop.mes.models import ExecutionDispatch, ExecutionOperation
from mop.mes.schemas import ExecutionStartCreate
from mop.mes.service import MESService
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ, reason="disposable PostgreSQL required")
PASSWORD = "G64-Test-Only-Pass-2026!"


def seed_mes_fixture():
    """Reuse G5's real published APS-to-MES fixture instead of inventing an operation."""
    location = Path(__file__).resolve().parents[2] / "infrastructure" / "scripts" / "mes-browser-fixture.py"
    spec = importlib.util.spec_from_file_location("g64_mes_fixture", location)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.seed()


def setup(settings, *, rbacs=False):
    db = DatabaseManager(settings.database_url)
    fixture = seed_mes_fixture()
    suffix = uuid4().hex[:9].upper()
    with db.session() as session:
        resource = session.get(Resource, UUID(fixture["resource_id"]))
        wc = session.get(WorkCenter, resource.work_center_id)
        area = session.get(Area, wc.area_id)
        uom = UnitOfMeasure(code=f"G64-UN-{suffix}", dimension="COUNT", canonical=True)
        session.add(uom)
        session.flush()
        article = Article(
            external_system="G64_TEST", external_code=f"MAT-{suffix}",
            canonical_description="Measured synthetic material", article_kind="PURCHASED",
            default_uom_id=uom.id,
        )
        session.add(article)
        session.flush()
        iam = IdentityService(session)
        admin = iam.create_user(UserCreate(
            username=f"g64-admin-{suffix.lower()}", display_name="G64 administrator", password=PASSWORD,
        ))
        admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        assert admin_role is not None
        iam.assign_role(admin.id, RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"))
        viewer_username = None
        if rbacs:
            viewer = iam.create_user(UserCreate(
                username=f"g64-viewer-{suffix.lower()}", display_name="G64 material viewer",
                password=PASSWORD,
            ))
            role = iam.create_role(RoleCreate(code=f"G64VIEW-{suffix}", name="G64 consumption read-only"))
            iam.grant_permission(role.id, "materials.read")
            iam.assign_role(viewer.id, RoleAssignmentCreate(role_id=role.id, scope_type="global"))
            viewer_username = viewer.username
        session.commit()
        svc = MaterialsService(session)
        warehouse = svc.warehouse(WarehouseCreate(
            plant_id=area.plant_id, code=f"G64WH-{suffix}", name="G64 warehouse",
        ), admin.id, admin.username)
        slot = svc.location(LocationCreate(
            warehouse_id=warehouse.id, code="WORKCELL", name="Workcell material bin",
        ), admin.id, admin.username)
        initial = svc.post(MovementCreate(
            article_id=article.id, location_id=slot.id, uom_id=uom.id,
            kind="OPENING", quantity=Decimal("10"), source_system="G64_TEST",
            source_reference=f"TEST-OPEN-{suffix}", idempotency_key=f"G64-OPEN-{suffix}",
        ), admin.id, admin.username)
        assert initial.movement.quantity == Decimal("10")
        ids = {
            "operation_id": UUID(fixture["source_operation_id"]),
            "pending_operation_id": UUID(fixture["successor_operation_id"]),
            "dispatch_id": UUID(fixture["dispatch_id"]),
            "article_id": article.id, "location_id": slot.id, "uom_id": uom.id,
            "admin_id": admin.id, "username": admin.username,
            "viewer_username": viewer_username,
            "fingerprint": fixture["schedule_fingerprint"],
        }
        return db, ids


def start(db, ids):
    with db.session() as session:
        operation, _, replay = MESService(session).start_operation(
            ids["operation_id"], ExecutionStartCreate(), ids["admin_id"],
        )
        assert not replay and operation.status == "RUNNING"
        return operation.actual_start


def payload(ids, moment, *, qty="4.25", key=None, ref="FABRIC-CONSUMED"):
    return ConsumptionCreate(
        article_id=ids["article_id"], location_id=ids["location_id"],
        uom_id=ids["uom_id"], quantity=Decimal(qty),
        idempotency_key=key or uuid4().hex, evidence_reference=ref, observed_at=moment,
    )


def test_atomic_consumption_and_reversal_preserve_mes_and_aps():
    settings = Settings(environment="test", _env_file=None)
    db, ids = setup(settings)
    with db.session() as session:
        assert not MaterialConsumptionService(session).list(ids["operation_id"])
        assert MaterialsService(session).balance(ids["article_id"], ids["location_id"]).on_hand == Decimal("10")
        pre_dispatch = session.get(ExecutionDispatch, ids["dispatch_id"])
        assert pre_dispatch.schedule_fingerprint == ids["fingerprint"]
    with db.session() as session:
        svc=MaterialConsumptionService(session)
        with pytest.raises(MaterialsRule, match="actually started"):
            svc.record(ids["operation_id"], payload(ids,datetime.now(timezone.utc)),ids["admin_id"],ids["username"])
        with pytest.raises(MaterialsRule, match="actually started"):
            svc.record(ids["pending_operation_id"], payload(ids,datetime.now(timezone.utc)),ids["admin_id"],ids["username"])
    started = start(db,ids)
    with db.session() as session:
        svc=MaterialConsumptionService(session)
        data=payload(ids,started,key=f"G64-POST-{uuid4().hex}")
        posted=svc.record(ids["operation_id"],data,ids["admin_id"],ids["username"])
        assert not posted.idempotent_replay
        assert posted.consumption.recorded_by == ids["admin_id"]
        assert posted.consumption.execution_operation_id == ids["operation_id"]
        assert posted.consumption.quantity == Decimal("4.25")
        assert MaterialsService(session).balance(ids["article_id"],ids["location_id"]).on_hand == Decimal("5.75")
        events=svc.list(ids["operation_id"])
        assert len(events)==1 and events[0].kind=="CONSUME"
        stock=session.get(MaterialMovement,events[0].stock_movement_id)
        assert stock.kind=="ISSUE" and stock.signed_quantity==Decimal("-4.25")
        replay=svc.record(ids["operation_id"],data,ids["admin_id"],ids["username"])
        assert replay.idempotent_replay and replay.consumption.id==posted.consumption.id
        with pytest.raises(MaterialsConflict,match="idempotency"):
            svc.record(ids["operation_id"],payload(ids,started,qty="4.5",key=data.idempotency_key),ids["admin_id"],ids["username"])
        with pytest.raises(MaterialsRule,match="insufficient"):
            svc.record(ids["operation_id"],payload(ids,started,qty="6.0"),ids["admin_id"],ids["username"])
        with pytest.raises(MaterialsRule,match="reserved"):
            MaterialsService(session).reverse(
                stock.id,MovementReverse(source_system="G64_TEST",source_reference="BYPASS",idempotency_key=uuid4().hex),
                ids["admin_id"],ids["username"],
            )
        with pytest.raises(MaterialsRule,match="reserved"):
            MaterialsService(session).post(MovementCreate(
                article_id=ids["article_id"],location_id=ids["location_id"],uom_id=ids["uom_id"],
                kind="ISSUE",quantity=Decimal("1"),source_system="MOP_G6_CONSUMPTION",
                source_reference="BYPASS",idempotency_key=uuid4().hex,
            ),ids["admin_id"],ids["username"])
        reversal=ConsumptionReverse(
            evidence_reference="PHYSICAL-POSTING-ERROR",idempotency_key=f"G64-REV-{uuid4().hex}",
            reason_code="POSTING_ERROR",observed_at=datetime.now(timezone.utc),
        )
        reverted=svc.reverse(posted.consumption.id,reversal,ids["admin_id"],ids["username"])
        assert not reverted.idempotent_replay and reverted.consumption.reversal_of_id==posted.consumption.id
        assert MaterialsService(session).balance(ids["article_id"],ids["location_id"]).on_hand==Decimal("10")
        assert svc.reverse(posted.consumption.id,reversal,ids["admin_id"],ids["username"]).idempotent_replay
        with pytest.raises(MaterialsConflict,match="already reversed"):
            svc.reverse(posted.consumption.id,ConsumptionReverse(
                evidence_reference="SECOND-CORRECTION",idempotency_key=uuid4().hex,
                reason_code="POSTING_ERROR",observed_at=datetime.now(timezone.utc),
            ),ids["admin_id"],ids["username"])
        assert len(svc.list(ids["operation_id"]))==2
        operation=session.get(ExecutionOperation,ids["operation_id"])
        dispatch=session.get(ExecutionDispatch,ids["dispatch_id"])
        assert operation.status=="RUNNING" and operation.produced_quantity is None
        assert dispatch.schedule_fingerprint==ids["fingerprint"]
        assert session.scalar(select(func.count(MaterialConsumption.id)).where(
            MaterialConsumption.execution_operation_id==ids["pending_operation_id"]
        ))==0
        assert session.scalar(select(func.count(MaterialMovement.id)).where(
            MaterialMovement.source_system=="MOP_G6_CONSUMPTION",
        ))==2
        with pytest.raises(DBAPIError,match="append-only"):
            session.execute(text("UPDATE mat_consumption SET quantity=9 WHERE id=:id"),{"id":posted.consumption.id})
        session.rollback()
        with pytest.raises(DBAPIError,match="append-only"):
            session.execute(text("DELETE FROM mat_consumption WHERE id=:id"),{"id":posted.consumption.id})
        session.rollback()


def test_consumption_http_rbac_validation_and_audit():
    settings=Settings(environment="test",_env_file=None)
    db, ids=setup(settings,rbacs=True)
    observed=start(db,ids)
    path=f"/api/v1/materials/operations/{ids['operation_id']}/consumptions"
    request={
        "article_id":str(ids["article_id"]),"location_id":str(ids["location_id"]),
        "uom_id":str(ids["uom_id"]),"quantity":"2.75",
        "evidence_reference":"G64-ISSUE-DOCUMENT","idempotency_key":uuid4().hex,
        "observed_at":observed.isoformat(),
    }
    with TestClient(create_app(settings,database=db)) as client:
        assert client.get(path).status_code==401
        assert client.post(path,json=request).status_code==401
        assert client.post("/api/v1/auth/login",json={
            "username":ids["viewer_username"],"password":PASSWORD,
        }).status_code==200
        assert client.get(path).status_code==200
        assert client.post(path,json=request).status_code==403
        assert client.post("/api/v1/auth/logout").status_code==204
        assert client.post("/api/v1/auth/login",json={
            "username":ids["username"],"password":PASSWORD,
        }).status_code==200
        for invalid in ["0","-1",0.75,"NaN"]:
            bad=client.post(path,json={**request,"quantity":invalid,"idempotency_key":uuid4().hex})
            assert bad.status_code==422,bad.text
        naive=client.post(path,json={**request,"observed_at":"2026-11-03T10:00:00"})
        assert naive.status_code==422
        created=client.post(path,json=request)
        assert created.status_code==201,created.text
        assert not created.json()["idempotent_replay"]
        item=created.json()["consumption"]
        assert item["recorded_by"]==str(ids["admin_id"])
        second=client.post(path,json=request)
        assert second.status_code==201 and second.json()["idempotent_replay"]
        conflict=client.post(path,json={**request,"quantity":"3"})
        assert conflict.status_code==409
        assert len(client.get(path).json())==1
        bal=client.get("/api/v1/materials/balances",params={
            "article_id":str(ids["article_id"]),"location_id":str(ids["location_id"])
        })
        assert bal.status_code==200 and Decimal(bal.json()["on_hand"])==Decimal("7.25")
        audits=client.get("/api/v1/audit/events",params={"action":"materials.consumption.record"})
        assert audits.status_code==200
        assert any(a["object_id"]==item["id"] and
                   a["actor_user_id"]==str(ids["admin_id"]) for a in audits.json())
        revision={
            "idempotency_key":uuid4().hex,"evidence_reference":"ERROR-CORRECTION",
            "reason_code":"POSTING_ERROR","observed_at":datetime.now(timezone.utc).isoformat(),
        }
        undone=client.post(f"/api/v1/materials/consumptions/{item['id']}/reverse",json=revision)
        assert undone.status_code==201,undone.text
        assert Decimal(client.get("/api/v1/materials/balances",params={
            "article_id":str(ids["article_id"]),"location_id":str(ids["location_id"])
        }).json()["on_hand"])==Decimal("10")
