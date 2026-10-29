from decimal import Decimal

import pytest
from pydantic import ValidationError

from mop.master_data.schemas import ArticleCreate, UnitOfMeasureAliasCreate, UnitOfMeasureCreate


def test_uom_and_source_system_normalize_without_losing_raw_alias() -> None:
    uom = UnitOfMeasureCreate(code=" unid ", dimension="COUNT")
    alias = UnitOfMeasureAliasCreate(
        source_system=" prolowin ",
        raw_value=" UNID. ",
        uom_id="00000000-0000-0000-0000-000000000001",
        mapping_status="MAPPED",
        conversion_factor=Decimal("1"),
    )

    assert uom.code == "UNID"
    assert alias.source_system == "PROLOWIN"
    assert alias.raw_value == "UNID."


def test_unmapped_alias_cannot_claim_canonical_uom() -> None:
    with pytest.raises(ValidationError):
        UnitOfMeasureAliasCreate(
            source_system="PROLOWIN",
            raw_value="UNKNOWN",
            uom_id="00000000-0000-0000-0000-000000000001",
            mapping_status="UNMAPPED",
        )


def test_article_prefix_does_not_infer_kind() -> None:
    article = ArticleCreate(
        external_system="PROLOWIN",
        external_code="X-6111",
        canonical_description="Apollo",
    )

    assert article.article_kind == "UNKNOWN"
