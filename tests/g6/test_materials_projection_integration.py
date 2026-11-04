"""G6.7 source-isolated, read-only Materials dashboard acceptance."""
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
from mop.iam.models import User
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent
from mop.prolowin.procurement_models import ProcurementCapture, ProcurementEvidenceEvent
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ,
                                reason="requires disposable PostgreSQL")
PASSWORD = "G67-Dashboard-Synthetic-Only-2026!"


def fixture():
    file = Path(__file__).with_name("test_reservations_integration.py")
    spec = importlib.util.spec_from_file_location("g67_g65_fixture", file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row_by_article(result, article_id):
    return next(line for line in result["items"] if line["article_id"] == article_id)


def test_plan_projection_isolated_by_plant_no_double_consumption_and_unknown():
    g65 = fixture()
    settings, db, suffix, username, plant_id, actor = g65.setup()
    base="/api/v1/materials"
    with TestClient(create_app(settings, database=db)) as client:
        assert client.get(base+"/projection/plants").status_code == 401
        g65.auth(client, username)
        data, loc, uom, effect = g65.prepared(client, db, suffix, plant_id, initial="20")
        plan=data["plan"]["id"]
        hold1=g65.post(client,base+"/reservations",
                       g65.hold_payload(data,loc,uom,effect,data["t1"],"6","G67-H1-"+suffix))
        hold2=g65.post(client,base+"/reservations",
                       g65.hold_payload(data,loc,uom,effect,data["t2"],"10","G67-H2-"+suffix))
        assert hold1["reservation"]["kind"]=="HOLD" and hold2["reservation"]["kind"]=="HOLD"
        plants=client.get(base+"/projection/plants")
        plans=client.get(base+"/projection/plans")
        assert plants.status_code == 200 and plans.status_code == 200
        assert str(plant_id) in [p["id"] for p in plants.json()]
        assert plan in [p["id"] for p in plans.json()]
        endpoint=base+f"/projection/plans/{plan}"
        params={"plant_id":str(plant_id),"effective_at":effect.isoformat()}
        with db.session() as session:
            movements_before=session.scalar(select(func.count(MaterialMovement.id)))
            reservations_before=session.scalar(select(func.count(MaterialReservationEvent.id)))
        response=client.get(endpoint,params=params)
        assert response.status_code==200,response.text
        result=response.json()
        assert result["basis"]=="THEORETICAL_BOM_PLUS_PHYSICAL_LEDGER"
        assert result["material_count"]==2
        assert result["source_taquillas"]==2
        assert result["unknown_stock_materials"]==1
        assert result["indicative_gap_materials"]==1
        assert result["excluded_cancelled_taquillas"]==[data["t3"]["id"]]
        steel=row_by_article(result,data["material_x"])
        assert Decimal(steel["theoretical_plan_quantity"])==37
        assert Decimal(steel["actual_net_measured_consumption"])==0
        assert Decimal(steel["physical_on_hand"])==20
        assert Decimal(steel["reserved_all_plans"])==16
        assert Decimal(steel["reserved_this_plan"])==16
        assert Decimal(steel["unallocated_physical"])==4
        assert Decimal(steel["provisional_gross_gap"])==17
        assert steel["distinct_taquillas"]==2
        assert steel["source_path_count"]==3
        assert len(steel["location_breakdown"])==1
        assert steel["location_breakdown"][0]["location_id"]==loc
        fabric=row_by_article(result,data["material_y"])
        # Both BOM materials have no MES events: absence must report measured zero.
        assert Decimal(fabric["actual_net_measured_consumption"]) == 0
        assert fabric["physical_on_hand"] is None
        assert fabric["provisional_gross_gap"] is None
        assert fabric["stock_state"]=="UNKNOWN"
        assert "GROSS_PROVISIONAL_NOT_ATP"==result["gap_policy"]
        assert "MEASURED_CONSUMPTION_IS_ALREADY_REFLECTED_IN_PHYSICAL_STOCK" in result["warnings"]
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==movements_before
            assert session.scalar(select(func.count(MaterialReservationEvent.id)))==reservations_before
            original_plant=session.get(Plant,plant_id)
            other=Plant(organization_id=original_plant.organization_id,
                        code="G67-OTHER-"+suffix,name="Other site not in scope")
            session.add(other)
            session.commit()
            other_id=other.id
        other_wh=g65.post(client,base+"/warehouses",{
            "plant_id":str(other_id),"code":"ISOLATED","name":"Unrelated warehouse",
        })
        other_loc=g65.post(client,base+"/locations",{
            "warehouse_id":other_wh["id"],"code":"A1","name":"Another plant",
        })
        g65.post(client,base+"/movements",{
            "article_id":data["material_x"],"location_id":other_loc["id"],
            "uom_id":uom,"kind":"OPENING","quantity":"1000",
            "source_system":"G67_TEST","source_reference":"OTHER-SITE",
            "idempotency_key":"G67-OTHER-"+suffix,
        })
        after_other=client.get(endpoint,params=params)
        assert after_other.status_code==200
        assert Decimal(row_by_article(after_other.json(),data["material_x"])["physical_on_hand"])==20
        other_projection=client.get(endpoint,params={**params,"plant_id":str(other_id)})
        assert other_projection.status_code==200
        assert Decimal(row_by_article(other_projection.json(),data["material_x"])["physical_on_hand"])==1000

        # An active empty location makes a plant-wide stock balance UNKNOWN.
        # Existing verified 20 units must NOT become a falsely precise total.
        primary_wh=client.get(base+"/warehouses",params={"plant_id":str(plant_id)}).json()[0]
        g65.post(client,base+"/locations",{
            "warehouse_id":primary_wh["id"],"code":"UNOPENED","name":"Unknown stock location",
        })
        changed=client.get(endpoint,params=params)
        assert changed.status_code==200,changed.text
        steel=row_by_article(changed.json(),data["material_x"])
        assert steel["physical_on_hand"] is None and steel["provisional_gross_gap"] is None
        assert steel["reserved_all_plans"]=="16.00000000"
        assert len(steel["location_breakdown"])==2
        assert sum(l["state"]=="UNKNOWN" for l in steel["location_breakdown"])==1


def test_procurement_is_separately_authorized_verified_only_and_no_inventory_effect():
    g65=fixture()
    settings,db,suffix,username,plant_id,actor_id=g65.setup()
    base="/api/v1/materials/projection"
    with TestClient(create_app(settings,database=db)) as client:
        g65.auth(client,username)
        data,loc,uom,effect=g65.prepared(client,db,suffix,plant_id,initial="20")
        plan=data["plan"]["id"]
        with db.session() as session:
            baseline=session.scalar(select(func.count(MaterialMovement.id)))
            capture=ProcurementCapture(
                id=uuid4(),source_type="MANUAL",source_reference="Synthetic capture",
                captured_by=actor_id,
            )
            session.add(capture)
            session.flush()
            now=datetime.now(timezone.utc)
            for i, kind, status in (
                (1,"ORDER","VERIFIED"),
                (2,"RECEIPT","VERIFIED"),
                (3,"CLAIM","PENDING"),
            ):
                session.add(ProcurementEvidenceEvent(
                    id=uuid4(),capture_id=capture.id,
                    source_event_key=f"G67-{suffix}-{i}",
                    kind=kind,po_number="G67-PO-"+suffix,line_number=1,
                    supplier_code="G67-SUPPLIER",article_code="G67-MAT",
                    uom_code="UN-"+suffix,
                    quantity=Decimal("8") if kind in ("ORDER","RECEIPT") else None,
                    accepted_quantity=None,event_date=now,
                    original_promise_date=now+timedelta(days=1) if kind=="ORDER" else None,
                    source_reference="G67-DOC-"+str(i),
                    mapped_article_id=UUID(data["material_x"]),
                    mapped_uom_id=UUID(uom),
                    review_status=status,entered_by=actor_id,
                    reviewed_by=actor_id if status=="VERIFIED" else None,
                    reviewed_at=now if status=="VERIFIED" else None,
                ))
            session.commit()
        evidence=client.get(base+f"/plans/{plan}/procurement",
                            params={"effective_at":effect.isoformat()})
        assert evidence.status_code==200,evidence.text
        data_resp=evidence.json()
        assert data_resp["data_scope"]=="VERIFIED_MANUAL_SAMPLES_ONLY"
        assert data_resp["no_verified_records_means"]=="UNKNOWN_NOT_ZERO"
        material=row_by_article(data_resp,data["material_x"])
        assert material["verified_order_lines"]==1
        assert material["verified_receipt_events"]==1
        assert material["verified_claims"]==0
        assert material["latest_verified_event_at"] is not None
        other=row_by_article(data_resp,data["material_y"])
        assert other["verified_order_lines"]==0
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==baseline
            iam=IdentityService(session)
            reader=iam.create_user(UserCreate(
                username="g67-reader-"+suffix.lower(),display_name="G67 materials only",
                password=PASSWORD,
            ))
            role=iam.create_role(RoleCreate(code="G67-READ-"+suffix,name="G67 materials only"))
            iam.grant_permission(role.id,"materials.read")
            iam.assign_role(reader.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
            reader_name=reader.username
        assert client.post("/api/v1/auth/logout").status_code==204
        assert client.post("/api/v1/auth/login",json={
            "username":reader_name,"password":PASSWORD,
        }).status_code==200
        result=client.get(base+f"/plans/{plan}",params={
            "plant_id":str(plant_id),"effective_at":effect.isoformat(),
        })
        assert result.status_code==200
        assert client.get(base+f"/plans/{plan}/procurement",
                          params={"effective_at":effect.isoformat()}).status_code==403
        assert client.get("/api/v1/prolowin/procurement/events").status_code==403
        assert client.get("/api/v1/demand/plans").status_code==403
        assert client.get("/api/v1/master-data/articles").status_code==403
