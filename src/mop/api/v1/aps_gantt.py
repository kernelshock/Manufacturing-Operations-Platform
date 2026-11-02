"""G4.6 read-only Gantt projection endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from mop.aps.gantt_schemas import GanttProjectionRead
from mop.aps.service import APSNotFoundError, APSRuleError, APSService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/aps", tags=["aps"])


def service(session: Session = Depends(get_session)) -> APSService:
    return APSService(session)


def translate(operation):
    try:
        return operation()
    except APSNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except APSRuleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/gantt", response_model=GanttProjectionRead)
def gantt_projection(
    plan_id: UUID | None = Query(default=None),
    app: APSService = Depends(service),
    _: User = Depends(require_global_permission("aps.read")),
):
    return GanttProjectionRead(**translate(lambda: app.gantt_projection(plan_id)))
