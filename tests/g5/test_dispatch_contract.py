from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g5_1_dispatch_foundation_preserves_ownership_boundaries() -> None:
    models = _read("src/mop/mes/models.py")
    service = _read("src/mop/mes/service.py")
    api = _read("src/mop/api/v1/mes.py")
    migration = _read("migrations/versions/0025_g5_1_execution_dispatch.py")

    for required in (
        "ExecutionDispatch",
        "ExecutionOperation",
        "publication_id",
        "published_operation_id",
        "planning_operation_id",
        "planned_resource_id",
        "planned_start",
        "planned_finish",
        "schedule_fingerprint",
        "DRAFT",
        "RELEASED",
        "CANCELLED",
        "mes.read",
        "mes.edit",
        "mes.dispatch.create",
        "mes.dispatch.release",
        "mes.dispatch.cancel",
    ):
        assert required in models or required in service or required in api or required in migration

    for forbidden in (
        "actual_start",
        "actual_finish",
        "produced_quantity",
        "scrap_quantity",
        "pause_started_at",
        "setup_started_at",
        "operator_id",
        "actual_resource_id",
    ):
        assert forbidden not in models

    assert "execution dispatch can only be created from a CURRENT publication" in service
    assert "cannot release dispatch because its source publication is no longer CURRENT" in service
    assert 'require_global_permission("mes.read")' in api
    assert 'require_global_permission("mes.edit")' in api


def test_g5_1_never_mutates_aps_or_demand_source_state() -> None:
    service = _read("src/mop/mes/service.py")
    for forbidden in (
        "publication.status =",
        "planning.planned_start =",
        "planning.planned_finish =",
        "requested_quantity = data",
        "TaquillaProductLine.requested_quantity =",
        "SchedulingRun.status =",
    ):
        assert forbidden not in service
