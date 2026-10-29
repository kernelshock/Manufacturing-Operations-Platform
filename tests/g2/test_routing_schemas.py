from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mop.master_data.schemas import (
    ResourceAssignmentCreate,
    RoutingOperationCreate,
    RoutingRevisionCreate,
)


def test_routing_revision_normalizes_source_and_fingerprint() -> None:
    routing = RoutingRevisionCreate(
        article_revision_id=uuid4(),
        revision_no=1,
        source_system=" prolowin ",
        source_fingerprint="A" * 64,
    )

    assert routing.source_system == "PROLOWIN"
    assert routing.source_fingerprint == "a" * 64


def test_routing_operation_enforces_execution_semantics() -> None:
    physical = RoutingOperationCreate(
        source_operation_code=" 010 ",
        sequence_no=10,
        source_description=" soldadura ",
        operation_kind="PHYSICAL_PRODUCTION",
        schedulable=True,
        nominal_rate=Decimal("2.50000000"),
        rate_uom=" units/min ",
    )

    assert physical.source_operation_code == "010"
    assert physical.source_description == "soldadura"
    assert physical.rate_uom == "units/min"

    with pytest.raises(ValidationError):
        RoutingOperationCreate(
            source_operation_code="FIN",
            sequence_no=999,
            source_description="Fin",
            operation_kind="COMPLETION_MARKER",
            completion_marker=True,
            schedulable=True,
        )

    with pytest.raises(ValidationError):
        RoutingOperationCreate(
            source_operation_code="090",
            sequence_no=90,
            source_description="Administrativa",
            operation_kind="ADMINISTRATIVE",
            schedulable=True,
        )


def test_resource_assignment_uses_decimal_capacity_factor() -> None:
    assignment = ResourceAssignmentCreate(
        resource_id=uuid4(),
        principal=True,
        capacity_factor=Decimal("0.75000000"),
    )

    assert assignment.capacity_factor == Decimal("0.75000000")
