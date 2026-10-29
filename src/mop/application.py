"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, Request

from mop import __version__
from mop.api.health import router as health_router
from mop.api.v1.router import router as api_v1_router
from mop.config import Settings, get_settings
from mop.persistence.database import DatabaseManager


class DatabaseLifecycle(Protocol):
    """Minimum database contract required by the application boundary."""

    def check_connection(self) -> None: ...

    def dispose(self) -> None: ...


def create_app(
    settings: Settings | None = None,
    database: DatabaseLifecycle | None = None,
) -> FastAPI:
    """Build the HTTP application without coupling domain code to FastAPI."""

    runtime_settings = settings or get_settings()
    runtime_database = database or DatabaseManager(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            runtime_database.dispose()

    app = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
        debug=runtime_settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.database = runtime_database

    @app.middleware("http")
    async def sensitive_response_cache_control(request: Request, call_next):
        response = await call_next(request)
        sensitive_prefixes = (
            f"{runtime_settings.api_prefix}/auth",
            f"{runtime_settings.api_prefix}/iam",
            f"{runtime_settings.api_prefix}/audit",
        )
        if request.url.path.startswith(sensitive_prefixes):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=runtime_settings.api_prefix)

    return app
