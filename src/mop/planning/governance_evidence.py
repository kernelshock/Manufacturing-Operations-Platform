"""Resolve operational evidence identifiers against the G6 inventory ledger."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.materials.models import MaterialLocation, MaterialMovement, MaterialWarehouse
from mop.planning.governance_models import GovernanceCaseRecord
from mop.planning.policy_contracts import PolicyError


def verify_movement_references(
    session: Session, case: GovernanceCaseRecord, movement_ids: list[UUID],
) -> tuple[str, ...]:
    """Verify ledger identity and scope, without inferring quality or production impact."""
    if not movement_ids:
        return ()
    if len(set(movement_ids)) != len(movement_ids):
        raise PolicyError("duplicate material movement evidence")
    matches = set(session.scalars(
        select(MaterialMovement.id)
        .join(MaterialLocation, MaterialLocation.id == MaterialMovement.location_id)
        .join(MaterialWarehouse, MaterialWarehouse.id == MaterialLocation.warehouse_id)
        .where(
            MaterialMovement.id.in_(movement_ids),
            MaterialMovement.article_id == case.article_id,
            MaterialMovement.uom_id == case.uom_id,
            MaterialWarehouse.plant_id == case.plant_id,
        )
    ))
    if matches != set(movement_ids):
        raise PolicyError("material movement evidence is missing or outside the case scope")
    return tuple(f"G6:MOVEMENT:{movement_id}" for movement_id in sorted(matches))
