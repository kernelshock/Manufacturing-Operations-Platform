from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from mop.demand.schemas import RoutingOverrideRequest, RoutingResolveRequest


def test_routing_binding_requests_accept_explicit_effectivity() -> None:
    at = datetime.now(timezone.utc)
    resolve = RoutingResolveRequest(effective_at=at)
    assert resolve.effective_at == at

    override = RoutingOverrideRequest(
        routing_revision_id=UUID("00000000-0000-0000-0000-000000000001"),
        effective_at=at,
        reason="  Engineering approval  ",
    )
    assert override.reason == "Engineering approval"


def test_override_requires_nonempty_reason() -> None:
    with pytest.raises(ValidationError):
        RoutingOverrideRequest(
            routing_revision_id=UUID("00000000-0000-0000-0000-000000000001"),
            reason="   ",
        )
