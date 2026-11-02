from uuid import UUID

import pytest
from pydantic import ValidationError

from mop.demand.schemas import TaquillaAssimilationRequest


def _base():
    return {
        "schema_version": "1.0.0",
        "source_system": "TAQUILLA",
        "parser_version": "test-1",
        "mapping_version": "map-1",
        "plan_id": UUID("00000000-0000-0000-0000-000000000001"),
        "taquilla_code": "26-157",
        "sequence_no": 1,
        "vehicle_topology": "DOUBLE_DECK",
        "documents": [
            {
                "source_document_key": "DOC",
                "filename": "taquilla.pdf",
                "sha256": "a" * 64,
            }
        ],
        "lines": [
            {
                "source_document_key": "DOC",
                "source_line_key": "U",
                "article_code": "MOON-UP",
                "requested_quantity": "10.00000000",
                "deck_position": "UPPER",
            },
            {
                "source_document_key": "DOC",
                "source_line_key": "L",
                "article_code": "MOON-LOW",
                "requested_quantity": "12",
                "deck_position": "LOWER",
            },
        ],
    }


def test_double_deck_requires_explicit_both_decks():
    payload = _base()
    parsed = TaquillaAssimilationRequest(**payload)
    assert len(parsed.documents) == 1
    assert {line.deck_position for line in parsed.lines} == {
        "UPPER",
        "LOWER",
    }

    payload["lines"] = payload["lines"][:1]
    with pytest.raises(ValidationError):
        TaquillaAssimilationRequest(**payload)


def test_simple_rejects_upper_or_lower():
    payload = _base()
    payload["vehicle_topology"] = "SIMPLE"
    payload["lines"] = [
        {
            "source_document_key": "DOC",
            "source_line_key": "L1",
            "article_code": "MOON",
            "requested_quantity": "1",
            "deck_position": "UPPER",
        }
    ]
    with pytest.raises(ValidationError):
        TaquillaAssimilationRequest(**payload)


def test_source_line_must_reference_known_document_and_be_unique():
    payload = _base()
    payload["lines"][0]["source_document_key"] = "MISSING"
    with pytest.raises(ValidationError):
        TaquillaAssimilationRequest(**payload)

    payload = _base()
    payload["lines"][1]["source_line_key"] = "U"
    with pytest.raises(ValidationError):
        TaquillaAssimilationRequest(**payload)


def test_quantity_must_be_decimal_string():
    payload = _base()
    payload["lines"][0]["requested_quantity"] = 10.0
    with pytest.raises(ValidationError):
        TaquillaAssimilationRequest(**payload)


def test_import_accepts_at_most_two_source_documents():
    payload = _base()
    payload["documents"].extend(
        [
            {
                "source_document_key": "DOC-2",
                "filename": "second.pdf",
                "sha256": "b" * 64,
            },
            {
                "source_document_key": "DOC-3",
                "filename": "third.pdf",
                "sha256": "c" * 64,
            },
        ]
    )
    with pytest.raises(ValidationError):
        TaquillaAssimilationRequest(**payload)
