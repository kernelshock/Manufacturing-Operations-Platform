from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_3_capacity_projection_preserves_planning_boundary() -> None:
    model = _read("src/mop/aps/capacity_models.py")
    service = _read("src/mop/aps/service.py")

    for required in (
        "EXPLICIT_ASSIGNMENT",
        "WORK_CENTER_POOL",
        "calendar_capacity_factor",
        "assignment_capacity_factor",
        "ResourceAvailabilityInterval",
        'run.status = "CAPACITY_PROJECTED"',
        "resolve_calendar_availability",
    ):
        assert required in model or required in service

    for forbidden in (
        "planned_start",
        "planned_finish",
        "actual_start",
        "actual_finish",
        "produced_quantity",
        "scrap_quantity",
    ):
        assert forbidden not in model

    assert "CalendarWeeklyWindow" in service
    assert "CalendarException" in service
    assert "ZoneInfo" in service
