import pytest
from pydantic import ValidationError

from mop.demand.schemas import (
    DemandCancellationRequest,
    HistoricalCompletionRequest,
)


def test_historical_completion_normalizes_note():
    request = HistoricalCompletionRequest(
        classification="DELAYED",
        note="  Legacy baseline  ",
    )
    assert request.classification == "DELAYED"
    assert request.note == "Legacy baseline"


def test_cancellation_requires_reason():
    with pytest.raises(ValidationError):
        DemandCancellationRequest(reason="   ")
