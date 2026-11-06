"""G6.1: deterministic material calculations, no inventory side effects.

The G2 canonical article and UoM references are supplied by callers. Material
movements and actual-consumption facts are persisted only in later G6 increments.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TypeAlias

QuantityInput: TypeAlias = Decimal | int | str


class MaterialQuantityError(ValueError):
    """Invalid quantity or incompatible units; refuse an implicit correction."""


class MaterialVarianceState(StrEnum):
    UNKNOWN = "UNKNOWN"
    BALANCED = "BALANCED"
    OVERCONSUMED = "OVERCONSUMED"
    UNDERCONSUMED = "UNDERCONSUMED"


def decimal_quantity(value: QuantityInput, *, allow_zero: bool = True) -> Decimal:
    """Parse exact, finite, nonnegative decimal quantity. Floats are forbidden."""
    if isinstance(value, (float, bool)) or not isinstance(value, (Decimal, int, str)):
        raise MaterialQuantityError("quantity must be Decimal, integer or decimal string; floats forbidden")
    if isinstance(value, str) and not value.strip():
        raise MaterialQuantityError("quantity cannot be blank")
    try:
        quantity = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise MaterialQuantityError("quantity must be decimal") from exc
    if not quantity.is_finite():
        raise MaterialQuantityError("quantity must be finite")
    if quantity < 0 or (quantity == 0 and not allow_zero):
        raise MaterialQuantityError("quantity must be nonnegative" if allow_zero else "quantity must be positive")
    return quantity


@dataclass(frozen=True)
class MaterialQuantity:
    value: Decimal
    uom_code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", decimal_quantity(self.value))
        normalized = self.uom_code.strip().upper()
        if not normalized:
            raise MaterialQuantityError("UoM is required")
        object.__setattr__(self, "uom_code", normalized)


@dataclass(frozen=True)
class MaterialVariance:
    theoretical: MaterialQuantity
    actual: MaterialQuantity | None
    state: MaterialVarianceState
    difference: Decimal | None
    """Signed difference (actual minus theoretical), unknown if actual is absent."""


def material_variance(
    theoretical: MaterialQuantity, actual: MaterialQuantity | None
) -> MaterialVariance:
    """No inferred consumption: missing measurements remain UNKNOWN, not zero."""
    if actual is None:
        return MaterialVariance(theoretical, None, MaterialVarianceState.UNKNOWN, None)
    if actual.uom_code != theoretical.uom_code:
        raise MaterialQuantityError("explicit UoM conversion is required")
    difference = actual.value - theoretical.value
    state = (
        MaterialVarianceState.BALANCED if difference == 0
        else MaterialVarianceState.OVERCONSUMED if difference > 0
        else MaterialVarianceState.UNDERCONSUMED
    )
    return MaterialVariance(theoretical, actual, state, difference)


@dataclass(frozen=True)
class MaterialBalance:
    on_hand: MaterialQuantity | None
    reserved: MaterialQuantity | None
    available: Decimal | None
    """Signed available balance in on_hand UoM, None if an input is unknown."""


def available_balance(
    on_hand: MaterialQuantity | None, reserved: MaterialQuantity | None
) -> MaterialBalance:
    """Read-only projection; never modifies inventory or assumes unknown stock is zero."""
    if on_hand is None or reserved is None:
        return MaterialBalance(on_hand, reserved, None)
    if on_hand.uom_code != reserved.uom_code:
        raise MaterialQuantityError("stock and reservation UoMs must match")
    return MaterialBalance(on_hand, reserved, on_hand.value - reserved.value)
