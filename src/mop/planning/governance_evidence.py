"""Resolve operational evidence identifiers against the G6 inventory ledger."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mop.core.models import Area, Resource, WorkCenter
from mop.materials.models import MaterialLocation, MaterialMovement, MaterialWarehouse
from mop.materials.reservation_service import ReservationService
from mop.mes.models import ExecutionDispatch, ExecutionInterruption, ExecutionOperation
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


def resolve_material_stoppage(
    session: Session, *, plant_id: UUID, article_id: UUID, location_id: UUID,
    interruption_id: UUID, observed_at: datetime,
):
    """Corroborate an explicitly recorded MES cause with current G6 coverage."""
    reason_code = f"MATERIAL_SHORTAGE:{article_id}"
    taquilla_id = session.scalar(
        select(ExecutionOperation.taquilla_id)
        .join(ExecutionInterruption, ExecutionInterruption.execution_operation_id == ExecutionOperation.id)
        .join(ExecutionDispatch, ExecutionDispatch.id == ExecutionOperation.dispatch_id)
        .join(Resource, Resource.id == func.coalesce(
            ExecutionOperation.actual_resource_id, ExecutionOperation.planned_resource_id,
        ))
        .join(WorkCenter, WorkCenter.id == Resource.work_center_id)
        .join(Area, Area.id == WorkCenter.area_id)
        .where(
            ExecutionInterruption.id == interruption_id,
            ExecutionInterruption.reason_code == reason_code,
            ExecutionInterruption.started_at <= observed_at,
            ExecutionInterruption.ended_at.is_(None),
            ExecutionOperation.status == "PAUSED",
            ExecutionDispatch.status == "RELEASED",
            Area.plant_id == plant_id,
        )
        .with_for_update(of=ExecutionInterruption)
    )
    if taquilla_id is None:
        raise PolicyError("no active MES interruption for this material in the case plant")
    local_location = session.scalar(
        select(MaterialLocation.id)
        .join(MaterialWarehouse, MaterialWarehouse.id == MaterialLocation.warehouse_id)
        .where(
            MaterialLocation.id == location_id,
            MaterialLocation.active.is_(True),
            MaterialWarehouse.active.is_(True),
            MaterialWarehouse.plant_id == plant_id,
        )
    )
    if local_location is None:
        raise PolicyError("material location is unavailable in the case plant")
    coverage = ReservationService(session).coverage(taquilla_id, article_id, location_id, observed_at)
    if coverage.shortage is None or coverage.shortage <= 0:
        raise PolicyError("live G6 coverage does not corroborate a known shortage")
    return coverage
