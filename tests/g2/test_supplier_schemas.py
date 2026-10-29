from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mop.master_data.schemas import (
    SupplierArticleCreate,
    SupplierCreate,
    SupplierSourceMappingCreate,
)


def test_supplier_identity_normalizes_code_without_rewriting_names() -> None:
    supplier = SupplierCreate(
        code=" prov-001 ",
        legal_name="  Proveedor Ejemplo S.A. ",
        trade_name=" Ejemplo ",
        supply_category="PRODUCT",
    )

    assert supplier.code == "PROV-001"
    assert supplier.legal_name == "Proveedor Ejemplo S.A."
    assert supplier.trade_name == "Ejemplo"


def test_mapped_source_requires_supplier_and_rejected_source_cannot_claim_one() -> None:
    with pytest.raises(ValidationError):
        SupplierSourceMappingCreate(
            external_system="PROLOWIN",
            external_code="0001",
            mapping_status="MAPPED",
        )

    with pytest.raises(ValidationError):
        SupplierSourceMappingCreate(
            supplier_id=uuid4(),
            external_system="CRM",
            external_code="0001",
            mapping_status="REJECTED",
        )


def test_supplier_article_uses_decimal_moq_and_nonnegative_lead_time() -> None:
    link = SupplierArticleCreate(
        supplier_id=uuid4(),
        article_id=uuid4(),
        lead_time_days=12,
        minimum_order_quantity=Decimal("25.50000000"),
    )

    assert link.lead_time_days == 12
    assert link.minimum_order_quantity == Decimal("25.50000000")

    with pytest.raises(ValidationError):
        SupplierArticleCreate(
            supplier_id=uuid4(),
            article_id=uuid4(),
            lead_time_days=-1,
        )
