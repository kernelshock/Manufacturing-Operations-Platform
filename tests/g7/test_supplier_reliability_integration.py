"""G7.3 PostgreSQL/API acceptance: verified legacy PO lead-time sample + IAM."""
import importlib.util
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mop.application import create_app
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.master_data.models import ManufacturingCalendar, CalendarWeeklyWindow, CalendarException
from mop.materials.models import MaterialMovement
from mop.prolowin.procurement_models import ProcurementCapture, ProcurementEvidenceEvent
from mop.persistence.database import DatabaseManager

pytestmark=pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ,reason="disposable PostgreSQL only")
PASSWORD="G73-Temporary-Synthetic-Only-2026!"


def g65_fixture():
    path=Path(__file__).resolve().parents[1]/"g6"/"test_reservations_integration.py"
    spec=importlib.util.spec_from_file_location("g73_g65_fixture",path)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_supplier_reliability_verified_sample_holidays_partial_receipts_and_permissions():
    g65=g65_fixture()
    settings,db,suffix,admin,plant,actor=g65.setup()
    root="/api/v1/planning/supplier-reliability"
    ts=lambda day: datetime(2026,10,day,12,tzinfo=timezone.utc)
    with TestClient(create_app(settings,database=db)) as client:
        assert client.get(root).status_code==401
        g65.auth(client,admin)
        data,loc,uom,when=g65.prepared(client,db,suffix,plant,initial="20")
        with db.session() as session:
            calendar=ManufacturingCalendar(
                code="G73-CAL-"+suffix,name="Synthetic Mon-Fri / explicit closure",
                revision_no=1,timezone="America/Argentina/Cordoba",
                plant_id=plant,valid_from=date(2026,1,1),status="ACTIVE",
            )
            session.add(calendar)
            session.flush()
            for day in range(5):
                session.add(CalendarWeeklyWindow(calendar_id=calendar.id,weekday=day,
                             start_minute=420,end_minute=960,spans_midnight=False,
                             capacity_factor=Decimal("1")))
            session.add(CalendarException(calendar_id=calendar.id,
                        local_date=date(2026,10,12),exception_kind="CLOSED"))
            capture=ProcurementCapture(source_type="MANUAL",
                     source_reference="G73 synthetic supplier source",captured_by=actor)
            session.add(capture)
            session.flush()
            def evidence(key,po,kind,at,qty=None,**kw):
                session.add(ProcurementEvidenceEvent(
                    id=uuid4(),capture_id=capture.id,source_event_key="G73-"+suffix+"-"+key,
                    kind=kind,po_number=po,line_number=1,supplier_code="G73SUP-"+suffix,
                    article_code="G73ARTICLE-"+suffix,uom_code="G73UOM-"+suffix,
                    quantity=Decimal(qty) if qty else None,event_date=at,
                    source_reference="DOC-"+key,
                    mapped_article_id=UUID(data["material_x"]),mapped_uom_id=UUID(uom),
                    entered_by=actor,review_status="VERIFIED",
                    reviewed_by=actor,reviewed_at=datetime.now(timezone.utc),**kw,
                ))
            po1="G73-CLOSED-"+suffix
            po2="G73-OPEN-"+suffix
            evidence("ORDER1",po1,"ORDER",ts(5),"10",original_promise_date=ts(9))
            evidence("R1",po1,"RECEIPT",ts(14),"4",accepted_quantity=Decimal("3"))
            evidence("R2",po1,"RECEIPT",ts(16),"6",accepted_quantity=Decimal("6"))
            evidence("REPLAN",po1,"RESCHEDULE",ts(13),revised_promise_date=ts(15),
                     reason="Approved reschedule no production risk",continuity_safe=True)
            evidence("ORDER2",po2,"ORDER",ts(5),"5",original_promise_date=ts(8))
            evidence("PARTIAL",po2,"RECEIPT",ts(9),"2",accepted_quantity=Decimal("1"))
            evidence("CLAIM",po2,"CLAIM",ts(13),reason="Late delivery")
            evidence("RISK",po2,"ESCALATION",ts(14),reason="Production at risk")
            # One unverified event may never alter service-level sample.
            session.add(ProcurementEvidenceEvent(
                id=uuid4(),capture_id=capture.id,source_event_key="G73-PENDING-"+suffix,
                kind="RECEIPT",po_number=po2,line_number=1,supplier_code="G73SUP-"+suffix,
                article_code="G73ARTICLE-"+suffix,uom_code="G73UOM-"+suffix,
                quantity=Decimal("3"),event_date=ts(15),source_reference="PENDING",
                entered_by=actor,review_status="PENDING",
                mapped_article_id=UUID(data["material_x"]),mapped_uom_id=UUID(uom),
            ))
            calendar_id=calendar.id
            before=session.scalar(select(func.count(MaterialMovement.id)))
            session.commit()
        params={"plant_id":str(plant),"article_id":data["material_x"],
                "supplier_code":"G73SUP-"+suffix,"calendar_id":str(calendar_id),
                "as_of":datetime.now(timezone.utc).isoformat()}
        response=client.get(root,params=params)
        assert response.status_code==200,response.text
        j=response.json()
        assert j["sample_size"]==2 and j["completed_lines"]==1 and j["open_lines"]==1
        assert j["statistical_reliability_state"]=="INSUFFICIENT_COVERAGE"
        assert j["completeness"]=="UNKNOWN_ERP_COVERAGE"
        assert j["mean_actual_lead_business_days"]=="8"
        assert j["late_against_original_completed"]==1
        assert j["late_against_revised_completed"]==1
        assert j["on_time_original_sample_ratio"]=="0"
        complete=next(x for x in j["lines"] if x["po_number"]==po1)
        openline=next(x for x in j["lines"] if x["po_number"]==po2)
        assert complete["partial_receipt_count"]==2
        assert complete["actual_lead_time_business_days"]==8
        assert complete["original_delay_business_days"]==4
        assert complete["revised_delay_business_days"]==1
        assert openline["status"]=="OPEN" and openline["actual_lead_time_business_days"] is None
        assert openline["outstanding_reported"]=="3.00000000"
        assert openline["claims"]==1 and openline["production_risk_escalations"]==1
        assert j["physical_stock_effect"]=="NONE" and j["purchase_order_effect"]=="NONE"
        historical=client.get(root,params={**params,"as_of":ts(14).isoformat()})
        assert historical.status_code==200,historical.text
        assert historical.json()["completed_lines"]==0
        assert historical.json()["mean_actual_lead_business_days"] is None
        assert historical.json()["lines"][0]["status"]=="OPEN"
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==before
            identity=IdentityService(session)
            viewer=identity.create_user(UserCreate(username="g73viewer-"+suffix.lower(),
                                display_name="G73 limited reader",password=PASSWORD))
            role=identity.create_role(RoleCreate(code="G73VIEW-"+suffix,name="Materials reader only"))
            identity.grant_permission(role.id,"materials.read")
            identity.assign_role(viewer.id,RoleAssignmentCreate(role_id=role.id,scope_type="global"))
            username=viewer.username
        assert client.post("/api/v1/auth/logout").status_code==204
        assert client.post("/api/v1/auth/login",json={"username":username,"password":PASSWORD}).status_code==200
        assert client.get(root,params=params).status_code==403


def test_explicit_calendar_and_future_cutoff_required():
    g65=g65_fixture()
    settings,db,suffix,admin,plant,actor=g65.setup()
    with TestClient(create_app(settings,database=db)) as client:
        g65.auth(client,admin)
        url="/api/v1/planning/supplier-reliability"
        p={"plant_id":str(plant),"article_id":str(uuid4()),"supplier_code":"TEST",
           "calendar_id":str(uuid4()),"as_of":datetime.now(timezone.utc).isoformat()}
        assert client.get(url,params=p).status_code==404
        assert client.get(url,params={**p,"as_of":(datetime.now(timezone.utc)+timedelta(days=4)).isoformat()}).status_code==422
        assert client.get(url,params={**p,"as_of":"2026-10-16T12:00:00"}).status_code==422
