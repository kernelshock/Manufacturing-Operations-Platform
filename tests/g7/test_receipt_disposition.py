from decimal import Decimal
from unittest import TestCase

from mop.materials.receipt_disposition import (
    LotAction, LotBucket, ReceiptBalances, ReceiptDispositionError, apply_lot_decision,
)


class ReceiptDispositionTest(TestCase):
    def test_partial_release_and_issue_preserve_physical_and_usable_balances(self):
        initial = ReceiptBalances.receive(Decimal("10"))
        released = apply_lot_decision(
            initial, action=LotAction.RELEASE, source=LotBucket.QUARANTINE,
            quantity=Decimal("4"), decision_ref="RELEASE-1", verified_release_quantity=Decimal("4"),
        )
        self.assertEqual((released.physical, released.available, released.quarantine), (10, 4, 6))
        after_issue = apply_lot_decision(
            released, action=LotAction.ISSUE, source=LotBucket.AVAILABLE,
            quantity=Decimal("3"), decision_ref="ISSUE-1",
        )
        self.assertEqual((after_issue.physical, after_issue.available), (7, 1))

    def test_unreleased_stock_cannot_be_issued_or_released_without_evidence(self):
        initial = ReceiptBalances.receive(Decimal("10"))
        for action, authorized in ((LotAction.ISSUE, None), (LotAction.RELEASE, None),
                                   (LotAction.RELEASE, Decimal("2"))):
            with self.subTest(action=action, authorized=authorized):
                with self.assertRaises(ReceiptDispositionError):
                    apply_lot_decision(
                        initial, action=action, source=LotBucket.QUARANTINE,
                        quantity=Decimal("3"), decision_ref="DECISION-1",
                        verified_release_quantity=authorized,
                    )

    def test_return_reduces_physical_and_rework_requires_fresh_release(self):
        initial = ReceiptBalances.receive(Decimal("10"))
        rejected = apply_lot_decision(
            initial, action=LotAction.REJECT, source=LotBucket.QUARANTINE,
            quantity=Decimal("6"), decision_ref="REJECT-1",
        )
        returned = apply_lot_decision(
            rejected, action=LotAction.RETURN, source=LotBucket.NONCONFORMING,
            quantity=Decimal("2"), decision_ref="RETURN-1",
        )
        reworked = apply_lot_decision(
            returned, action=LotAction.REWORK, source=LotBucket.NONCONFORMING,
            quantity=Decimal("4"), decision_ref="REWORK-1",
        )
        self.assertEqual((reworked.physical, reworked.available, reworked.quarantine), (8, 0, 8))
