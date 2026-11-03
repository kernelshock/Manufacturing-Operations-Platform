from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_g5_4_wip_handoff_contract() -> None:
    models = _read("src/mop/mes/models.py")
    service = _read("src/mop/mes/service.py")
    schemas = _read("src/mop/mes/schemas.py")
    api = _read("src/mop/api/v1/mes.py")
    migration = _read("migrations/versions/0028_g5_4_wip_handoff.py")

    for required in (
        "ExecutionHandoff",
        "TRANSFERRED",
        "RECEIVED",
        "from_execution_operation_id",
        "to_execution_operation_id",
        "sequence_no",
        "quantity",
        "transfer_wip",
        "receive_handoff",
        "get_wip_trace",
        "HandoffTransferCreate",
        "HandoffReceiveCreate",
        "ExecutionWIPTraceRead",
        "mes.handoff.transfer",
        "mes.handoff.receive",
    ):
        assert required in models or required in service or required in schemas or required in api or required in migration

    assert "WIP handoff target must be the immediate execution successor" in service
    assert "WIP can only transfer from a COMPLETED predecessor" in service
    assert "WIP transfer quantity exceeds predecessor produced quantity" in service
    assert "execution successor requires received WIP from its immediate predecessor" in service

    for forbidden in (
        "inventory_balance_id",
        "warehouse_id",
        "stock_location_id",
        "purchase_order_id",
        "maintenance_work_order_id",
    ):
        assert forbidden not in models


def test_g5_4_wip_is_execution_trace_not_inventory_truth() -> None:
    service = _read("src/mop/mes/service.py")

    for forbidden in (
        "InventoryBalance",
        "Warehouse",
        "StockLocation",
        "on_hand_quantity",
        "available_stock",
    ):
        assert forbidden not in service
