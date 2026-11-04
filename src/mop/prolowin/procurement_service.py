"""G6.6 — manual/screenshot Prolowin purchasing evidence; never alters G6 stock.

No Prolowin connection, OCR dependency, Excel schema, automatic purchase
decisions or inferred receipt are required. Human review is mandatory.
"""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry
from mop.master_data.models import Article, Supplier, SupplierSourceMapping, UnitOfMeasure
from mop.prolowin.procurement_models import ProcurementCapture, ProcurementEvidenceEvent
from mop.prolowin.procurement_schemas import (
    ManualCaptureCreate, EvidenceCreate, EvidenceReview, OrderLineSummary,
)


class EvidenceConflict(ValueError):
    pass


class EvidenceRule(ValueError):
    pass


class EvidenceNotFound(LookupError):
    pass


class ProcurementEvidenceService:
    def __init__(self, session: Session):
        self.session = session

    def _lock(self, key: str):
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "mop.g6.6:" + key},
        )

    def _audit(self, actor_id, username, action, record_id, details):
        self.session.add(AuditEntry(
            actor_user_id=actor_id, actor_username=username, action=action,
            object_type="ProlowinProcurementEvidence",
            object_id=str(record_id), outcome="success", details=details,
        ))

    def _commit(self, entity):
        try:
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.session.rollback()
            raise EvidenceConflict("duplicate or inconsistent Prolowin source evidence") from exc

    def manual_capture(self, payload: ManualCaptureCreate, actor: UUID, username: str):
        cap = ProcurementCapture(
            id=uuid4(), source_type=payload.source_type,
            source_reference=payload.source_reference, captured_by=actor,
        )
        self.session.add(cap)
        self._audit(actor, username, "prolowin.procurement.capture", cap.id,
                    {"source_type": cap.source_type, "reference": cap.source_reference})
        return self._commit(cap)

    def screenshot(self, content: bytes, content_type: str, reference: str,
                   actor: UUID, username: str):
        if not reference.strip() or len(reference.strip()) > 150:
            raise EvidenceRule("screenshot source reference is required (max 150 characters)")
        if len(content) == 0 or len(content) > 4 * 1024 * 1024:
            raise EvidenceRule("screenshot must be 1 byte to 4 MiB")
        valid_png = content.startswith(b"\\x89PNG\\r\\n\\x1a\\n") and content_type == "image/png"
        valid_jpeg = content.startswith(b"\\xff\\xd8\\xff") and content_type == "image/jpeg"
        if not (valid_png or valid_jpeg):
            raise EvidenceRule("only actual PNG or JPEG screenshot bytes are accepted")
        digest = sha256(content).hexdigest()
        self._lock("screenshot:" + digest)
        existing = self.session.scalar(select(ProcurementCapture).where(
            ProcurementCapture.source_sha256 == digest
        ))
        if existing is not None:
            self.session.rollback()
            return existing
        cap = ProcurementCapture(
            id=uuid4(), source_type="SCREENSHOT",
            source_reference=reference.strip(), source_sha256=digest,
            image_mime=content_type, image_bytes=content, captured_by=actor,
        )
        self.session.add(cap)
        self._audit(actor, username, "prolowin.procurement.screenshot", cap.id,
                    {"sha256": digest, "reference": cap.source_reference})
        return self._commit(cap)

    def capture(self, capture_id: UUID):
        cap = self.session.get(ProcurementCapture, capture_id)
        if cap is None:
            raise EvidenceNotFound("evidence capture not found")
        return cap

    def record(self, payload: EvidenceCreate, actor: UUID, username: str):
        capture = self.capture(payload.capture_id)
        self._lock("evidence:" + payload.source_event_key)
        if self.session.scalar(select(ProcurementEvidenceEvent.id).where(
            ProcurementEvidenceEvent.source_event_key == payload.source_event_key
        )) is not None:
            raise EvidenceConflict("source event already transcribed; inspect existing evidence")
        event = ProcurementEvidenceEvent(
            id=uuid4(), capture_id=capture.id, source_event_key=payload.source_event_key,
            kind=payload.kind, po_number=payload.po_number, line_number=payload.line_number,
            supplier_code=payload.supplier_code, article_code=payload.article_code,
            uom_code=payload.uom_code, quantity=payload.quantity,
            accepted_quantity=payload.accepted_quantity, event_date=payload.event_date,
            original_promise_date=payload.original_promise_date,
            revised_promise_date=payload.revised_promise_date,
            reason=payload.reason, continuity_safe=payload.continuity_safe,
            source_reference=payload.source_reference, review_status="PENDING",
            entered_by=actor,
        )
        self.session.add(event)
        self._audit(actor, username, "prolowin.procurement.transcribe", event.id,
                    {"capture_id": str(capture.id), "source_key": payload.source_event_key,
                     "kind": payload.kind, "status": "PENDING"})
        return self._commit(event)

    def list_events(self, *, po_number: str | None = None, status: str | None = None):
        stmt = select(ProcurementEvidenceEvent)
        if po_number:
            stmt = stmt.where(ProcurementEvidenceEvent.po_number == po_number)
        if status:
            stmt = stmt.where(ProcurementEvidenceEvent.review_status == status)
        return list(self.session.scalars(
            stmt.order_by(ProcurementEvidenceEvent.entered_at, ProcurementEvidenceEvent.id)
        ).all())

    def _mapped_supplier(self, raw: str) -> Supplier:
        mapped = self.session.scalar(select(SupplierSourceMapping).where(
            SupplierSourceMapping.external_system == "PROLOWIN",
            SupplierSourceMapping.external_code == raw,
            SupplierSourceMapping.mapping_status == "MAPPED",
            SupplierSourceMapping.active.is_(True),
        ))
        supplier = self.session.get(Supplier, mapped.supplier_id) if mapped and mapped.supplier_id else None
        if supplier is None:
            supplier = self.session.scalar(select(Supplier).where(Supplier.code == raw))
        if supplier is None or not supplier.active:
            raise EvidenceRule("supplier code is not mapped to active G2 supplier")
        return supplier

    def _mapped_article(self, raw: str) -> Article:
        options = list(self.session.scalars(select(Article).where(
            Article.external_code == raw, Article.active.is_(True)
        )).all())
        source = [article for article in options if article.external_system == "PROLOWIN"]
        candidates = source if source else options
        if len(candidates) != 1:
            raise EvidenceRule("article code does not uniquely map to active G2 article")
        return candidates[0]

    def _verified_order(self, event: ProcurementEvidenceEvent):
        stmt = select(ProcurementEvidenceEvent).where(
            ProcurementEvidenceEvent.po_number == event.po_number,
            ProcurementEvidenceEvent.line_number == event.line_number,
            ProcurementEvidenceEvent.kind == "ORDER",
            ProcurementEvidenceEvent.review_status == "VERIFIED",
        )
        orders = list(self.session.scalars(stmt).all())
        if len(orders) != 1:
            raise EvidenceRule("a single verified original PO line is required before review")
        order = orders[0]
        if (event.supplier_code, event.article_code, event.uom_code) != (
            order.supplier_code, order.article_code, order.uom_code
        ):
            raise EvidenceRule("record conflicts with original PO supplier, article or UoM")
        if event.event_date < order.event_date:
            raise EvidenceRule("event predates original PO date")
        return order

    def verify(self, event_id: UUID, decision: EvidenceReview, actor: UUID, username: str):
        event = self.session.scalar(select(ProcurementEvidenceEvent).where(
            ProcurementEvidenceEvent.id == event_id
        ).with_for_update())
        if event is None:
            raise EvidenceNotFound("procurement transcription not found")
        if event.review_status != "PENDING":
            raise EvidenceConflict("review decision already finalized")
        if actor == event.entered_by:
            raise EvidenceRule("independent reviewer must differ from transcribing user")
        cap = self.capture(event.capture_id)
        if decision.decision == "VERIFIED" and cap.source_type == "WEEKLY_SNAPSHOT":
            raise EvidenceRule("weekly Excel snapshot is secondary and cannot independently verify a transaction")
        if decision.decision == "VERIFIED":
            supplier = self._mapped_supplier(event.supplier_code)
            article = self._mapped_article(event.article_code)
            uom = self.session.scalar(select(UnitOfMeasure).where(
                UnitOfMeasure.code == event.uom_code,
                UnitOfMeasure.active.is_(True), UnitOfMeasure.canonical.is_(True),
            ))
            if uom is None or article.default_uom_id != uom.id:
                raise EvidenceRule("canonical article UoM mapping required for verification")
            event.mapped_supplier_id, event.mapped_article_id, event.mapped_uom_id = (
                supplier.id, article.id, uom.id
            )
            self._lock(f"order:{event.po_number}:{event.line_number}")
            if event.kind == "ORDER":
                if self.session.scalar(select(ProcurementEvidenceEvent.id).where(
                    ProcurementEvidenceEvent.po_number == event.po_number,
                    ProcurementEvidenceEvent.line_number == event.line_number,
                    ProcurementEvidenceEvent.kind == "ORDER",
                    ProcurementEvidenceEvent.review_status == "VERIFIED",
                )):
                    raise EvidenceConflict("original purchase order line already verified")
            else:
                self._verified_order(event)
                if event.kind == "RECEIPT":
                    order = self._verified_order(event)
                    receipts = self.session.scalar(select(func.coalesce(
                        func.sum(ProcurementEvidenceEvent.quantity), 0
                    )).where(
                        ProcurementEvidenceEvent.po_number == event.po_number,
                        ProcurementEvidenceEvent.line_number == event.line_number,
                        ProcurementEvidenceEvent.kind == "RECEIPT",
                        ProcurementEvidenceEvent.review_status == "VERIFIED",
                    ))
                    if Decimal(receipts) + event.quantity > order.quantity:
                        raise EvidenceRule("partial receipts exceed originally ordered quantity")
        event.review_status = decision.decision
        event.review_note = decision.note.strip()
        event.reviewed_by = actor
        event.reviewed_at = datetime.now(timezone.utc)
        self._audit(actor, username, "prolowin.procurement.review", event.id,
                    {"decision": decision.decision, "source_key": event.source_event_key,
                     "capture_sha256": cap.source_sha256})
        return self._commit(event)

    def summary(self, po_number: str, line_number: int, today: datetime):
        if today.tzinfo is None or today.utcoffset() is None:
            raise EvidenceRule("summary date requires a timezone")
        rows = list(self.session.scalars(select(ProcurementEvidenceEvent).where(
            ProcurementEvidenceEvent.po_number == po_number,
            ProcurementEvidenceEvent.line_number == line_number,
            ProcurementEvidenceEvent.review_status == "VERIFIED",
        ).order_by(ProcurementEvidenceEvent.event_date, ProcurementEvidenceEvent.id)).all())
        orders = [r for r in rows if r.kind == "ORDER"]
        if len(orders) != 1:
            raise EvidenceNotFound("no uniquely verified original PO line")
        o = orders[0]
        deliveries = [r for r in rows if r.kind == "RECEIPT"]
        delivered = sum((r.quantity for r in deliveries), Decimal("0"))
        accepted = (sum((r.accepted_quantity for r in deliveries), Decimal("0"))
                    if all(r.accepted_quantity is not None for r in deliveries) else None)
        latest = next((r.revised_promise_date for r in reversed(rows)
                       if r.kind == "RESCHEDULE"), None)
        # Calendar days are explicitly NOT business-day lead-time metrics.
        last = max((r.event_date for r in deliveries), default=today)
        overdue = delivered < o.quantity and last > o.original_promise_date
        days = ((last.date() - o.original_promise_date.date()).days if overdue else 0)
        return OrderLineSummary(
            po_number=po_number, line_number=line_number,
            supplier_code=o.supplier_code, article_code=o.article_code,
            original_promise_date=o.original_promise_date,
            latest_revised_promise_date=latest, order_date=o.event_date,
            ordered_quantity=o.quantity, delivered_quantity=delivered,
            accepted_quantity=accepted,
            outstanding_delivered_quantity=o.quantity - delivered,
            overdue_against_original=overdue, delayed_days_calendar=days,
            claim_count=sum(r.kind == "CLAIM" for r in rows),
            production_risk_escalations=sum(r.kind == "ESCALATION" for r in rows),
            partial_receipt_count=len(deliveries),
        )
