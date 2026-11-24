"""G7.2 read-only supply position. NEVER infer Quality release, ATP or PO receipts.

Physical is a *current* G6 ledger snapshot. The cutoff restricts manually verified
Prolowin events only, NOT the physical historical balance or its posted timestamps.
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mop.core.models import Plant
from mop.master_data.models import Article
from mop.materials.models import MaterialLocation, MaterialMovement, MaterialWarehouse
from mop.materials.reservation_models import MaterialReservationEvent
from mop.materials.service import MaterialsNotFound, MaterialsRule
from mop.planning.position_schemas import PositionLocation, PositionSnapshot, VerifiedOrderLine
from mop.prolowin.procurement_models import ProcurementEvidenceEvent

ZERO = Decimal("0")


class SupplyPositionService:
    def __init__(self, session: Session):
        self.session = session

    def snapshot(self, plant_id: UUID, article_id: UUID, evidence_cutoff_at: datetime) -> PositionSnapshot:
        if evidence_cutoff_at.tzinfo is None or evidence_cutoff_at.utcoffset() is None:
            raise MaterialsRule("evidence_cutoff_at requires timezone")
        snapshot_at = datetime.now(timezone.utc)
        if evidence_cutoff_at > snapshot_at:
            raise MaterialsRule("future evidence cutoff is not supported; this is not a forecast")
        plant = self.session.get(Plant, plant_id)
        if plant is None:
            raise MaterialsNotFound("plant not found")
        if not plant.active:
            raise MaterialsRule("plant is inactive")
        article = self.session.get(Article, article_id)
        if article is None:
            raise MaterialsNotFound("article not found")
        if not article.active or article.default_uom_id is None:
            raise MaterialsRule("active canonical article and unit required")

        sites = self.session.execute(
            select(MaterialLocation.id, MaterialWarehouse.code, MaterialLocation.code)
            .join(MaterialWarehouse, MaterialWarehouse.id == MaterialLocation.warehouse_id)
            .where(MaterialWarehouse.plant_id == plant_id, MaterialWarehouse.active.is_(True),
                   MaterialLocation.active.is_(True))
            .order_by(MaterialWarehouse.code, MaterialLocation.code)
        ).all()
        ids = [loc_id for loc_id, _, _ in sites]
        balances = {}
        holds = {}
        if ids:
            balances = {
                loc: (Decimal(q), unit)
                for loc, q, unit in self.session.execute(
                    select(MaterialMovement.location_id,
                           func.sum(MaterialMovement.signed_quantity),
                           MaterialMovement.uom_id)
                    .where(MaterialMovement.article_id == article_id,
                           MaterialMovement.location_id.in_(ids))
                    .group_by(MaterialMovement.location_id, MaterialMovement.uom_id)
                )
            }
            holds = {
                loc: Decimal(q)
                for loc, q in self.session.execute(
                    select(MaterialReservationEvent.location_id,
                           func.sum(MaterialReservationEvent.signed_quantity))
                    .where(MaterialReservationEvent.article_id == article_id,
                           MaterialReservationEvent.location_id.in_(ids))
                    .group_by(MaterialReservationEvent.location_id)
                )
            }

        known = bool(sites)
        physical_total = ZERO
        held_total = ZERO
        location_lines = []
        for loc_id, wh_code, loc_code in sites:
            stock = balances.get(loc_id)
            quantity = stock[0] if stock else None
            if stock and stock[1] != article.default_uom_id:
                raise MaterialsRule("stock UoM differs from canonical article unit")
            reserved = holds.get(loc_id, ZERO)
            if quantity is None:
                known = False
                if reserved != ZERO:
                    raise MaterialsRule("UNKNOWN location cannot have active holds")
            else:
                physical_total += quantity
                if reserved > quantity or reserved < ZERO:
                    raise MaterialsRule("inconsistent physical/held material position")
            held_total += reserved
            location_lines.append(PositionLocation(
                location_id=loc_id, warehouse_code=wh_code, location_code=loc_code,
                physical_on_hand=quantity, committed_holds=reserved,
                unallocated_physical=quantity - reserved if quantity is not None else None,
                state="KNOWN" if quantity is not None else "UNKNOWN",
            ))

        # Source events are independently VERIFIED, but the history is still only a
        # sample of manually captured Prolowin. Never assume it is a complete ERP.
        rows = list(self.session.scalars(
            select(ProcurementEvidenceEvent).where(
                ProcurementEvidenceEvent.mapped_article_id == article_id,
                ProcurementEvidenceEvent.mapped_uom_id == article.default_uom_id,
                ProcurementEvidenceEvent.review_status == "VERIFIED",
                ProcurementEvidenceEvent.event_date <= evidence_cutoff_at,
            ).order_by(ProcurementEvidenceEvent.event_date,
                       ProcurementEvidenceEvent.id)
        ).all())
        events_by_line = defaultdict(list)
        for event in rows:
            events_by_line[(event.po_number, event.line_number)].append(event)

        open_lines = []
        for (po, line_no), events in sorted(events_by_line.items()):
            orders = [e for e in events if e.kind == "ORDER"]
            if len(orders) != 1:
                # Manual history incomplete: never infer outstanding from a receipt alone.
                continue
            order = orders[0]
            if order.quantity is None or order.original_promise_date is None:
                continue
            if any((e.supplier_code, e.article_code, e.uom_code) != (
                order.supplier_code, order.article_code, order.uom_code
            ) for e in events):
                raise MaterialsRule("verified purchase line contains inconsistent identities")
            received = sum((e.quantity for e in events if e.kind == "RECEIPT"), ZERO)
            if received > order.quantity:
                raise MaterialsRule("verified receipt exceeds purchase order")
            remain = order.quantity - received
            if remain == ZERO:
                continue
            receipts = [e for e in events if e.kind == "RECEIPT"]
            accepted = (sum((e.accepted_quantity for e in receipts), ZERO)
                        if receipts and all(e.accepted_quantity is not None for e in receipts)
                        else None)
            revisions = [e for e in events if e.kind == "RESCHEDULE" and e.revised_promise_date]
            revised = revisions[-1].revised_promise_date if revisions else None
            open_lines.append(VerifiedOrderLine(
                po_number=po, line_number=line_no, supplier_code=order.supplier_code,
                original_promise_at=order.original_promise_date,
                revised_promise_at=revised,
                effective_promise_at=revised or order.original_promise_date,
                ordered=order.quantity, received_reported=received,
                accepted_reported=accepted, outstanding_reported=remain,
                receipt_count=len(receipts), evidence_event_ids=[e.id for e in events],
            ))
        open_lines.sort(key=lambda x: (x.effective_promise_at, x.po_number, x.line_number))

        physical = physical_total if known else None
        return PositionSnapshot(
            plant_id=plant_id, article_id=article_id, uom_id=article.default_uom_id,
            snapshot_at=snapshot_at, evidence_cutoff_at=evidence_cutoff_at,
            physical_on_hand=physical, physical_state="KNOWN" if known else "UNKNOWN",
            committed_holds=held_total,
            unallocated_physical=physical - held_total if physical is not None else None,
            verified_open_order_sample=sum((line.outstanding_reported for line in open_lines), ZERO)
                                       if rows else None,
            supplier_evidence_state="PARTIAL_VERIFIED_MANUAL" if rows else "UNKNOWN",
            location_breakdown=location_lines, order_lines=open_lines,
            warnings=[
                "PHYSICAL_IS_CURRENT_POSTED_LEDGER_NOT_HISTORICAL_AS_OF",
                "QUALITY_USABLE_UNKNOWN_UNTIL_EVIDENCED_RELEASE",
                "PROLOWIN_VERIFIED_MANUAL_HISTORY_IS_PARTIAL",
                "RECEIPT_TRANSCRIPT_IS_NOT_PHYSICAL_STOCK",
                "PENDING_PO_IS_NOT_CONFIRMED_IN_TRANSIT_OR_ATP",
                "ORDERS_ARE_NOT_PLANT_ASSIGNED_IN_LEGACY_EVIDENCE",
                "DUE_DATES_ARE_PROMISES_NOT_CONFIRMED_RECEIPTS",
            ] + (["UNKNOWN_STOCK_IN_ACTIVE_LOCATION"] if not known else []),
        )
