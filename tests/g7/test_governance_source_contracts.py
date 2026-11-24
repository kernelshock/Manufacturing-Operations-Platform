"""FAIC receipt release and supplier evidence scope checks."""

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from mop.planning.governance_source_contracts import (
    ReceiptRelease, ReceiptScope, ReleaseAuthority, SupplierCapacity,
    SupplierClassification, SupplierClassificationRecord, SupplierEvaluation, SupplierScope,
    released_receipt_quantity, verify_alternative_supplier,
)
from mop.planning.policy_contracts import EvidenceState, PolicyError


class ReceiptReleaseTest(TestCase):
    def setUp(self):
        self.scope = ReceiptScope(uuid4(), uuid4(), uuid4(), "RECEIPT-1:LINE-2", "LOT-3")
        self.cutoff = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.area = uuid4()
        self.release = ReceiptRelease(
            self.scope, "SHEET-1", "SIGNER-1", self.cutoff, EvidenceState.VERIFIED,
            ReleaseAuthority.LABORATORY, None, Decimal("4"),
        )

    def quantity(self, record, *, engineering=True):
        return released_receipt_quantity(
            record, self.scope, engineering_defined=engineering, responsible_area_id=self.area,
            received_quantity=Decimal("10"), as_of=self.cutoff,
        )

    def test_partial_release_and_authority(self):
        self.assertEqual(self.quantity(self.release), Decimal("4"))
        leader_release = replace(
            self.release, authority=ReleaseAuthority.AREA_LEADER, authority_area_id=self.area,
        )
        self.assertEqual(self.quantity(leader_release, engineering=False), Decimal("4"))
        with self.assertRaises(PolicyError):
            self.quantity(leader_release)
        with self.assertRaises(PolicyError):
            self.quantity(replace(leader_release, authority_area_id=uuid4()), engineering=False)

    def test_rejects_wrong_lot_missing_signature_and_excess_quantity(self):
        for invalid in (
            replace(self.release, scope=replace(self.scope, lot_ref="OTHER")),
            replace(self.release, signature_state=EvidenceState.UNKNOWN),
            replace(self.release, released_quantity=Decimal("11")),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(PolicyError):
                self.quantity(invalid)


class SupplierEvidenceTest(TestCase):
    def setUp(self):
        self.scope = SupplierScope(uuid4(), uuid4(), uuid4(), uuid4())
        self.evaluation = SupplierEvaluation(self.scope, "EVAL-1", EvidenceState.VERIFIED)
        self.classification = SupplierClassificationRecord(
            self.scope, "CLASS-1", "EVAL-1", SupplierClassification.ALTERNATIVE, EvidenceState.VERIFIED,
        )
        self.capacity = SupplierCapacity(
            self.scope, "CAPACITY-1", "EVAL-1", EvidenceState.VERIFIED,
            Decimal("50"), date(2026, 11, 20),
        )

    def verify(self, classification, capacity):
        return verify_alternative_supplier(
            self.scope, self.evaluation, classification, capacity,
            required_quantity=Decimal("50"), delivery_deadline=date(2026, 11, 20),
        )

    def test_requires_linked_documents_and_evidence_for_quantity_and_date(self):
        self.assertEqual(
            self.verify(self.classification, self.capacity), ("EVAL-1", "CLASS-1", "CAPACITY-1"),
        )
        for classification in (
            replace(self.classification, classification=SupplierClassification.SUSPENDED),
            replace(self.classification, evaluation_ref="OTHER-EVAL"),
            replace(self.classification, classification_ref="EVAL-1"),
        ):
            with self.subTest(classification=classification), self.assertRaises(PolicyError):
                self.verify(classification, self.capacity)
        for capacity in (
            replace(self.capacity, confirmed_quantity=Decimal("49")),
            replace(self.capacity, confirmed_delivery_date=date(2026, 11, 21)),
            replace(self.capacity, scope=replace(self.scope, supplier_id=uuid4())),
        ):
            with self.subTest(capacity=capacity), self.assertRaises(PolicyError):
                self.verify(self.classification, capacity)
