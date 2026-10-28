"""Infrastructure health and readiness endpoints."""

from fastapi import APIRouter, Request

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
def readiness(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "ready",
        "service": settings.app_name,
        "checks": {
            "application": "ok",
        },
    }
