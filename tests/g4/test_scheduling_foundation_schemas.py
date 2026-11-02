from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mop.aps.schemas import SchedulingScenarioCreate


def test_scenario_requires_ordered_timezone_aware_horizon() -> None:
    with pytest.raises(ValidationError):
        SchedulingScenarioCreate(plan_id=uuid4(), scenario_code="S1", name="Test", horizon_start=datetime(2026, 11, 2), horizon_end=datetime(2026, 11, 3), planning_timezone="America/Argentina/Cordoba")

    with pytest.raises(ValidationError):
        SchedulingScenarioCreate(plan_id=uuid4(), scenario_code="S1", name="Test", horizon_start=datetime(2026, 11, 3, tzinfo=timezone.utc), horizon_end=datetime(2026, 11, 2, tzinfo=timezone.utc), planning_timezone="America/Argentina/Cordoba")

    valid = SchedulingScenarioCreate(plan_id=uuid4(), scenario_code="S1", name="Test", horizon_start=datetime(2026, 11, 2, tzinfo=timezone.utc), horizon_end=datetime(2026, 11, 3, tzinfo=timezone.utc), planning_timezone="America/Argentina/Cordoba")
    assert valid.scenario_code == "S1"
