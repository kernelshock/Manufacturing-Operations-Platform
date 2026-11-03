from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g5_2_execution_actuals_are_explicit_and_separate_from_planning() -> None:
    models = _read("src/mop/mes/models.py")
    service = _read("src/mop/mes/service.py")
    schemas = _read("src/mop/mes/schemas.py")
    api = _read("src/mop/api/v1/mes.py")
    migration = _read("migrations/versions/0026_g5_2_operation_execution.py")

    for required in (
        "actual_start",
        "actual_finish",
        "produced_quantity",
        "started_by",
        "completed_by",
        "ExecutionOperationEvent",
        "START",
        "COMPLETE",
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "mes.operation.start",
        "mes.operation.complete",
        "ExecutionStartCreate",
        "ExecutionCompleteCreate",
    ):
        assert required in models or required in service or required in schemas or required in api or required in migration

    for forbidden in (
        "scrap_quantity",
        "pause_started_at",
        "pause_finished_at",
        "setup_started_at",
        "setup_finished_at",
        "maintenance_work_order_id",
    ):
        assert forbidden not in models

    assert "execution operation can only start from a RELEASED dispatch" in service
    assert "execution operation can only complete from a RELEASED dispatch" in service
    assert "only PENDING execution operation can be started" in service
    assert "only RUNNING execution operation can be completed" in service
    assert "actual finish cannot precede actual start" in service
    assert "already completed with a different produced quantity" in service

    assert 'require_global_permission("mes.edit")' in api
    assert 'action="mes.operation.start"' in api
    assert 'action="mes.operation.complete"' in api


def test_g5_2_does_not_rewrite_g4_planned_evidence() -> None:
    service = _read("src/mop/mes/service.py")

    for forbidden in (
        "operation.planned_start =",
        "operation.planned_finish =",
        "operation.requested_quantity =",
        "publication.status =",
        "planning.planned_start =",
        "planning.planned_finish =",
        "planning.requested_quantity =",
    ):
        assert forbidden not in service
