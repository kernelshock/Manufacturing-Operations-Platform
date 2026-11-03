"""G5.6 regression: no fabricated actuals, conservative classification, read-only API."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from mop.mes.feedback_service import FeedbackService, classify_operation

ROOT = Path(__file__).resolve().parents[2]


def operation(status: str, finish_offset: int | None = None):
    planned = datetime(2026, 11, 3, 14, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid4(), published_operation_id=uuid4(), plan_id=uuid4(),
        taquilla_id=uuid4(), product_line_id=uuid4(), routing_operation_id=uuid4(),
        planned_start=planned-timedelta(hours=2), planned_finish=planned,
        status=status,
        actual_start=planned-timedelta(hours=1) if status != "PENDING" else None,
        actual_finish=planned+timedelta(minutes=finish_offset) if finish_offset is not None else None,
        requested_quantity=Decimal("9.5"),
        produced_quantity=Decimal("9.0") if status == "COMPLETED" else None,
        planned_resource_id=uuid4(), actual_resource_id=None,
    )


def test_operation_classification_requires_explicit_completion():
    assert classify_operation(operation("PENDING")) == "NOT_STARTED"
    assert classify_operation(operation("RUNNING")) == "IN_PROGRESS"
    assert classify_operation(operation("PAUSED")) == "IN_PROGRESS"
    assert classify_operation(operation("COMPLETED", -2)) == "ON_TIME"
    assert classify_operation(operation("COMPLETED", 0)) == "ON_TIME"
    assert classify_operation(operation("COMPLETED", 3)) == "DELAYED"


def test_observation_preserves_unknown_actuals_and_decimal_quantity():
    pending = FeedbackService._operation_feedback(operation("PENDING"))
    assert pending.actual_finish is None and pending.produced_quantity is None
    assert pending.finish_delta_seconds is None and pending.quantity_delta is None
    completed = FeedbackService._operation_feedback(operation("COMPLETED", 3))
    assert completed.finish_delta_seconds == Decimal("180")
    assert completed.quantity_delta == Decimal("-0.5")
    assert completed.resource_deviation is None


def test_feedback_does_not_write_to_aps_or_infer_root_causes():
    source = (ROOT / "src/mop/mes/feedback_service.py").read_text(encoding="utf-8")
    api = (ROOT / "src/mop/api/v1/mes_feedback.py").read_text(encoding="utf-8")
    assert "session.commit(" not in source
    assert "session.add(" not in source
    assert "SchedulePublication" not in source
    assert "require_global_permission(\"mes.read\")" in api
    assert "@router.post" not in api
    assert "@router.put" not in api
    assert "@router.patch" not in api
