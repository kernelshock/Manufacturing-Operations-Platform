import pytest
from pydantic import ValidationError

from mop.demand.schemas import ProductionPlanCreate, TaquillaCreate


def test_plan_number_is_trimmed_and_required() -> None:
    assert ProductionPlanCreate(plan_number="  26-A  ").plan_number == "26-A"
    with pytest.raises(ValidationError):
        ProductionPlanCreate(plan_number="   ")


def test_taquilla_sequence_must_be_positive() -> None:
    assert TaquillaCreate(taquilla_code=" 25-072 ", sequence_no=1).taquilla_code == "25-072"
    with pytest.raises(ValidationError):
        TaquillaCreate(taquilla_code="25-073", sequence_no=0)
