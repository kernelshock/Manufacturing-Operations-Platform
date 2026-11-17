"""Internal receipt commands sharing the G6 transaction and stock lock.

The caller authenticates and authorizes the actor, verifies release evidence,
and commits. There is no HTTP entry point for these commands yet.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.materials.models import MaterialMovement
from mop.materials.quantity import decimal_quantity
from mop.materials.receipt_disposition import LotAction, LotBucket, ReceiptBalances, apply_lot_decision
from mop.materials.receipt_models import MaterialReceiptDecision, MaterialReceiptLot
from mop.materials.service import RECEIPT_LEDGER_SOURCE, MaterialsConflict, MaterialsNotFound, MaterialsRule, MaterialsService


class ReceiptService:
    def __init__(self, session: Session):
        self.session = session
        self.stock = MaterialsService(session)

    def receive(
        self, *, receipt_line_ref: str, lot_ref: str, article_id: UUID, location_id: UUID,
        uom_id: UUID, quantity: Decimal, actor_id: UUID, username: str,
    ) -> MaterialReceiptLot:
        line = self._reference(receipt_line_ref)
        lot_ref = self._reference(lot_ref)
        amount = self._quantity(quantity)
        with self.session.begin_nested():
            self.stock._advisory_lock(f"receipt:{line}:{lot_ref}")
            self.stock._advisory_lock(f"balance:{article_id}:{location_id}")
            lot = self.session.scalar(select(MaterialReceiptLot).where(
                MaterialReceiptLot.receipt_line_ref == line, MaterialReceiptLot.lot_ref == lot_ref,
            ))
            if lot is not None:
                if (lot.article_id, lot.location_id, lot.uom_id, lot.quantity) != (
                    article_id, location_id, uom_id, amount,
                ):
                    raise MaterialsConflict("receipt identity already has different evidence")
                return lot

            balance = self.stock._check_dimensions(article_id, location_id, uom_id)
            if not self.stock.is_lot_managed(article_id, location_id) and balance.initialized:
                raise MaterialsRule("new lot tracking requires a material/location without legacy movements")

            lot_id = uuid4()
            movement = self._post_movement(
                lot_id, article_id, location_id, uom_id, "RECEIPT", amount, actor_id, username,
            )
            lot = MaterialReceiptLot(
                id=lot_id, receipt_line_ref=line, lot_ref=lot_ref, article_id=article_id,
                location_id=location_id, uom_id=uom_id, quantity=amount, movement_id=movement.id,
            )
            self.session.add(lot)
            self.stock._audit(actor_id, username, "materials.receipt.receive", lot)
            self.session.flush()
            return lot

    def decide(
        self, lot_id: UUID, *, action: LotAction, source: LotBucket, quantity: Decimal,
        decision_ref: str, expected_revision: int, actor_id: UUID, username: str,
        verified_release_quantity: Decimal | None = None,
    ) -> MaterialReceiptDecision:
        amount = self._quantity(quantity)
        reference = self._reference(decision_ref)
        if action != LotAction.RELEASE and verified_release_quantity is not None:
            raise MaterialsRule("release authorization applies only to a release")
        if verified_release_quantity is not None:
            verified_release_quantity = self._quantity(verified_release_quantity)

        with self.session.begin_nested():
            lot = self.session.get(MaterialReceiptLot, lot_id)
            if lot is None:
                raise MaterialsNotFound("receipt lot not found")
            self.stock._advisory_lock(f"balance:{lot.article_id}:{lot.location_id}")
            events = self._events(lot_id)
            for event in events:
                if event.decision_ref == reference:
                    if (event.action, event.source, event.quantity, event.actor_id,
                        event.verified_release_quantity, event.revision) != (
                        action.value, source.value, amount, actor_id, verified_release_quantity,
                        expected_revision + 1,
                    ):
                        raise MaterialsConflict("decision reference already has different evidence")
                    return event
            if len(events) != expected_revision:
                raise MaterialsConflict("receipt lot revision has changed")

            apply_lot_decision(
                self._balances(lot, events), action=action, source=source, quantity=amount,
                decision_ref=reference, verified_release_quantity=verified_release_quantity,
            )
            event_id = uuid4()
            movement_id = None
            if action in (LotAction.ISSUE, LotAction.SCRAP, LotAction.RETURN):
                movement = self._post_movement(
                    event_id, lot.article_id, lot.location_id, lot.uom_id,
                    "ISSUE" if action == LotAction.ISSUE else "ADJUSTMENT_OUT",
                    -amount, actor_id, username,
                )
                movement_id = movement.id
            event = MaterialReceiptDecision(
                id=event_id, lot_id=lot_id, revision=expected_revision + 1,
                action=action.value, source=source.value, decision_ref=reference, quantity=amount,
                verified_release_quantity=verified_release_quantity, movement_id=movement_id,
                actor_id=actor_id, occurred_at=datetime.now(timezone.utc),
            )
            self.session.add(event)
            self.stock._audit(actor_id, username, f"materials.receipt.{action.value.lower()}", event)
            self.session.flush()
            return event

    def balances(self, lot_id: UUID) -> ReceiptBalances:
        lot = self.session.get(MaterialReceiptLot, lot_id)
        if lot is None:
            raise MaterialsNotFound("receipt lot not found")
        return self._balances(lot, self._events(lot_id))

    @staticmethod
    def _balances(lot, events):
        balances = ReceiptBalances.receive(lot.quantity)
        for event in events:
            balances = apply_lot_decision(
                balances, action=LotAction(event.action), source=LotBucket(event.source),
                quantity=event.quantity, decision_ref=event.decision_ref,
                verified_release_quantity=event.verified_release_quantity,
            )
        return balances

    def _events(self, lot_id: UUID):
        return list(self.session.scalars(select(MaterialReceiptDecision).where(
            MaterialReceiptDecision.lot_id == lot_id,
        ).order_by(MaterialReceiptDecision.revision)))

    def _post_movement(self, event_id, article_id, location_id, uom_id, kind, amount, actor_id, username):
        movement = MaterialMovement(
            id=uuid4(), article_id=article_id, location_id=location_id, uom_id=uom_id,
            kind=kind, quantity=abs(amount), signed_quantity=amount,
            source_system=RECEIPT_LEDGER_SOURCE, source_reference=str(event_id),
            idempotency_key=str(event_id), occurred_at=datetime.now(timezone.utc), posted_by=actor_id,
        )
        self.session.add(movement)
        self.stock._audit(actor_id, username, "materials.movement.post", movement)
        self.session.flush()
        return movement

    @staticmethod
    def _reference(value: str) -> str:
        reference = value.strip()
        if not reference or len(reference) > 128:
            raise MaterialsRule("receipt evidence reference must contain 1 to 128 characters")
        return reference

    @staticmethod
    def _quantity(value: Decimal) -> Decimal:
        amount = decimal_quantity(value, allow_zero=False)
        if amount > Decimal("9999999999999999.99999999") or amount != amount.quantize(Decimal("0.00000001")):
            raise MaterialsRule("quantity exceeds the exact ledger precision")
        return amount
