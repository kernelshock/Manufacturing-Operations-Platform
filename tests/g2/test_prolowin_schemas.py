import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from mop.prolowin.schemas import (
    ProlowinCompleteStructureImport,
    ProlowinDirectStructureImport,
)


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/prolowin/reference-corpus-metadata.json"


def _source(sha: str = "a" * 64) -> dict:
    return {
        "filename": "synthetic.json",
        "sha256": sha,
        "exported_at": "2026-10-28T09:46:00-03:00",
        "parser_version": "test-1",
    }


def test_complete_contract_requires_decimal_strings() -> None:
    payload = ProlowinCompleteStructureImport.model_validate(
        {
            "schema_version": "1.0.0",
            "source_system": "PROLOWIN",
            "report_type": "COMPLETE_ARTICLE_STRUCTURE",
            "source": _source(),
            "root_article": {
                "code": "X-6111",
                "quantity": "1.0000",
                "uom_raw": "UNID.",
            },
            "rows": [
                {
                    "row_no": 1,
                    "article_code": "X-6111",
                    "operation_code": "FIN",
                    "description_raw": "Apollo",
                    "quantity": "1.0000",
                    "uom_raw": "UNID.",
                }
            ],
        }
    )
    assert payload.root_article.quantity == Decimal("1.0000")
    assert payload.rows[0].quantity == Decimal("1.0000")

    invalid = payload.model_dump(mode="json")
    invalid["root_article"]["quantity"] = 1.0
    with pytest.raises(ValidationError):
        ProlowinCompleteStructureImport.model_validate(invalid)


def test_direct_contract_preserves_parent_child_identity() -> None:
    payload = ProlowinDirectStructureImport.model_validate(
        {
            "schema_version": "1.0.0",
            "source_system": "PROLOWIN",
            "report_type": "DIRECT_ARTICLE_STRUCTURE",
            "source": _source("b" * 64),
            "root_article_code": " x-6111 ",
            "relations": [
                {
                    "row_no": 1,
                    "sequence_no": 10,
                    "parent_article_code": " x-6111 ",
                    "parent_description_raw": "Apollo",
                    "child_article_code": " a-621 ",
                    "child_description_raw": "Respaldo",
                    "quantity": "2.0000",
                    "uom_raw": "UNID.",
                }
            ],
        }
    )

    assert payload.root_article_code == "X-6111"
    assert payload.relations[0].parent_article_code == "X-6111"
    assert payload.relations[0].child_article_code == "A-621"


def test_reference_corpus_metadata_covers_all_five_products_and_fin_invariant() -> None:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    products = {item["code"]: item for item in data["products"]}

    assert set(products) == {
        "X-1148",
        "X-1149",
        "X-2209",
        "X-6111",
        "X-7070",
    }
    for item in products.values():
        assert item["fin_rows"] == item["unique_article_codes"]
        assert item["source_rows"] == (
            item["fin_rows"] + item["non_fin_rows"]
        )

    assert data["x6111_trace"] == {
        "article_code": "14027",
        "description": "ALAMBRE CHICO RESPALDO MB F10",
        "quantity": "6.0000",
        "uom_raw": "UNID.",
    }
