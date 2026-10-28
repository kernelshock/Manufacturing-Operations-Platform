import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "integrations/prolowin/contracts/complete-structure-batch.schema.json"

def load_schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))

def test_prolowin_contract_schema_is_valid_json_and_versioned():
    schema = load_schema()
    assert schema["$schema"].endswith("/2020-12/schema")
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert schema["properties"]["source_system"]["const"] == "PROLOWIN"
    assert schema["properties"]["report_type"]["const"] == "COMPLETE_ARTICLE_STRUCTURE"

def test_prolowin_contract_requires_source_root_and_rows():
    schema = load_schema()
    assert set(schema["required"]) == {
        "schema_version", "source_system", "report_type",
        "source", "root_article", "rows"
    }
    row = schema["properties"]["rows"]["items"]
    assert set(row["required"]) == {
        "row_no", "article_code", "operation_code",
        "description_raw", "quantity", "uom_raw"
    }
    assert row["properties"]["quantity"]["type"] == "string"
    assert schema["properties"]["source"]["properties"]["sha256"]["pattern"] == "^[a-fA-F0-9]{64}$"
