"""G7.2 read-only supply position endpoint; procurement evidence needs dual permission."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.materials.service import MaterialsNotFound, MaterialsRule
from mop.persistence.dependencies import get_session
from mop.planning.position_schemas import PositionSnapshot
from mop.planning.position_service import SupplyPositionService
from mop.planning.reliability_service import SupplierReliabilityService
from mop.planning.reliability_schemas import SupplierReliabilityOverview

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/supply-position", response_model=PositionSnapshot)
def supply_position(
    plant_id: UUID, article_id: UUID,
    evidence_cutoff_at: datetime = Query(..., description="Time-zone aware verified Prolowin event cutoff; physical stock is current"),
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
    __: User = Depends(require_global_permission("prolowin.procurement.read")),
):
    """Read-only current G6 stock plus separately labeled verified manual PO sample."""
    try:
        return SupplyPositionService(session).snapshot(plant_id, article_id, evidence_cutoff_at)
    except MaterialsNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MaterialsRule as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/supplier-reliability", response_model=SupplierReliabilityOverview)
def supplier_reliability(
    plant_id: UUID,
    article_id: UUID,
    supplier_code: str = Query(..., min_length=1, max_length=80),
    calendar_id: UUID = Query(..., description="Explicit G2 active plant calendar; proxy, not supplier agreed calendar"),
    as_of: datetime = Query(..., description="Timezone-aware cutoff of verified Prolowin events"),
    session: Session = Depends(get_session),
    _: User = Depends(require_global_permission("materials.read")),
    __: User = Depends(require_global_permission("prolowin.procurement.read")),
):
    """Read-only sampled delivery evidence, not a global reliability rating."""
    try:
        return SupplierReliabilityService(session).overview(
            plant_id, article_id, supplier_code, calendar_id, as_of,
        )
    except MaterialsNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MaterialsRule as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
