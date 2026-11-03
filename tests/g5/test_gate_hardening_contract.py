"""G5.8 gate regressions for frontend/backend integration boundaries.

These contract checks supplement, but DO NOT replace, browser E2E acceptance.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mes_shopfloor_is_permission_gated_and_uses_versioned_api():
    navigation = source("frontend/src/lib/permissions.ts")
    shell = source("frontend/src/shell/AppShell.tsx")
    panel = source("frontend/src/shell/MESPanel.tsx")
    assert 'requiredAny: ["mes.read", "mes.edit"]' in navigation
    assert 'user.permissions.includes("mes.edit")' in shell
    assert '"/api/v1/mes"' in panel
    assert "apiFetch<Dispatch[]>" in panel
    assert "apiFetch<Operation[]>" in panel
    assert 'dispatch?.status !== "RELEASED"' in panel
    assert 'if (!selected || !canEdit' in panel


def test_mes_capture_requires_explicit_quantity_and_pause_reason():
    panel = source("frontend/src/shell/MESPanel.tsx")
    for term in (
        'action === "complete"',
        'produced_quantity: quantity',
        'Number(quantity) <= 0',
        'action === "pause"',
        'reason_code: reason.trim()',
        'idempotent_replay',
    ):
        assert term in panel


def test_g5_feedback_does_not_write_published_aps_data():
    feedback = source("src/mop/mes/feedback_service.py")
    for forbidden in ("session.commit(", "session.add(", "SchedulePublication", "PublishedScheduledOperation"):
        assert forbidden not in feedback
    for expected in ("requested_quantity", "actual_finish", "planned_finish", "quantity_delta", "open_rework_count"):
        assert expected in feedback


def test_mes_rework_and_wip_are_canonical_not_inventory_truth():
    rework = source("src/mop/mes/rework_service.py")
    service = source("src/mop/mes/service.py")
    assert "rework allocation exceeds untransferred produced quantity" in rework
    assert "reserved rework quantity" in service
    assert "execution successor requires received WIP or an explicit returned rework path" in service
    for forbidden in ("inventory_balance", "maintenance_work_order", "employee_skill"):
        assert forbidden not in rework
