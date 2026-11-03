"""G5.6 observational feedback endpoints. Read permission only; no APS writes."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.mes.feedback_schemas import DispatchFeedbackRead, OperationFeedbackRead
from mop.mes.feedback_service import FeedbackService
from mop.mes.service import MESNotFoundError
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/mes/feedback", tags=["mes"])


def service(session: Session = Depends(get_session)) -> FeedbackService:
    return FeedbackService(session)


@router.get("/operations/{operation_id}", response_model=OperationFeedbackRead)
def operation_feedback(
    operation_id: UUID,
    app: FeedbackService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    try:
        return app.operation_feedback(operation_id)
    except MESNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/dispatches/{dispatch_id}", response_model=DispatchFeedbackRead)
def dispatch_feedback(
    dispatch_id: UUID,
    app: FeedbackService = Depends(service),
    _: User = Depends(require_global_permission("mes.read")),
):
    try:
        return app.dispatch_feedback(dispatch_id)
    except MESNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
