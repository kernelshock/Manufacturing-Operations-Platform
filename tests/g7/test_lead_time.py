"""G7.3 pure business-day and sampled reliability acceptance."""
from datetime import date
from decimal import Decimal

import pytest

from mop.planning.lead_time import BusinessCalendar, CompletedLine, sample_reliability
from mop.planning.policy_contracts import PolicyError


def cal(**kwargs):
    args = dict(code="SYNTHETIC", timezone_name="America/Argentina/Cordoba",
                workdays=frozenset(range(5)),
                closed_dates=frozenset({date(2026,10,12)}),
                override_dates=frozenset(),
                valid_from=date(2026,1,1))
    args.update(kwargs)
    return BusinessCalendar(**args)


def test_weekends_holidays_and_explicit_override():
    # Monday October 5 to Friday October 16; October 12 is explicitly CLOSED.
    assert cal().days_between(date(2026,10,5),date(2026,10,16))==8
    assert cal().days_between(date(2026,10,5),date(2026,10,5))==0
    assert cal().days_between(date(2026,10,9),date(2026,10,13))==1
    assert cal(override_dates=frozenset({date(2026,10,10)})).days_between(
        date(2026,10,9),date(2026,10,13))==2
    assert cal().is_workday(date(2026,10,12)) is False
    assert cal().is_workday(date(2026,10,10)) is False


def test_full_delivery_late_and_original_promise_immutable():
    line=CompletedLine(order_date=date(2026,10,5),promised_original=date(2026,10,9),
                       promised_revised=date(2026,10,15),final_receipt_date=date(2026,10,16),
                       receipt_count=2,claims=1,escalations=0)
    stats=sample_reliability(cal(),[line])
    assert stats.completed==1
    assert stats.late_original==1
    assert stats.late_revised==1
    assert stats.mean_actual_lead_days==Decimal("8")
    assert stats.mean_original_delay_days==Decimal("4")
    assert stats.on_time_original_sample_ratio==0
    assert stats.lead_time_population_std_days is None


def test_exact_decimal_std_population_without_floats():
    lines=[CompletedLine(date(2026,10,5),date(2026,10,9),None,end,1,0,0)
           for end in (date(2026,10,9),date(2026,10,16))]
    result=sample_reliability(cal(),lines)
    assert result.mean_actual_lead_days==Decimal("6")
    assert result.lead_time_population_std_days==Decimal("2")
    assert result.late_revised is None


def test_empty_sample_is_unknown_not_perfect_reliability():
    r=sample_reliability(cal(),[])
    assert r.completed==0
    assert r.on_time_original_sample_ratio is None
    assert r.mean_actual_lead_days is None
    assert r.lead_time_population_std_days is None


@pytest.mark.parametrize("kwargs",[
    {"workdays":frozenset()},
    {"workdays":frozenset({7})},
    {"code":" "},
    {"closed_dates":frozenset({date(2026,10,10)}),
     "override_dates":frozenset({date(2026,10,10)})},
])
def test_invalid_calendar_fails_closed(kwargs):
    with pytest.raises(PolicyError):
        cal(**kwargs)


def test_calendar_expiration_and_backward_receipts_fail_closed():
    with pytest.raises(PolicyError):
        cal(valid_from=date(2026,10,6)).days_between(date(2026,10,5),date(2026,10,10))
    with pytest.raises(PolicyError):
        cal(valid_to=date(2026,10,10)).days_between(date(2026,10,5),date(2026,10,16))
    with pytest.raises(PolicyError):
        cal().days_between(date(2026,10,16),date(2026,10,5))
