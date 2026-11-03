"""G6.1 Materials semantic and Decimal invariants."""
from decimal import Decimal
import pytest

from mop.materials.quantity import (
    MaterialQuantity, MaterialQuantityError, MaterialVarianceState,
    available_balance, decimal_quantity, material_variance,
)


def q(value: str, uom: str = "UN") -> MaterialQuantity:
    return MaterialQuantity(Decimal(value), uom)


@pytest.mark.parametrize("bad", [
    "-1", "-0.001", "NaN", "Infinity", "-Infinity", "", " ",
    "12,4", 0.1, True, None, object(),
])
def test_invalid_quantity_fails_closed(bad):
    with pytest.raises(MaterialQuantityError):
        decimal_quantity(bad)


def test_zero_is_distinct_from_absent_and_positive_only():
    assert decimal_quantity("0") == Decimal("0")
    with pytest.raises(MaterialQuantityError):
        decimal_quantity("0", allow_zero=False)
    assert material_variance(q("5"), None).state == MaterialVarianceState.UNKNOWN
    observed_zero = material_variance(q("5"), q("0"))
    assert observed_zero.state == MaterialVarianceState.UNDERCONSUMED
    assert observed_zero.difference == Decimal("-5")


@pytest.mark.parametrize("actual, expected_state, difference", [
    ("10", MaterialVarianceState.BALANCED, "0"),
    ("12.50000000", MaterialVarianceState.OVERCONSUMED, "2.50000000"),
    ("9.75", MaterialVarianceState.UNDERCONSUMED, "-0.25"),
])
def test_exact_theoretical_actual_variance(actual, expected_state, difference):
    comparison = material_variance(q("10"), q(actual))
    assert comparison.state == expected_state
    assert comparison.difference == Decimal(difference)
    assert isinstance(comparison.difference, Decimal)


def test_units_are_explicit_and_canonicalized():
    assert q("1", " kg ").uom_code == "KG"
    with pytest.raises(MaterialQuantityError):
        q("1", "")
    with pytest.raises(MaterialQuantityError, match="UoM"):
        material_variance(q("10", "UN"), q("10", "KG"))
    with pytest.raises(MaterialQuantityError, match="UoM"):
        available_balance(q("10", "KG"), q("1", "M"))


def test_availability_requires_both_known_inputs_and_preserves_signed_shortfall():
    assert available_balance(None, q("0")).available is None
    assert available_balance(q("0"), None).available is None
    assert available_balance(q("0"), q("0")).available == Decimal("0")
    assert available_balance(q("10.5"), q("3.25")).available == Decimal("7.25")
    assert available_balance(q("3"), q("5")).available == Decimal("-2")


def test_does_not_change_inputs():
    theoretical, actual = q("10"), q("12")
    material_variance(theoretical, actual)
    assert theoretical.value == Decimal("10")
    assert actual.value == Decimal("12")
