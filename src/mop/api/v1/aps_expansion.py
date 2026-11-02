"""G4.2 APS expansion endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from mop.aps.operation_schemas import ExpansionResult, PlanningOperationRead
from mop.aps.service import APSConflictError, APSNotFoundError, APSRuleError, APSService
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
    except APSConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except APSRuleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
