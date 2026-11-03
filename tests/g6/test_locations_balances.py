"""G6.2 PostgreSQL integration: ledger invariants, idempotency and immutability."""
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from mop.config import Settings
from mop.core.models import Organization, Plant
from mop.iam.models import User
from mop.master_data.models import Article, UnitOfMeasure
from mop.materials.models import MaterialMovement
from mop.materials.schemas import LocationCreate, MovementCreate, MovementReverse, WarehouseCreate
from mop.materials.service import MaterialsConflict, MaterialsRule, MaterialsService
from mop.persistence.database import DatabaseManager

pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="G6.2 requires explicit disposable PostgreSQL integration DB",
)


def setup(session):
    code = uuid4().hex[:10].upper()
    org = Organization(code=f"G62O-{code}", name="G6 test organization")
    session.add(org)
    session.flush()
    plant = Plant(organization_id=org.id, code=f"G62P-{code}", name="G6 test plant")
    uom = UnitOfMeasure(code=f"G62U-{code}", dimension="COUNT", canonical=True)
    user = User(username=f"g62-{code.lower()}", display_name="G6 operator", password_hash="test-only")
    session.add_all([plant,uom,user])
    session.flush()
    article = Article(
        external_system="G6_TEST",external_code=f"A-{code}",
        canonical_description="Test-only stock article",
        article_kind="PURCHASED", default_uom_id=uom.id,
    )
    session.add(article)
    session.commit()
    svc = MaterialsService(session)
    wh = svc.warehouse(WarehouseCreate(plant_id=plant.id,code=f"WH-{code}",name="Warehouse"),user.id,user.username)
    location = svc.location(LocationCreate(warehouse_id=wh.id,code="RACK-1",name="Rack 1"),user.id,user.username)
    return svc, article, uom, location, user, wh


def movement(article, uom, location, key, qty, kind, ref=None):
    return MovementCreate(
        article_id=article.id,location_id=location.id,uom_id=uom.id,
        kind=kind,quantity=Decimal(qty),
        source_system="G6_TEST",source_reference=ref or "TRX-001",
        idempotency_key=key,occurred_at=datetime(2026,11,3,tzinfo=timezone.utc),
    )


def test_zero_opening_posts_and_reconciles_without_silent_inference():
    db=DatabaseManager(Settings(environment="test",_env_file=None).database_url)
    with db.session() as session:
        svc,article,uom,loc,user,_=setup(session)
        initial=svc.balance(article.id,loc.id)
        assert not initial.initialized and initial.on_hand is None
        with pytest.raises(MaterialsRule,match="UNKNOWN"):
            svc.post(movement(article,uom,loc,"no-opening","1","ISSUE"),user.id,user.username)
        opened=svc.post(movement(article,uom,loc,"zero-opening","0","OPENING_ZERO"),user.id,user.username)
        assert opened.movement.signed_quantity == 0
        assert svc.balance(article.id,loc.id).initialized
        assert svc.balance(article.id,loc.id).on_hand == Decimal("0")
        with pytest.raises(MaterialsRule,match="only once"):
            svc.post(movement(article,uom,loc,"opening-again","2","OPENING"),user.id,user.username)
        in_stock=svc.post(movement(article,uom,loc,"receipt-1","8.5","RECEIPT"),user.id,user.username)
        assert in_stock.movement.signed_quantity == Decimal("8.5")
        assert svc.balance(article.id,loc.id).on_hand == Decimal("8.5")
        out=svc.post(movement(article,uom,loc,"issue-1","8.5","ISSUE"),user.id,user.username)
        assert out.movement.signed_quantity == Decimal("-8.5")
        assert svc.balance(article.id,loc.id).on_hand == Decimal("0")
        assert len(svc.list_movements(article.id,loc.id)) == 3


def test_replay_conflict_reversal_and_negative_stock_guard():
    db=DatabaseManager(Settings(environment="test",_env_file=None).database_url)
    with db.session() as session:
        svc,article,uom,loc,user,_=setup(session)
        created=svc.post(movement(article,uom,loc,"receipt","5","RECEIPT"),user.id,user.username)
        again=svc.post(movement(article,uom,loc,"receipt","5","RECEIPT"),user.id,user.username)
        assert again.idempotent_replay and again.movement.id==created.movement.id
        with pytest.raises(MaterialsConflict,match="idempotency"):
            svc.post(movement(article,uom,loc,"receipt","6","RECEIPT"),user.id,user.username)
        with pytest.raises(MaterialsRule,match="insufficient"):
            svc.post(movement(article,uom,loc,"too-much","6","ISSUE"),user.id,user.username)
        assert svc.balance(article.id,loc.id).on_hand == Decimal("5")
        reversal=MovementReverse(source_system="G6_TEST",source_reference="CANCEL-RECEIPT",idempotency_key="rev-1")
        rev=svc.reverse(created.movement.id,reversal,user.id,user.username)
        assert rev.movement.kind=="REVERSAL" and rev.movement.signed_quantity==Decimal("-5")
        assert svc.balance(article.id,loc.id).on_hand==Decimal("0")
        replay=svc.reverse(created.movement.id,reversal,user.id,user.username)
        assert replay.idempotent_replay and replay.movement.id==rev.movement.id
        with pytest.raises(MaterialsConflict,match="already reversed"):
            svc.reverse(created.movement.id,MovementReverse(
                source_system="G6_TEST",source_reference="ANOTHER",idempotency_key="rev-2"
            ),user.id,user.username)


def test_ledger_rejects_direct_mutation_at_database_boundary():
    db=DatabaseManager(Settings(environment="test",_env_file=None).database_url)
    with db.session() as session:
        svc,article,uom,loc,user,_=setup(session)
        posted=svc.post(movement(article,uom,loc,"original","2","RECEIPT"),user.id,user.username)
        with pytest.raises(DBAPIError,match="append-only"):
            session.execute(text("UPDATE mat_movement SET signed_quantity = 99 WHERE id = :id"),{"id":posted.movement.id})
        session.rollback()
        with pytest.raises(DBAPIError,match="append-only"):
            session.execute(text("DELETE FROM mat_movement WHERE id = :id"),{"id":posted.movement.id})
        session.rollback()
        assert svc.balance(article.id,loc.id).on_hand==Decimal("2")


def test_duplicate_warehouse_and_location_are_conflicts():
    db=DatabaseManager(Settings(environment="test",_env_file=None).database_url)
    with db.session() as session:
        svc,_,_,_,user,wh=setup(session)
        with pytest.raises(MaterialsConflict):
            svc.warehouse(WarehouseCreate(plant_id=wh.plant_id,code=wh.code,name="Duplicate"),user.id,user.username)
        existing=svc.list_locations(wh.id)[0]
        with pytest.raises(MaterialsConflict):
            svc.location(LocationCreate(warehouse_id=wh.id,code=existing.code,name="Duplicate"),user.id,user.username)
