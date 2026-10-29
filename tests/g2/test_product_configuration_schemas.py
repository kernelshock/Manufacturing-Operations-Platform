from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mop.master_data.schemas import ProductConfigurationCreate


def _payload() -> dict:
    return {
        "article_id": uuid4(),
        "family_code": " seat-family ",
        "family_name": "Passenger Seat Family",
        "model_code": " model-a ",
        "model_name": "Model A",
        "product_class": "Premium",
        "configuration_string": "Model A / premium / synthetic configuration",
    }


def test_product_configuration_normalizes_codes() -> None:
    configuration = ProductConfigurationCreate(**_payload())

    assert configuration.family_code == "SEAT-FAMILY"
    assert configuration.model_code == "MODEL-A"


def test_width_requires_uom_and_uom_requires_width() -> None:
    with pytest.raises(ValidationError):
        ProductConfigurationCreate(**_payload(), width=Decimal("440"))

    with pytest.raises(ValidationError):
        ProductConfigurationCreate(**_payload(), width_uom_id=uuid4())


def test_width_uses_decimal_semantics() -> None:
    configuration = ProductConfigurationCreate(
        **_payload(),
        width=Decimal("440.1250"),
        width_uom_id=uuid4(),
    )

    assert configuration.width == Decimal("440.1250")
