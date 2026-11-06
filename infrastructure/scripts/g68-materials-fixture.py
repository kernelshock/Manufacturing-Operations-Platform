"""G6.8 synthetic Materials acceptance on an isolated API + PostgreSQL stack.

The test helper source is loaded using only its fixture functions and imports:
no pytest or TestClient dependency is installed in the production API image.
No Prolowin captures or FAIC production data are read or modified.
"""
import ast
import importlib.util
import json
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from sqlalchemy import func, select
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self.text = body.decode("utf-8")
    def json(self):
        return json.loads(self.text)


class HttpClient:
    """Minimal compatible client that exercises the running FastAPI HTTP API."""
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method, path, json_value=None, params=None):
        url = "http://127.0.0.1:8000" + path
        if params:
            url += "?" + urlencode(params)
        payload = json.dumps(json_value).encode("utf-8") if json_value is not None else None
        req = Request(url, method=method, data=payload,
                      headers={"Content-Type": "application/json"} if payload else {})
        try:
            with self.opener.open(req, timeout=30) as r:
                return Response(r.status, r.read())
        except HTTPError as e:
            return Response(e.code, e.read())

    def post(self, path, json=None):
        return self.request("POST", path, json_value=json)

    def get(self, path, params=None):
        return self.request("GET", path, params=params)


def load_selected_fixture(filename, function_names):
    source = Path("/tmp/g68_fixture") / filename
    if not source.is_file():
        raise RuntimeError("Synthetic fixture helper missing: " + str(source))
    parsed = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    nodes = []
    for node in parsed.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "fastapi.testclient":
                continue
            if isinstance(node, ast.Import) and any(alias.name == "pytest" for alias in node.names):
                continue
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in function_names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PASSWORD"
            for target in node.targets
        ):
            nodes.append(node)
    present = {n.name for n in nodes if isinstance(n, ast.FunctionDef)}
    if present != set(function_names):
        raise RuntimeError(f"Fixture functions changed: missing {set(function_names)-present}")
    module = ModuleType(filename.removesuffix(".py"))
    module.__file__ = str(source)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), vars(module))
    return module


g63 = load_selected_fixture("test_material_requirements_integration.py",
                            {"write", "new_article", "rev", "bom", "add_line", "fixture"})
g65 = load_selected_fixture("test_reservations_integration.py",
                            {"setup", "auth", "post", "prepared", "hold_payload"})
g65.fixture_module = lambda: g63

settings, db, suffix, username, plant_id, _ = g65.setup()
client = HttpClient()
g65.auth(client, username)
data, loc, uom, effective = g65.prepared(client, db, suffix, plant_id, initial="20")
route = "/api/v1/materials/reservations"
g65.post(client, route, g65.hold_payload(data, loc, uom, effective, data["t1"], "6", "G68-H1-"+suffix))
g65.post(client, route, g65.hold_payload(data, loc, uom, effective, data["t2"], "10", "G68-H2-"+suffix))
with db.session() as session:
    movement_count = session.scalar(select(func.count(MaterialMovement.id)))
    reservation_count = session.scalar(select(func.count(MaterialReservationEvent.id)))
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
    assert session.scalar(select(func.count(MaterialMovement.id))) == movement_count
    assert session.scalar(select(func.count(MaterialReservationEvent.id))) == reservation_count
print("G68_MATERIALS_FIXTURE=" + json.dumps({
    "plan_id": data["plan"]["id"], "plan_number": data["plan"]["plan_number"],
    "plant_id": str(plant_id), "plant_code": "G65PLANT-"+suffix,
    "steel_code": steel["article_code"], "fabric_code": fabric["article_code"],
    "steel_id": data["material_x"], "fabric_id": data["material_y"],
    "effective_at": effective.isoformat(),
    "expected": {"materials": 2, "taquillas": 2, "unknown": 1, "gaps": 1,
                 "theoretical_steel": "37", "physical_steel": "20",
                 "held_steel": "16", "gross_gap_steel": "17"},
    "movement_count": movement_count, "reservation_count": reservation_count,
}, sort_keys=True))
