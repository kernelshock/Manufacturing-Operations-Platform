"""G7.3: read-only, calendar-explicit interpretation of verified Prolowin samples.

Neither a full Prolowin census nor confirmed receipt at a plant. Returned
ratios describe only completed source lines in this bounded sample.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.master_data.models import (
    Article, ManufacturingCalendar, CalendarWeeklyWindow, CalendarException,
)
from mop.materials.service import MaterialsNotFound, MaterialsRule
from mop.planning.lead_time import BusinessCalendar, CompletedLine, sample_reliability
from mop.planning.reliability_schemas import SupplierLineMetric, SupplierReliabilityOverview
from mop.prolowin.procurement_models import ProcurementEvidenceEvent

ZERO = Decimal("0")


class SupplierReliabilityService:
    def __init__(self, session: Session):
        self.session = session

    def calendar(self, calendar_id: UUID, plant_id: UUID) -> tuple[BusinessCalendar, ZoneInfo]:
        row = self.session.get(ManufacturingCalendar, calendar_id)
        if row is None:
            raise MaterialsNotFound("manufacturing calendar not found")
        if row.status != "ACTIVE" or row.plant_id != plant_id:
            raise MaterialsRule("active plant-scoped calendar is required; no supplier calendar assumed")
        try:
            zone = ZoneInfo(row.timezone)
        except ZoneInfoNotFoundError as exc:
            raise MaterialsRule("calendar has invalid IANA timezone") from exc
        weekly = self.session.scalars(select(CalendarWeeklyWindow).where(
            CalendarWeeklyWindow.calendar_id == calendar_id,
            CalendarWeeklyWindow.active.is_(True),
        )).all()
        workdays = frozenset(w.weekday for w in weekly)
        exceptions = self.session.scalars(select(CalendarException).where(
            CalendarException.calendar_id == calendar_id,
            CalendarException.active.is_(True),
        )).all()
        closed = set()
        override = set()
        for ex in exceptions:
            if ex.exception_kind == "CLOSED":
                if ex.start_minute is not None:
                    raise MaterialsRule("partial-day closure cannot be treated as a full nonworking day")
                closed.add(ex.local_date)
            elif ex.exception_kind == "AVAILABLE_OVERRIDE":
                override.add(ex.local_date)
        try:
            return BusinessCalendar(
                code=row.code, timezone_name=row.timezone, workdays=workdays,
                closed_dates=frozenset(closed), override_dates=frozenset(override),
                valid_from=row.valid_from, valid_to=row.valid_to,
            ), zone
        except ValueError as exc:
            raise MaterialsRule(str(exc)) from exc

    def overview(self, plant_id: UUID, article_id: UUID, supplier_code: str,
                 calendar_id: UUID, as_of: datetime) -> SupplierReliabilityOverview:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise MaterialsRule("as_of requires timezone")
        if as_of > datetime.now(as_of.tzinfo):
            raise MaterialsRule("cannot include future Prolowin events")
        if not supplier_code or supplier_code != supplier_code.strip():
            raise MaterialsRule("supplier_code must be exact and nonblank")
        article = self.session.get(Article, article_id)
        if article is None:
            raise MaterialsNotFound("article not found")
        if not article.active or article.default_uom_id is None:
            raise MaterialsRule("canonical active article is required")
        cal, tz = self.calendar(calendar_id, plant_id)
        end_date = as_of.astimezone(tz).date()
        try:
            cal.is_workday(end_date)
        except ValueError as exc:
            raise MaterialsRule(str(exc)) from exc

        rows = list(self.session.scalars(select(ProcurementEvidenceEvent).where(
            ProcurementEvidenceEvent.review_status == "VERIFIED",
            ProcurementEvidenceEvent.mapped_article_id == article_id,
            ProcurementEvidenceEvent.mapped_uom_id == article.default_uom_id,
            ProcurementEvidenceEvent.supplier_code == supplier_code,
            ProcurementEvidenceEvent.event_date <= as_of,
        ).order_by(ProcurementEvidenceEvent.event_date, ProcurementEvidenceEvent.id)).all())
        groups = defaultdict(list)
        for row in rows:
            groups[(row.po_number, row.line_number)].append(row)

        lines = []
        complete = []
        for (po, line), events in sorted(groups.items()):
            orders = [e for e in events if e.kind == "ORDER"]
            if len(orders) != 1:
                # Missing original cannot contribute to a denominator or fake a lead time.
                continue
            order = orders[0]
            if order.quantity is None or order.original_promise_date is None:
                continue
            if any((e.supplier_code, e.article_code, e.uom_code) !=
                   (order.supplier_code, order.article_code, order.uom_code) for e in events):
                raise MaterialsRule("verified events contain conflicting order-line identity")
            receipts = [e for e in events if e.kind == "RECEIPT"]
            delivered = sum((e.quantity for e in receipts if e.quantity is not None), ZERO)
            if delivered > order.quantity:
                raise MaterialsRule("verified receipts exceed original purchase quantity")
            done = delivered == order.quantity
            final = max((e.event_date for e in receipts), default=None) if done else None
            first = min((e.event_date for e in receipts), default=None)
            rev = next((e.revised_promise_date for e in reversed(events)
                        if e.kind == "RESCHEDULE" and e.revised_promise_date), None)
            # All the original source events are timestamps with explicit zones.
            local = lambda dt: dt.astimezone(tz).date()
            try:
                orig_date = local(order.original_promise_date)
                order_date = local(order.event_date)
                revised_date = local(rev) if rev else None
                cal.days_between(order_date, orig_date)
                if revised_date is not None:
                    cal.is_workday(revised_date)
                actual = cal.days_between(order_date, local(final)) if final else None
                original_delay = (cal.days_between(orig_date, local(final))
                                  if final and local(final) > orig_date else 0 if done else None)
                revised_delay = (cal.days_between(revised_date, local(final))
                                 if rev and final and local(final) > revised_date
                                 else 0 if rev and done else None)
                if done:
                    effective = local(final)
                else:
                    effective = end_date
                orig_elapsed_delay = (cal.days_between(orig_date, effective)
                                      if effective > orig_date else 0)
                rev_elapsed_delay = (cal.days_between(revised_date, effective)
                                     if revised_date and effective > revised_date else 0)
            except ValueError as exc:
                raise MaterialsRule("unusable calendar for verified PO history: " + str(exc)) from exc
            original_status = ("LATE" if orig_elapsed_delay > 0 else
                               "ON_TIME" if done else "NOT_YET_DUE")
            revised_status = ("NOT_REPROGRAMMED" if rev is None else
                              "LATE" if rev_elapsed_delay > 0 else
                              "ON_TIME" if done else "NOT_YET_DUE")
            lines.append(SupplierLineMetric(
                po_number=po, line_number=line,
                original_promised_at=order.original_promise_date,
                latest_revised_at=rev,
                ordered=order.quantity, delivered_reported=delivered,
                outstanding_reported=order.quantity-delivered,
                partial_receipt_count=len(receipts),
                claims=sum(e.kind == "CLAIM" for e in events),
                production_risk_escalations=sum(e.kind == "ESCALATION" for e in events),
                first_receipt_at=first, final_receipt_at=final,
                actual_lead_time_business_days=actual,
                original_delay_business_days=original_delay,
                revised_delay_business_days=revised_delay,
                source_event_ids=[e.id for e in events],
                status="COMPLETED" if done else "OPEN",
                original_promise_status=original_status,
                revised_promise_status=revised_status,
            ))
            if final:
                complete.append(CompletedLine(
                    order_date, orig_date, revised_date, local(final),
                    len(receipts), sum(e.kind == "CLAIM" for e in events),
                    sum(e.kind == "ESCALATION" for e in events),
                ))
        sample = sample_reliability(cal, complete)
        lines.sort(key=lambda x: (x.po_number, x.line_number))
        return SupplierReliabilityOverview(
            supplier_code=supplier_code, article_id=article_id, calendar_id=calendar_id,
            calendar_code=cal.code, calendar_timezone=cal.timezone_name,
            evidence_cutoff_at=as_of, sample_size=len(lines),
            completed_lines=sample.completed, open_lines=len(lines)-sample.completed,
            late_against_original_completed=sample.late_original,
            late_against_revised_completed=sample.late_revised,
            on_time_original_sample_ratio=sample.on_time_original_sample_ratio,
            mean_actual_lead_business_days=sample.mean_actual_lead_days,
            observed_lead_std_business_days=sample.lead_time_population_std_days,
            mean_original_delay_business_days=sample.mean_original_delay_days,
            lines=lines,
            warnings=[
                "PARTIAL_PROLOWIN_MANUAL_CAPTURE_NOT_A_COMPLETE_SUPPLIER_CENSUS",
                "PLANT_CALENDAR_PROXY_NOT_VERIFIED_SUPPLIER_AGREEMENT",
                "BUSINESS_DAYS_EXCLUDE_ORDER_DATE_INCLUDE_RECEIPT_DATE",
                "ACTUAL_LEAD_TIME_ONLY_FOR_FULLY_REPORTED_RECEIPTS",
                "PROMISE_REVISIONS_DO_NOT_REPLACE_ORIGINAL_COMMITMENT",
                "OPEN_ORDERS_ARE_CENSORED_AND_EXCLUDED_FROM_COMPLETED_SAMPLE",
                "SAMPLE_RATIOS_NOT_STATISTICALLY_RELIABLE_OR_APPROVED_FOR_SAFETY_STOCK",
                "SOURCE_PO_LINE_NOT_PROVEN_PLANT_BOUND",
            ],
        )
