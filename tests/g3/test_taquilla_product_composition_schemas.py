from decimal import Decimal

import pytest
from pydantic import ValidationError

from mop.demand.schemas import TaquillaProductLineCreate, TaquillaProductLineUpdate


def test_product_line_preserves_decimal_and_normalizes_source_key() -> None:
    payload = TaquillaProductLineCreate(
        article_id="00000000-0000-0000-0000-000000000001",
        sequence_no=1,
        requested_quantity="12.50000000",
        source_line_key="  SRC-42  ",
    )
    assert payload.requested_quantity == Decimal("12.50000000")
    assert payload.source_line_key == "SRC-42"


def test_product_line_requires_positive_quantity_and_sequence() -> None:
    with pytest.raises(ValidationError):
        TaquillaProductLineCreate(
            article_id="00000000-0000-0000-0000-000000000001",
            sequence_no=0,
            requested_quantity="1",
        )
    with pytest.raises(ValidationError):
        TaquillaProductLineUpdate(sequence_no=1, requested_quantity="0")
