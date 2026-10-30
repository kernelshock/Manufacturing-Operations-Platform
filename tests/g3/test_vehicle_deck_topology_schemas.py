from uuid import UUID

from mop.demand.schemas import (
    TaquillaProductLineCreate,
    TaquillaProductLineUpdate,
    TaquillaTopologyUpdate,
)


def test_topology_literals_and_simple_default_are_explicit() -> None:
    topology = TaquillaTopologyUpdate(vehicle_topology="DOUBLE_DECK")
    assert topology.vehicle_topology == "DOUBLE_DECK"

    line = TaquillaProductLineCreate(
        article_id=UUID("00000000-0000-0000-0000-000000000001"),
        sequence_no=1,
        requested_quantity="1",
    )
    assert line.deck_position == "SINGLE"


def test_source_document_key_is_trimmed_without_defining_deck() -> None:
    line = TaquillaProductLineCreate(
        article_id=UUID("00000000-0000-0000-0000-000000000001"),
        sequence_no=1,
        requested_quantity="1",
        deck_position="UPPER",
        source_document_key="  DOC-01  ",
    )
    assert line.source_document_key == "DOC-01"
    assert line.deck_position == "UPPER"

    update = TaquillaProductLineUpdate(
        sequence_no=1,
        requested_quantity="2",
        source_document_key="  DOC-02  ",
    )
    assert update.source_document_key == "DOC-02"
