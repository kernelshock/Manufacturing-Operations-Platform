"""G7.2 real PostgreSQL & FastAPI acceptance: no stock or purchasing side effects."""
import importlib.util
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mop.application import create_app
from mop.core.models import Plant
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent
from mop.prolowin.procurement_models import ProcurementCapture, ProcurementEvidenceEvent
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ,
                                reason="requires disposable PostgreSQL")
PASSWORD = "G72-Read-Only-Synthetic-2026!"


def source_fixture():
    file = Path(__file__).resolve().parents[1] / "g6" / "test_reservations_integration.py"
    spec = importlib.util.spec_from_file_location("g72_g65", file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stock_holds_unknown_quality_and_manual_order_sample_are_distinct():
    g65 = source_fixture()
    settings, db, suffix, admin, plant, actor = g65.setup()
    root = "/api/v1/planning/supply-position"
    with TestClient(create_app(settings, database=db)) as client:
        unauthenticated = client.get(root, params={
            "plant_id": str(plant), "article_id": str(uuid4()),
            "evidence_cutoff_at": datetime.now(timezone.utc).isoformat(),
        })
        assert unauthenticated.status_code == 401
        g65.auth(client, admin)
        data, loc, uom, effect = g65.prepared(client, db, suffix, plant, initial="20")
        g65.post(client, "/api/v1/materials/reservations",
                 g65.hold_payload(data, loc, uom, effect, data["t1"], "6", "G72-H-"+suffix))
        # Two independent verified Prolowin events are still incomplete/manual.
        now = datetime.now(timezone.utc) - timedelta(days=1)
        order_day = now - timedelta(days=4)
        promise = now + timedelta(days=3)
        with db.session() as session:
            capture = ProcurementCapture(source_type="MANUAL",
                                         source_reference="G72 synthetic purchase screen",
                                         captured_by=actor)
            session.add(capture)
            session.flush()
            for seq, kind, qty, event_at in ((1,"ORDER","12",order_day),
                                              (2,"RECEIPT","5",now)):
                session.add(ProcurementEvidenceEvent(
                    id=uuid4(), capture_id=capture.id,
                    source_event_key=f"G72-{suffix}-{seq}", kind=kind,
                    po_number=f"G72-PO-{suffix}", line_number=1,
                    supplier_code="G72-SYNTHETIC", article_code="G72-MAT",
                    uom_code="G72-UN", quantity=Decimal(qty),
                    accepted_quantity=Decimal("4") if kind=="RECEIPT" else None,
                    event_date=event_at,
                    original_promise_date=promise if kind=="ORDER" else None,
                    source_reference=f"G72-DOC-{seq}",
                    mapped_article_id=UUID(data["material_x"]),
                    mapped_uom_id=UUID(uom), review_status="VERIFIED",
                    entered_by=actor, reviewed_by=actor, reviewed_at=datetime.now(timezone.utc),
                ))
            before_move = session.scalar(select(func.count(MaterialMovement.id)))
            before_hold = session.scalar(select(func.count(MaterialReservationEvent.id)))
            session.commit()
        params={"plant_id":str(plant),"article_id":data["material_x"],
                "evidence_cutoff_at":datetime.now(timezone.utc).isoformat()}
        response=client.get(root,params=params)
        assert response.status_code==200,response.text
        v=response.json()
        assert Decimal(v["physical_on_hand"])==20
        assert Decimal(v["committed_holds"])==6
        assert Decimal(v["unallocated_physical"])==14
        assert v["quality_usable"] is None and v["quality_unallocated"] is None
        assert v["confirmed_in_transit"] is None
        assert v["physical_state"]=="KNOWN"
        assert v["supplier_evidence_state"]=="PARTIAL_VERIFIED_MANUAL"
        assert Decimal(v["verified_open_order_sample"])==7
        assert v["order_lines"][0]["effective_promise_at"]==promise.isoformat().replace("+00:00","Z")
        assert Decimal(v["order_lines"][0]["received_reported"])==5
        assert Decimal(v["order_lines"][0]["accepted_reported"])==4
        assert v["stock_effect"]=="NONE" and v["purchasing_effect"]=="NONE"
        assert "ORDERS_ARE_NOT_PLANT_ASSIGNED_IN_LEGACY_EVIDENCE" in v["warnings"]

        # Historical event cutoff must omit later receipt but MUST NOT pretend
        # it is a historical inventory snapshot.
        old=client.get(root,params={**params,"evidence_cutoff_at":
            (order_day+timedelta(hours=1)).isoformat()})
        assert old.status_code==200,old.text
        assert Decimal(old.json()["verified_open_order_sample"])==12
        assert Decimal(old.json()["physical_on_hand"])==20
        assert "PHYSICAL_IS_CURRENT_POSTED_LEDGER_NOT_HISTORICAL_AS_OF" in old.json()["warnings"]

        # Article with no opening cannot be silently treated as zero.
        unknown=client.get(root,params={**params,"article_id":data["material_y"]})
        assert unknown.status_code==200,unknown.text
        assert unknown.json()["physical_on_hand"] is None
        assert unknown.json()["unallocated_physical"] is None
        assert unknown.json()["verified_open_order_sample"] is None

        # Uninitialized active location makes all-plant stock UNKNOWN.
        warehouses=client.get("/api/v1/materials/warehouses",params={"plant_id":str(plant)}).json()
        g65.post(client,"/api/v1/materials/locations",{
            "warehouse_id":warehouses[0]["id"],"code":"G72-UNOPENED","name":"No inventory"})
        partial=client.get(root,params=params)
        assert partial.status_code==200
        assert partial.json()["physical_on_hand"] is None
        assert partial.json()["committed_holds"]=="6.00000000"

        # Another plant must never inherit physical G6 stock or holds.
        with db.session() as session:
            p=session.get(Plant,plant)
            other=Plant(organization_id=p.organization_id,code="G72-OTHER-"+suffix,
                        name="Other isolated site")
            session.add(other)
            session.commit()
            other_id=other.id
        cross=client.get(root,params={**params,"plant_id":str(other_id)})
        assert cross.status_code==200
        assert cross.json()["physical_on_hand"] is None
        assert cross.json()["committed_holds"]=="0"
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==before_move
            assert session.scalar(select(func.count(MaterialReservationEvent.id)))==before_hold

        # Separate procurement permission: materials reader cannot see supplier data.
        with db.session() as session:
            identity=IdentityService(session)
            viewer=identity.create_user(UserCreate(username=f"g72viewer-{suffix.lower()}",
                                                  display_name="G72 materials reader",
                                                  password=PASSWORD))
            role=identity.create_role(RoleCreate(code="G72VIEW-"+suffix,name="G72 materials"))
            identity.grant_permission(role.id,"materials.read")
            identity.assign_role(viewer.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
            viewer_name=viewer.username
        assert client.post("/api/v1/auth/logout").status_code==204
        assert client.post("/api/v1/auth/login",json={
            "username":viewer_name,"password":PASSWORD}).status_code==200
        assert client.get(root,params=params).status_code==403
        assert client.get("/api/v1/materials/balances",params={
            "article_id":data["material_x"],"location_id":loc}).status_code==200


def test_bad_cutoff_and_missing_objects_fail_closed():
    g65=source_fixture()
    settings,db,suffix,username,plant,_=g65.setup()
    with TestClient(create_app(settings,database=db)) as client:
        g65.auth(client,username)
        path="/api/v1/planning/supply-position"
        future=datetime.now(timezone.utc)+timedelta(days=30)
        result=client.get(path,params={"plant_id":str(plant),"article_id":str(uuid4()),
                                        "evidence_cutoff_at":future.isoformat()})
        assert result.status_code==422
        missing=client.get(path,params={"plant_id":str(plant),"article_id":str(uuid4()),
                                         "evidence_cutoff_at":datetime.now(timezone.utc).isoformat()})
        assert missing.status_code==404
