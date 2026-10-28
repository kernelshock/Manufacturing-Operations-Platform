"""API metadata endpoint."""

from fastapi import APIRouter, Request

from mop import __version__

router = APIRouter(tags=["system"])


@router.get("/meta")
def metadata(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "name": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "api_prefix": settings.api_prefix,
    }
