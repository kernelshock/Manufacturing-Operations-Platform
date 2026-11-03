from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g5_3_setup_interruption_and_deviation_contract() -> None:
    models = _read("src/mop/mes/models.py")
    service = _read("src/mop/mes/service.py")
    schemas = _read("src/mop/mes/schemas.py")
    api = _read("src/mop/api/v1/mes.py")
    migration = _read("migrations/versions/0027_g5_3_setup_interruption.py")

    for required in (
        "ExecutionSetup",
        "ExecutionInterruption",
        "PAUSED",
        "actual_resource_id",
        "resource_deviation_reason",
        "uq_mes_execution_open_interruption",
        "start_setup",
        "finish_setup",
        "pause_operation",
        "resume_operation",
        "get_deviation",
        "SetupStartCreate",
        "InterruptionStartCreate",
        "ExecutionDeviationRead",
        "mes.operation.setup.start",
        "mes.operation.setup.finish",
        "mes.operation.pause",
        "mes.operation.resume",
    ):
        assert required in models or required in service or required in schemas or required in api or required in migration

    for forbidden in (
        "maintenance_work_order_id",
        "employee_skill_id",
        "inventory_balance_id",
        "purchase_order_id",
        "scrap_quantity",
    ):
        assert forbidden not in models

    assert "setup can only start while execution operation is PENDING" in service
    assert "execution operation cannot start while setup is still open" in service
    assert "only RUNNING execution operation can be paused" in service
    assert "execution operation has no open interruption to resume" in service
    assert "resource deviation reason is required when actual resource differs from planned resource" in service


def test_g5_3_deviation_projection_is_observational_not_causal_classification() -> None:
    service = _read("src/mop/mes/service.py")

    for required in (
        "start_delta_seconds",
        "finish_delta_seconds",
        "quantity_delta",
        "setup_seconds",
        "interruption_seconds",
        "resource_deviation",
    ):
        assert required in service

    for forbidden in (
        "maintenance_delay",
        "material_delay",
        "workforce_delay",
        "automatic_delay_classification",
    ):
        assert forbidden not in service.lower()
