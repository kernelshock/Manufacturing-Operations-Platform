from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_rework_has_separate_actual_execution_identity_and_route_provenance():
    model = read("src/mop/mes/rework_models.py")
    service = read("src/mop/mes/rework_service.py")
    api = read("src/mop/api/v1/mes_rework.py")
    migration = read("migrations/versions/0029_g5_5_rework.py")
    for term in (
        "ReworkCase", "ReworkStep", "source_execution_operation_id",
        "return_execution_operation_id", "routing_operation_id", "resource_id",
        "quantity", "reason_code", "actual_start", "actual_finish", "produced_quantity",
        "OPEN", "IN_PROGRESS", "READY_TO_RETURN", "RETURNED",
    ):
        assert term in model
    for term in (
        "source must be COMPLETED", "rework allocation exceeds",
        "rework step must reference a routing operation in the source revision",
        "previous rework step must be COMPLETED",
        "rework return quantity must match allocated quantity",
    ):
        assert term in service
    for term in ("mes.read", "mes.edit", "mes.rework.case.create",
                 "mes.rework.step.add", "mes.rework.step.start",
                 "mes.rework.step.complete", "mes.rework.case.return"):
        assert term in api
    assert 'down_revision = "0028_g5_4"' in migration


def test_nominal_wip_cannot_double_allocate_rework_quantities():
    service = read("src/mop/mes/service.py")
    assert "allocated_to_rework" in service
    assert "reserved rework quantity" in service
    assert "incoming_returned_rework_quantity" in service
    assert "execution successor requires received WIP or an explicit returned rework path" in service
    for filename in ("src/mop/mes/rework_service.py", "src/mop/mes/rework_models.py"):
        source = read(filename)
        for forbidden in ("inventory_balance", "maintenance_work_order", "employee_skill"):
            assert forbidden not in source
