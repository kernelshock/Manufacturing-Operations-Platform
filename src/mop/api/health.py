"""Infrastructure health and readiness endpoints."""

from fastapi import APIRouter, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["system"])


@router.get("/health/live")
def liveness(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/health/ready")
def readiness(request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings

    try:
        request.app.state.database.check_connection()
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "service": settings.app_name,
            "checks": {
                "application": "ok",
                "database": "unavailable",
            },
        }

    return {
        "status": "ready",
        "service": settings.app_name,
        "checks": {
            "application": "ok",
            "database": "ok",
        },
    }
