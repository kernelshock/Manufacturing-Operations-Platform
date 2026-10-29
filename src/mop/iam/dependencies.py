"""FastAPI identity and authorization dependencies."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.iam.authorization import AuthorizationService, PermissionDeniedError
from mop.iam.models import User
from mop.iam.session import SessionService
from mop.persistence.dependencies import get_session


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    user = SessionService(session, settings.session_ttl_minutes).resolve(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return user


def require_global_permission(permission_code: str) -> Callable:
    def dependency(
        user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> User:
        try:
            AuthorizationService(session).require(user.id, permission_code)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied") from exc
        return user

    return dependency
