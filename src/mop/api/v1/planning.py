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
