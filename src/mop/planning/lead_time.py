"""G7.3 business-day calendar and supplier service metrics, pure and deterministic.

Business days are local calendar dates, excluding the order date and including
the receipt/commitment date. No timestamp-precision or supplier acceptance is
inferred from the source records.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, pstdev

from mop.planning.policy_contracts import PolicyError


@dataclass(frozen=True)
class BusinessCalendar:
    code: str
    timezone_name: str
    workdays: frozenset[int]
    closed_dates: frozenset[date] = frozenset()
    override_dates: frozenset[date] = frozenset()
    valid_from: date | None = None
    valid_to: date | None = None

    def __post_init__(self):
        if not self.code.strip() or not self.timezone_name.strip():
            raise PolicyError("calendar code and timezone required")
        if not self.workdays or any(not isinstance(d, int) or d not in range(7) for d in self.workdays):
            raise PolicyError("calendar must have explicit weekdays 0..6")
        if self.closed_dates & self.override_dates:
            raise PolicyError("contradictory closed and available exceptions")

    def is_workday(self, day: date) -> bool:
        if self.valid_from and day < self.valid_from:
            raise PolicyError("calendar not effective for requested historical date")
        if self.valid_to and day >= self.valid_to:
            raise PolicyError("calendar revision expired for requested historical date")
        if day in self.closed_dates:
            return False
        return day in self.override_dates or day.weekday() in self.workdays

    def days_between(self, start: date, end: date) -> int:
        if end < start:
            raise PolicyError("supplier receipt/commitment predates original order")
        # Validate both endpoints even on same-day transactions.
        self.is_workday(start)
        self.is_workday(end)
        if (end - start).days > 3660:
            raise PolicyError("calendar span exceeds 10 years")
        cur = start
        count = 0
        while cur < end:
            cur += timedelta(days=1)
            count += int(self.is_workday(cur))
        return count


@dataclass(frozen=True)
class CompletedLine:
    order_date: date
    promised_original: date
    promised_revised: date | None
    final_receipt_date: date
    receipt_count: int
    claims: int
    escalations: int


@dataclass(frozen=True)
class SupplierSampleStats:
    completed: int
    late_original: int
    late_revised: int | None
    on_time_original_sample_ratio: Decimal | None
    mean_actual_lead_days: Decimal | None
    lead_time_population_std_days: Decimal | None
    mean_original_delay_days: Decimal | None


def sample_reliability(calendar: BusinessCalendar, lines: list[CompletedLine]) -> SupplierSampleStats:
    if not lines:
        return SupplierSampleStats(0, 0, None, None, None, None, None)
    actual = [calendar.days_between(x.order_date, x.final_receipt_date) for x in lines]
    late_original = [
        calendar.days_between(x.promised_original, x.final_receipt_date)
        if x.final_receipt_date > x.promised_original else 0 for x in lines
    ]
    revised = [x for x in lines if x.promised_revised is not None]
    late_revised = sum(
        x.final_receipt_date > x.promised_revised
        and calendar.days_between(x.promised_revised, x.final_receipt_date) > 0
        for x in revised
    ) if revised else None
    def decimal_average(values):
        return sum((Decimal(v) for v in values), Decimal(0)) / Decimal(len(values))
    avg = decimal_average(actual)
    std = Decimal(str(pstdev(actual))) if len(actual) > 1 else None
    return SupplierSampleStats(
        completed=len(lines),
        late_original=sum(v > 0 for v in late_original),
        late_revised=late_revised,
        on_time_original_sample_ratio=Decimal(sum(v == 0 for v in late_original)) / Decimal(len(lines)),
        mean_actual_lead_days=avg,
        lead_time_population_std_days=std,
        mean_original_delay_days=decimal_average(late_original),
    )
