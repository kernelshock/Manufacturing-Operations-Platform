from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g4_6_gantt_is_read_only_projection_of_published_schedule() -> None:
    service = _read("src/mop/aps/service.py")
    schema = _read("src/mop/aps/gantt_schemas.py")
    api = _read("src/mop/api/v1/aps_gantt.py")

    for required in (
        'SchedulePublication.status == "CURRENT"',
        "PublishedScheduledOperation",
        "PublishedScheduledOperationSegment",
        "taquilla_code",
        "article_code",
        "resource_code",
        "work_center_code",
        "constraints_not_evaluated",
        'require_global_permission("aps.read")',
    ):
        assert required in service or required in schema or required in api

    for forbidden in (
        "planned_start =",
        "planned_finish =",
        "solve_finite_capacity(",
        "publish_schedule(",
    ):
        assert forbidden not in api
