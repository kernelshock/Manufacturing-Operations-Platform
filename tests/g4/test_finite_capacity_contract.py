from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_4_owns_planned_time_but_not_mes_actuals() -> None:
    model = _read("src/mop/aps/schedule_models.py")
    service = _read("src/mop/aps/service.py")

    for required in (
        "planned_start",
        "planned_finish",
        "resource_id",
        "ScheduledOperationSegment",
        'run.status = "SCHEDULED"',
        "_subtract_occupied",
        "insufficient finite capacity inside planning horizon",
    ):
        assert required in model or required in service

    for forbidden in (
        "actual_start",
        "actual_finish",
        "scrap_quantity",
        "actual_produced_quantity",
    ):
        assert forbidden not in model

    assert "unsupported temporal rate_uom" in service
    assert "resource.code" in service
