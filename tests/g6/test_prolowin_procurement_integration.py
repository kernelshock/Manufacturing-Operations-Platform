"""G6.6 no-API legacy Prolowin acceptance: screenshot, manual and human review."""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mop.application import create_app
from mop.config import Settings
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, UserCreate
from mop.iam.service import IdentityService
from mop.master_data.models import Supplier, Article, UnitOfMeasure
from mop.materials.models import MaterialMovement
from mop.prolowin.procurement_models import ProcurementEvidenceEvent, ProcurementCapture
from mop.persistence.database import DatabaseManager

pytestmark=pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ,reason="disposable PostgreSQL required")
PASSWORD="G66-Legacy-Source-Only-2026!"


def setup():
    settings=Settings(environment="test",_env_file=None)
    db=DatabaseManager(settings.database_url)
    suffix=uuid4().hex[:9].upper()
    with db.session() as session:
        unit=UnitOfMeasure(code="G66U-"+suffix,dimension="COUNT",canonical=True)
        session.add(unit)
        session.flush()
        supplier=Supplier(code="G66S-"+suffix,legal_name="Synthetic parts vendor")
        article=Article(external_system="PROLOWIN",external_code="G66A-"+suffix,
                        canonical_description="Synthetic material",article_kind="PURCHASED",
                        default_uom_id=unit.id)
        session.add_all([supplier,article])
        iam=IdentityService(session)
        admin_role=session.scalar(select(Role).where(Role.code=="ADMIN"))
        assert admin_role
        users=[]
        for x in ("entry","review","reader"):
            user=iam.create_user(UserCreate(
                username=f"g66-{x}-{suffix.lower()}",display_name="G6 "+x,password=PASSWORD))
            if x != "reader":
                iam.assign_role(user.id,RoleAssignmentCreate(role_id=admin_role.id,scope_type="global"))
            users.append(user.username)
        session.commit()
        return settings,db,suffix,users,unit.code,supplier.code,article.external_code


def login(client, username):
    assert client.post("/api/v1/auth/login",json={"username":username,"password":PASSWORD}).status_code==200


def post(client,path,data):
    r=client.post(path,json=data)
    assert r.status_code==201,(path,r.status_code,r.text)
    return r.json()


def event(cap, po, suffix, code, supplier, uom, date, kind, ref, **kwargs):
    return {
        "capture_id":cap,"source_event_key":f"G66-{suffix}-{ref}",
        "kind":kind,"po_number":po,"line_number":1,
        "supplier_code":supplier,"article_code":code,"uom_code":uom,
        "event_date":date.isoformat(),"source_reference":ref,
        **kwargs,
    }


def test_manual_screenshot_verified_partial_receipts_and_original_promise():
    settings,db,suffix,users,uom,supplier,article=setup()
    root="/api/v1/prolowin/procurement"
    po="PO-"+suffix
    order_date=datetime.now(timezone.utc)-timedelta(days=16)
    original=order_date+timedelta(days=7)
    receipt_one=order_date+timedelta(days=9)
    receipt_two=order_date+timedelta(days=11)
    with db.session() as session:
        before=session.scalar(select(func.count(MaterialMovement.id)))
    with TestClient(create_app(settings,database=db)) as client:
        assert client.get(root+"/events").status_code==401
        login(client,users[0])
        manual=post(client,root+"/captures/manual",{
            "source_type":"MANUAL","source_reference":"Prolowin PO screen by operator"
        })
        image=bytes((137,80,78,71,13,10,26,10))+b"synthetic-test-only-pixel"
        screenshot=client.post(root+"/captures/screenshots",content=image,headers={
            "content-type":"image/png","x-evidence-label":"PO actual screenshot test"
        })
        assert screenshot.status_code==201,screenshot.text
        pic=screenshot.json()
        assert pic["source_sha256"] and len(pic["source_sha256"])==64
        same=client.post(root+"/captures/screenshots",content=image,headers={
            "content-type":"image/png","x-evidence-label":"same screenshot"
        })
        assert same.status_code==201 and same.json()["id"]==pic["id"]
        downloaded=client.get(root+f"/captures/{pic['id']}/image")
        assert downloaded.status_code==200 and downloaded.content==image
        assert downloaded.headers["cache-control"]=="no-store"
        bad=client.post(root+"/captures/screenshots",content=b"fake PNG",headers={
            "content-type":"image/png","x-evidence-label":"fake"
        })
        assert bad.status_code==422

        # Unverified orders cannot appear in the trusted supplier history.
        original_order=post(client,root+"/events",event(
            manual["id"],po,suffix,article,supplier,uom,order_date,
            "ORDER","ORDER-1",quantity="10",original_promise_date=original.isoformat(),
        ))
        assert original_order["review_status"]=="PENDING"
        pending=client.get(root+f"/orders/{po}/lines/1",params={"as_of":datetime.now(timezone.utc).isoformat()})
        assert pending.status_code==404
        assert client.post(root+f"/events/{original_order['id']}/review",json={
            "decision":"VERIFIED","note":"cannot self-review"
        }).status_code==422
        assert client.post(root+"/events",json=event(
            manual["id"],po,suffix,article,supplier,uom,order_date,
            "ORDER","ORDER-1",quantity="10",original_promise_date=original.isoformat(),
        )).status_code==409

        rescheduled=post(client,root+"/events",event(
            pic["id"],po,suffix,article,supplier,uom,receipt_one,
            "RESCHEDULE","REV-1",revised_promise_date=(original+timedelta(days=5)).isoformat(),
            continuity_safe=True,reason="No interruption according to PCP",
        ))
        assert client.post(root+"/events",json=event(
            pic["id"],po,suffix,article,supplier,uom,receipt_one,
            "RESCHEDULE","INVALID-REV",revised_promise_date=(original+timedelta(days=5)).isoformat(),
            continuity_safe=False,reason="Production at risk",
        )).status_code==422
        receipt1=post(client,root+"/events",event(
            pic["id"],po,suffix,article,supplier,uom,receipt_one,
            "RECEIPT","REM-01",quantity="6",accepted_quantity="5",
        ))
        receipt2=post(client,root+"/events",event(
            pic["id"],po,suffix,article,supplier,uom,receipt_two,
            "RECEIPT","REM-02",quantity="4",accepted_quantity="4",
        ))
        claim=post(client,root+"/events",event(
            manual["id"],po,suffix,article,supplier,uom,receipt_one,
            "CLAIM","CLAIM-123",reason="Supplier missed original promised date",
        ))
        escalated=post(client,root+"/events",event(
            manual["id"],po,suffix,article,supplier,uom,receipt_two,
            "ESCALATION","ESC-1",reason="Review alternate approved supplier, no automatic PO",
        ))
        weekly=post(client,root+"/captures/manual",{
            "source_type":"WEEKLY_SNAPSHOT","source_reference":"Export weekly control.xlsx"
        })
        secondary=post(client,root+"/events",event(
            weekly["id"],"PO-SECONDARY-"+suffix,suffix,article,supplier,uom,order_date,
            "ORDER","WEEKLY",quantity="5",original_promise_date=original.isoformat(),
        ))
        assert client.post("/api/v1/auth/logout").status_code==204
        login(client,users[1])
        denied=client.post(root+f"/events/{secondary['id']}/review",json={
            "decision":"VERIFIED","note":"source weekly export only"
        })
        assert denied.status_code==422

        approved=client.post(root+f"/events/{original_order['id']}/review",json={
            "decision":"VERIFIED","note":"Compared order to original Prolowin PO screen"
        })
        assert approved.status_code==200,approved.text
        for item in (rescheduled,receipt1,receipt2,claim,escalated):
            reviewed=client.post(root+f"/events/{item['id']}/review",json={
                "decision":"VERIFIED","note":"Independent source screen verification"
            })
            assert reviewed.status_code==200,(reviewed.status_code,reviewed.text)
        summary=client.get(root+f"/orders/{po}/lines/1",params={
            "as_of":datetime.now(timezone.utc).isoformat()
        })
        assert summary.status_code==200,summary.text
        value=summary.json()
        assert Decimal(value["ordered_quantity"])==Decimal("10")
        assert Decimal(value["delivered_quantity"])==Decimal("10")
        assert Decimal(value["accepted_quantity"])==Decimal("9")
        assert Decimal(value["outstanding_delivered_quantity"])==0
        assert value["original_promise_date"]==original.isoformat().replace("+00:00","Z")
        assert value["latest_revised_promise_date"]==(original+timedelta(days=5)).isoformat().replace("+00:00","Z")
        assert value["partial_receipt_count"]==2
        assert value["delayed_days_calendar"]==4
        assert value["delayed_days_revised_calendar"]==0
        assert value["actual_lead_time_calendar_days"]==11
        assert value["completeness"]=="PARTIAL_MANUAL_CAPTURE_NOT_ERP_SYNC"
        assert value["claim_count"]==1
        assert value["production_risk_escalations"]==1
        assert value["physical_inventory_effect"]=="NONE"

        assert client.post(root+f"/events/{receipt1['id']}/review",json={
            "decision":"REJECTED","note":"second review forbidden"
        }).status_code==409
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==before
            db_status=session.scalar(select(ProcurementEvidenceEvent.review_status).where(
                ProcurementEvidenceEvent.id==original_order["id"]
            ))
            assert db_status=="VERIFIED"
        # No physical G6 inventory movements or Prolowin order writes.
        assert client.post("/api/v1/auth/logout").status_code==204
        login(client,users[2])
        assert client.get(root+"/events").status_code==403
        assert client.post(root+"/captures/manual",json={
            "source_type":"MANUAL","source_reference":"no rights"
        }).status_code==403


def test_missing_supplier_article_and_over_receipt_fail_closed():
    settings,db,suffix,users,uom,supplier,article=setup()
    root="/api/v1/prolowin/procurement"
    ordered=datetime.now(timezone.utc)-timedelta(days=12)
    with TestClient(create_app(settings,database=db)) as client:
        login(client,users[0])
        cap=post(client,root+"/captures/manual",{
            "source_reference":"manual record, no ERP interface"
        })
        order=post(client,root+"/events",event(
            cap["id"],"P2-"+suffix,suffix,article,supplier,uom,ordered,"ORDER",
            "ORDER-MISSING",quantity="4",
            original_promise_date=(ordered+timedelta(days=5)).isoformat(),
        ))
        too_much=post(client,root+"/events",event(
            cap["id"],"P2-"+suffix,suffix,article,supplier,uom,
            ordered+timedelta(days=6),"RECEIPT","OVER",quantity="5",
        ))
        unmapped=post(client,root+"/events",event(
            cap["id"],"P3-"+suffix,suffix,"UNKNOWN-"+suffix,supplier,uom,ordered,
            "ORDER","BAD-ARTICLE",quantity="3",
            original_promise_date=(ordered+timedelta(days=5)).isoformat(),
        ))
        assert client.post("/api/v1/auth/logout").status_code==204
        login(client,users[1])
        wrong=client.post(root+f"/events/{unmapped['id']}/review",json={
            "decision":"VERIFIED","note":"Unknown canonical article cannot be approved"
        })
        assert wrong.status_code==422
        assert client.post(root+f"/events/{order['id']}/review",json={
            "decision":"VERIFIED","note":"Source confirmed manually"
        }).status_code==200
        over=client.post(root+f"/events/{too_much['id']}/review",json={
            "decision":"VERIFIED","note":"Too much compared with original PO"
        })
        assert over.status_code==422
        assert "exceed" in over.json()["detail"]
        reject=client.post(root+f"/events/{too_much['id']}/review",json={
            "decision":"REJECTED","note":"Exceeds original purchase quantity"
        })
        assert reject.status_code==200
