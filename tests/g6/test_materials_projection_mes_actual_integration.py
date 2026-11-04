"""G6.7 regression: measured MES use must be compared without duplicate stock issue."""
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
from mop.config import Settings
from mop.master_data.models import Article, ArticleRevision
from mop.materials.consumption_schemas import ConsumptionCreate
from mop.materials.consumption_service import MaterialConsumptionService
from mop.materials.models import MaterialLocation, MaterialMovement, MaterialWarehouse
from mop.materials.schemas import MovementCreate
from mop.materials.service import MaterialsService
from mop.mes.models import ExecutionOperation
from mop.persistence.database import DatabaseManager

pytestmark=pytest.mark.skipif("MOP_DATABASE_URL" not in os.environ,
                              reason="requires disposable PostgreSQL 18")


def module_from(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_measured_bom_and_unplanned_consumption_are_visible_without_double_issue():
    settings=Settings(environment="test",_env_file=None)
    here=Path(__file__).resolve().parent
    g64=module_from(here/"test_actual_consumption_integration.py","g67_g64")
    g63=module_from(here/"test_material_requirements_integration.py","g67_g63")
    db, ids=g64.setup(settings)
    suffix=uuid4().hex[:8].upper()
    with db.session() as session:
        op=session.get(ExecutionOperation,ids["operation_id"])
        assert op is not None
        plan_id=op.plan_id
        root=session.get(Article,op.article_id)
        root.default_uom_id=ids["uom_id"]
        rev=session.scalar(select(ArticleRevision).where(ArticleRevision.article_id==root.id))
        assert rev is not None
        rev_id=rev.id
        location=session.get(MaterialLocation,ids["location_id"])
        wh=session.get(MaterialWarehouse,location.warehouse_id)
        plant_id=wh.plant_id
        unexpected=Article(
            external_system="G67_TEST",external_code="EXTRA-"+suffix,
            canonical_description="Unplanned production input",
            article_kind="PURCHASED",default_uom_id=ids["uom_id"],
        )
        session.add(unexpected)
        session.commit()
        extra_id=unexpected.id
        root_id=root.id
    observed=g64.start(db,ids)
    with TestClient(create_app(settings,database=db)) as client:
        response=client.post("/api/v1/auth/login",json={
            "username":ids["username"],"password":g64.PASSWORD,
        })
        assert response.status_code==200,response.text
        at=datetime.now(timezone.utc)-timedelta(minutes=3)
        g63.bom(client,rev_id,at,[
            (str(ids["article_id"]),"2",str(ids["uom_id"]),None,None),
        ])
        effect=at+timedelta(minutes=2)
        with db.session() as session:
            materials=MaterialsService(session)
            materials.post(MovementCreate(
                article_id=extra_id,location_id=ids["location_id"],
                uom_id=ids["uom_id"],kind="OPENING",quantity=Decimal("5"),
                source_system="G67_TEST",source_reference="UNPLANNED-OPEN",
                idempotency_key="G67-OPEN-"+suffix,
            ),ids["admin_id"],ids["username"])
            consumption=MaterialConsumptionService(session)
            consumption.record(ids["operation_id"],ConsumptionCreate(
                article_id=ids["article_id"],location_id=ids["location_id"],
                uom_id=ids["uom_id"],quantity=Decimal("2.5"),
                idempotency_key="G67-USE-"+suffix,
                evidence_reference="G67-ACTUAL-EXPECTED",
                observed_at=observed,
            ),ids["admin_id"],ids["username"])
            consumption.record(ids["operation_id"],ConsumptionCreate(
                article_id=extra_id,location_id=ids["location_id"],
                uom_id=ids["uom_id"],quantity=Decimal("1"),
                idempotency_key="G67-UNEXPECTED-"+suffix,
                evidence_reference="G67-ACTUAL-UNPLANNED",
                observed_at=observed,
            ),ids["admin_id"],ids["username"])
            stock_before=session.scalar(select(func.count(MaterialMovement.id)))
        projection=client.get(
            f"/api/v1/materials/projection/plans/{plan_id}",
            params={"plant_id":str(plant_id),"effective_at":effect.isoformat()},
        )
        assert projection.status_code==200,projection.text
        result=projection.json()
        assert result["bom_material_count"]==1
        assert result["unplanned_consumption_materials"]==1
        assert result["material_count"]==2
        expected=next(item for item in result["items"] if item["article_id"]==str(ids["article_id"]))
        actual_only=next(item for item in result["items"] if item["article_id"]==str(extra_id))
        assert expected["source_basis"]=="BOM"
        assert Decimal(expected["theoretical_plan_quantity"])==20
        assert Decimal(expected["actual_net_measured_consumption"])==Decimal("2.5")
        assert Decimal(expected["physical_on_hand"])==Decimal("7.5")
        assert Decimal(expected["theoretical_minus_measured"])==Decimal("17.5")
        assert actual_only["source_basis"]=="MEASURED_WITHOUT_BOM"
        assert Decimal(actual_only["theoretical_plan_quantity"])==0
        assert Decimal(actual_only["actual_net_measured_consumption"])==1
        assert Decimal(actual_only["physical_on_hand"])==4
        assert "MEASURED_MATERIAL_NOT_IN_EFFECTIVE_BOM" in actual_only["warnings"]
        with db.session() as session:
            assert session.scalar(select(func.count(MaterialMovement.id)))==stock_before
