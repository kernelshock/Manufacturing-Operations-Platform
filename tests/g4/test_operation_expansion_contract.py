from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_2_preserves_full_operation_provenance_without_schedule_state() -> None:
    model = _read("src/mop/aps/operation_models.py")
    service = _read("src/mop/aps/service.py")

    for field in (
        "plan_id",
        "taquilla_id",
        "product_line_id",
        "article_id",
        "routing_revision_id",
        "routing_operation_id",
        "requested_quantity",
        "routing_sequence_no",
        "routing_source_fingerprint",
    ):
        assert field in model

    for forbidden in (
        "planned_start",
        "planned_finish",
        "actual_start",
        "actual_finish",
        "produced_quantity",
        "scrap_quantity",
    ):
        assert forbidden not in model

    assert 'run.status = "EXPANDED"' in service
    assert "input_fingerprint" in service
    assert "idempotent" not in service.lower() or "EXPANDED" in service
