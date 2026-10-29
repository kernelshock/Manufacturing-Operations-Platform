"""FastAPI persistence dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """Yield one database session per request."""

    with request.app.state.database.session() as session:
        yield session
