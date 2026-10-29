from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mop.master_data.schemas import (
    CalendarExceptionCreate,
    CalendarWeeklyWindowCreate,
    ManufacturingCalendarCreate,
)


def test_calendar_requires_one_target_and_valid_timezone() -> None:
    with pytest.raises(ValidationError):
        ManufacturingCalendarCreate(
            code="FAIC",
            name="FAIC",
            revision_no=1,
            timezone="Not/A_Timezone",
            plant_id=uuid4(),
            valid_from=date(2026, 11, 1),
        )

    with pytest.raises(ValidationError):
        ManufacturingCalendarCreate(
            code="FAIC",
            name="FAIC",
            revision_no=1,
            timezone="America/Argentina/Cordoba",
            plant_id=uuid4(),
            area_id=uuid4(),
            valid_from=date(2026, 11, 1),
        )


def test_weekly_window_supports_same_day_and_overnight() -> None:
    day = CalendarWeeklyWindowCreate(
        weekday=0,
        start_minute=420,
        end_minute=960,
        capacity_factor=Decimal("1"),
    )
    night = CalendarWeeklyWindowCreate(
        weekday=4,
        start_minute=1320,
        end_minute=360,
        spans_midnight=True,
        capacity_factor=Decimal("0.75"),
    )

    assert day.spans_midnight is False
    assert night.spans_midnight is True

    with pytest.raises(ValidationError):
        CalendarWeeklyWindowCreate(
            weekday=0,
            start_minute=960,
            end_minute=420,
        )


def test_calendar_exception_semantics_are_explicit() -> None:
    closed = CalendarExceptionCreate(
        local_date=date(2026, 12, 25),
        exception_kind="CLOSED",
        reason="Holiday",
    )
    override = CalendarExceptionCreate(
        local_date=date(2026, 12, 26),
        exception_kind="AVAILABLE_OVERRIDE",
        start_minute=480,
        end_minute=720,
        capacity_factor=Decimal("0.5"),
    )

    assert closed.capacity_factor is None
    assert override.capacity_factor == Decimal("0.5")

    with pytest.raises(ValidationError):
        CalendarExceptionCreate(
            local_date=date(2026, 12, 25),
            exception_kind="AVAILABLE_OVERRIDE",
            start_minute=480,
            end_minute=720,
        )
