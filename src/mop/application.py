"""FastAPI application factory."""

from fastapi import FastAPI

from mop import __version__
from mop.api.health import router as health_router
from mop.api.v1.router import router as api_v1_router
from mop.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the HTTP application without coupling domain code to FastAPI."""

    runtime_settings = settings or get_settings()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
        debug=runtime_settings.debug,
    )
    app.state.settings = runtime_settings

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=runtime_settings.api_prefix)

    return app
