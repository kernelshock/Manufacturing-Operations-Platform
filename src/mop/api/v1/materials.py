"""G6.2 — operational materials warehouse and immutable ledger endpoints."""
from uuid import UUID

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.materials.schemas import (
    BalanceRead, LocationCreate, LocationRead, MovementCreate, MovementRead,
    MovementReverse, PostingResult, WarehouseCreate, WarehouseRead,
)
from mop.materials.service import MaterialsConflict, MaterialsNotFound, MaterialsRule, MaterialsService
from mop.materials.requirement_schemas import MaterialDemandProjection
from mop.materials.requirements import MaterialRequirementsService
from mop.materials.consumption_service import MaterialConsumptionService
from mop.materials.reservation_service import ReservationService
from mop.materials.reservation_schemas import (ReservationCreate, ReservationRelease, ReservationResult, ReservationEventRead, LocationAvailability, TaquillaCoverage)
from mop.materials.consumption_schemas import (
    ConsumptionCreate, ConsumptionRead, ConsumptionReverse, ConsumptionResult,
)
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/materials", tags=["materials"])


def svc(session: Session = Depends(get_session)) -> MaterialsService:
    return MaterialsService(session)


def checked(operation):
    try:
        return operation()
    except MaterialsNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MaterialsConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MaterialsRule as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/warehouses", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreate,
    app: MaterialsService = Depends(svc),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    return checked(lambda: app.warehouse(payload, actor.id, actor.username))


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_warehouses(
    plant_id: UUID | None = None,
    app: MaterialsService = Depends(svc),
    _: User = Depends(require_global_permission("materials.read")),
):
    return app.list_warehouses(plant_id)


@router.post("/locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    app: MaterialsService = Depends(svc),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    return checked(lambda: app.location(payload, actor.id, actor.username))


@router.get("/locations", response_model=list[LocationRead])
def list_locations(
    warehouse_id: UUID | None = None,
    app: MaterialsService = Depends(svc),
    _: User = Depends(require_global_permission("materials.read")),
):
    return app.list_locations(warehouse_id)


@router.post("/movements", response_model=PostingResult, status_code=status.HTTP_201_CREATED)
def post_movement(
    payload: MovementCreate,
    app: MaterialsService = Depends(svc),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    return checked(lambda: app.post(payload, actor.id, actor.username))


@router.post("/movements/{movement_id}/reverse", response_model=PostingResult, status_code=status.HTTP_201_CREATED)
def reverse_movement(
    movement_id: UUID,
    payload: MovementReverse,
    app: MaterialsService = Depends(svc),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    return checked(lambda: app.reverse(movement_id, payload, actor.id, actor.username))


@router.get("/balances", response_model=BalanceRead)
def get_balance(
    article_id: UUID,
    location_id: UUID,
    app: MaterialsService = Depends(svc),
    _: User = Depends(require_global_permission("materials.read")),
):
    return app.balance(article_id, location_id)


@router.get("/movements", response_model=list[MovementRead])
def list_movements(
    article_id: UUID,
    location_id: UUID,
    app: MaterialsService = Depends(svc),
    _: User = Depends(require_global_permission("materials.read")),
):
    return app.list_movements(article_id, location_id)


@router.get("/plans/{plan_id}/requirements", response_model=MaterialDemandProjection)
def plan_material_requirements(
    plan_id: UUID,
    effective_at: datetime = Query(..., description="Explicit, timezone-aware BOM effectivity timestamp"),
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
):
    """Read-only theoretical explosion; never posts, reserves or subtracts stock."""
    return checked(lambda: MaterialRequirementsService(session).project(plan_id, effective_at))


@router.get("/taquillas/{taquilla_id}/requirements", response_model=MaterialDemandProjection)
def taquilla_material_requirements(
    taquilla_id: UUID,
    effective_at: datetime = Query(..., description="Explicit, timezone-aware BOM effectivity timestamp"),
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
):
    return checked(lambda: MaterialRequirementsService(session).project_taquilla(taquilla_id, effective_at))


@router.post(
    "/operations/{operation_id}/consumptions",
    response_model=ConsumptionResult,
    status_code=status.HTTP_201_CREATED,
)
def record_actual_material_consumption(
    operation_id: UUID,
    payload: ConsumptionCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    """Explicit measured material use; atomic stock ISSUE and audit (not a MES automation)."""
    return checked(lambda: MaterialConsumptionService(session).record(
        operation_id, payload, actor.id, actor.username,
    ))


@router.get(
    "/operations/{operation_id}/consumptions", response_model=list[ConsumptionRead]
)
def list_actual_material_consumptions(
    operation_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
):
    return checked(lambda: MaterialConsumptionService(session).list(operation_id))


@router.post(
    "/consumptions/{consumption_id}/reverse",
    response_model=ConsumptionResult,
    status_code=status.HTTP_201_CREATED,
)
def reverse_actual_material_consumption(
    consumption_id: UUID,
    payload: ConsumptionReverse,
    session: Session = Depends(get_session),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    """Append-only evidence correction and linked stock reversal; never edits MES."""
    return checked(lambda: MaterialConsumptionService(session).reverse(
        consumption_id, payload, actor.id, actor.username,
    ))


@router.post("/reservations", response_model=ReservationResult, status_code=status.HTTP_201_CREATED)
def reserve_for_taquilla(
    payload: ReservationCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    """Commit physical quantity to one taquilla; no inventory movement or PO."""
    return checked(lambda: ReservationService(session).hold(payload, actor.id, actor.username))


@router.post("/reservations/{hold_id}/release", response_model=ReservationResult,
             status_code=status.HTTP_201_CREATED)
def release_material_reservation(
    hold_id: UUID,
    payload: ReservationRelease,
    session: Session = Depends(get_session),
    actor: User = Depends(require_global_permission("materials.edit")),
):
    """Release whole or partial reservation; retain append-only provenance."""
    return checked(lambda: ReservationService(session).release(
        hold_id, payload, actor.id, actor.username,
    ))


@router.get("/taquillas/{taquilla_id}/reservations", response_model=list[ReservationEventRead])
def list_taquilla_reservations(
    taquilla_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
):
    return ReservationService(session).events(taquilla_id)


@router.get("/availability", response_model=LocationAvailability)
def material_location_availability(
    article_id: UUID,
    location_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
):
    """Unallocated physical on-hand: quality release and ATP are NOT inferred."""
    return ReservationService(session).availability(article_id, location_id)


@router.get("/taquillas/{taquilla_id}/coverage", response_model=TaquillaCoverage)
def taquilla_material_coverage(
    taquilla_id: UUID,
    article_id: UUID,
    location_id: UUID,
    effective_at: datetime = Query(..., description="Timezone-aware effective BOM timestamp"),
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
):
    """Shortfall after reservations + unallocated physical stock, not a purchasing order."""
    return checked(lambda: ReservationService(session).coverage(
        taquilla_id, article_id, location_id, effective_at,
    ))
