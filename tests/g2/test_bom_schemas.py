from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mop.master_data.schemas import BOMComponentCreate, BOMRevisionCreate


def test_bom_revision_fingerprint_and_source_normalize() -> None:
    bom = BOMRevisionCreate(
        parent_article_revision_id=uuid4(),
        revision_no=1,
        source_system=" prolowin ",
        source_fingerprint="A" * 64,
    )

    assert bom.source_system == "PROLOWIN"
    assert bom.source_fingerprint == "a" * 64


def test_bom_revision_rejects_invalid_effectivity() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        BOMRevisionCreate(
            parent_article_revision_id=uuid4(),
            revision_no=1,
            valid_from=now,
            valid_to=now - timedelta(seconds=1),
            source_system="SYNTHETIC",
            source_fingerprint="b" * 64,
        )


def test_bom_component_is_decimal_safe_and_preserves_raw_uom() -> None:
    component = BOMComponentCreate(
        child_article_id=uuid4(),
        quantity=Decimal("0.12500000"),
        source_uom_raw=" MTS 3 ",
        scrap_factor=Decimal("0.05000000"),
    )

    assert component.quantity == Decimal("0.12500000")
    assert component.source_uom_raw == "MTS 3"
    assert component.scrap_factor == Decimal("0.05000000")
