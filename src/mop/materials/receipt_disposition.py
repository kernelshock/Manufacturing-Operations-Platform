"""Quantity-level receipt decisions for quarantined and usable material."""

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum

from mop.materials.quantity import MaterialQuantityError, decimal_quantity


class ReceiptDispositionError(ValueError):
    """The lot decision violates its quantity or evidence boundary."""


class LotBucket(StrEnum):
    QUARANTINE = "QUARANTINE"
    AVAILABLE = "AVAILABLE"
    NONCONFORMING = "NONCONFORMING"


class LotAction(StrEnum):
    RELEASE = "RELEASE"
    HOLD = "HOLD"
    REJECT = "REJECT"
    REWORK = "REWORK"
    RETURN = "RETURN"
    SCRAP = "SCRAP"
    ISSUE = "ISSUE"


# Destination None means the quantity physically leaves this receipt lot.
_TRANSITIONS = {
    (LotAction.RELEASE, LotBucket.QUARANTINE): LotBucket.AVAILABLE,
    (LotAction.HOLD, LotBucket.AVAILABLE): LotBucket.QUARANTINE,
    (LotAction.REJECT, LotBucket.QUARANTINE): LotBucket.NONCONFORMING,
    (LotAction.REWORK, LotBucket.NONCONFORMING): LotBucket.QUARANTINE,
    (LotAction.RETURN, LotBucket.NONCONFORMING): None,
    (LotAction.SCRAP, LotBucket.NONCONFORMING): None,
    (LotAction.ISSUE, LotBucket.AVAILABLE): None,
}


@dataclass(frozen=True)
class ReceiptBalances:
    quarantine: Decimal
    available: Decimal = Decimal("0")
    nonconforming: Decimal = Decimal("0")

    @classmethod
    def receive(cls, quantity: Decimal) -> "ReceiptBalances":
        return cls(quarantine=decimal_quantity(quantity, allow_zero=False))

    @property
    def physical(self) -> Decimal:
        return self.quarantine + self.available + self.nonconforming


def apply_lot_decision(
    balances: ReceiptBalances,
    *,
    action: LotAction,
    source: LotBucket,
    quantity: Decimal,
    decision_ref: str,
    verified_release_quantity: Decimal | None = None,
) -> ReceiptBalances:
    """Project an authorized decision within one receipt line or lot.

    The release amount comes from the release evidence validator. The caller
    owns authority verification, evidence replay protection and persistence.
    """
    transition = (action, source)
    if transition not in _TRANSITIONS:
        raise ReceiptDispositionError("action is not permitted from this stock state")
    if not decision_ref.strip():
        raise ReceiptDispositionError("lot decision needs a traceable record")

    try:
        amount = decimal_quantity(quantity, allow_zero=False)
        if action == LotAction.RELEASE and (
            verified_release_quantity is None or amount > decimal_quantity(verified_release_quantity)
        ):
            raise ReceiptDispositionError("release exceeds the verified authorization")
    except MaterialQuantityError as exc:
        raise ReceiptDispositionError(str(exc)) from exc

    source_field = source.value.lower()
    remaining = getattr(balances, source_field) - amount
    if remaining < 0:
        raise ReceiptDispositionError("decision quantity exceeds the balance in this state")

    changes = {source_field: remaining}
    destination = _TRANSITIONS[transition]
    if destination is not None:
        destination_field = destination.value.lower()
        changes[destination_field] = getattr(balances, destination_field) + amount
    return replace(balances, **changes)
