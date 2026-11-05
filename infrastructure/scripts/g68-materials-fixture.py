"""G6.8 synthetic dashboard fixture, run only inside disposable runtime CI database.

Reuses the already-covered G6.3/G6.5 fixture factories copied into /tmp/g68_fixture.
It creates no production or Prolowin source record.
"""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from sqlalchemy import func, select
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent

path = Path("/tmp/g68_fixture/test_reservations_integration.py")
if not path.is_file():
    raise RuntimeError("G6 synthetic helper is missing from disposable runtime container")
spec = importlib.util.spec_from_file_location("g68_material_fixture", path)
assert spec and spec.loader
g65 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g65)

from fastapi.testclient import TestClient
from mop.application import create_app

settings, db, suffix, username, plant_id, _ = g65.setup()
with TestClient(create_app(settings, database=db)) as client:
    g65.auth(client, username)
    data, loc, uom, effective = g65.prepared(client, db, suffix, plant_id, initial="20")
    path = "/api/v1/materials/reservations"
    g65.post(client, path, g65.hold_payload(data, loc, uom, effective, data["t1"], "6", "G68-H1-"+suffix))
    g65.post(client, path, g65.hold_payload(data, loc, uom, effective, data["t2"], "10", "G68-H2-"+suffix))
    with db.session() as session:
        before_movements = session.scalar(select(func.count(MaterialMovement.id)))
        before_holds = session.scalar(select(func.count(MaterialReservationEvent.id)))
    response = client.get(
        "/api/v1/materials/projection/plans/" + data["plan"]["id"],
        params={"plant_id": str(plant_id), "effective_at": effective.isoformat()},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    by_id = {x["article_id"]: x for x in result["items"]}
    assert len(result["items"]) == 2
    assert result["source_taquillas"] == 2
    assert result["excluded_cancelled_taquillas"] == [data["t3"]["id"]]
    steel = by_id[data["material_x"]]
    fabric = by_id[data["material_y"]]
    assert Decimal(steel["theoretical_plan_quantity"]) == 37
    assert Decimal(steel["physical_on_hand"]) == 20
    assert Decimal(steel["reserved_all_plans"]) == 16
    assert Decimal(steel["provisional_gross_gap"]) == 17
    assert fabric["physical_on_hand"] is None and fabric["stock_state"] == "UNKNOWN"
    with db.session() as session:
        assert session.scalar(select(func.count(MaterialMovement.id))) == before_movements
        assert session.scalar(select(func.count(MaterialReservationEvent.id))) == before_holds
    print("G68_MATERIALS_FIXTURE=" + json.dumps({
        "plan_id": data["plan"]["id"],
        "plan_number": data["plan"]["plan_number"],
        "plant_id": str(plant_id),
        "plant_code": "G65PLANT-"+suffix,
        "steel_code": steel["article_code"],
        "fabric_code": fabric["article_code"],
        "steel_id": data["material_x"],
        "fabric_id": data["material_y"],
        "effective_at": effective.isoformat(),
        "expected": {"materials": 2, "taquillas": 2, "unknown": 1, "gaps": 1,
                     "theoretical_steel": "37", "physical_steel": "20",
                     "held_steel": "16", "gross_gap_steel": "17"},
        "movement_count": before_movements, "reservation_count": before_holds,
    }, sort_keys=True))
