import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/prolowin/reference-corpus-metadata.json"


def test_g2_reference_corpus_counts_remain_locked() -> None:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    actual = {
        item["code"]: (
            item["pages"],
            item["source_rows"],
            item["unique_article_codes"],
            item["fin_rows"],
            item["non_fin_rows"],
            item["multistage_codes"],
        )
        for item in data["products"]
    }
    assert actual == {
        "X-1148": (7, 230, 194, 194, 36, 20),
        "X-1149": (7, 222, 186, 186, 36, 20),
        "X-2209": (6, 210, 187, 187, 23, 16),
        "X-6111": (5, 175, 147, 147, 28, 20),
        "X-7070": (5, 172, 149, 149, 23, 18),
    }
