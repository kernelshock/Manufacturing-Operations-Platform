"""Local session authentication API."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.authorization import AuthorizationService
from mop.iam.dependencies import get_current_user
from mop.iam.models import User
from mop.iam.schemas import CurrentUserRead, LoginRequest, UserRead
from mop.iam.service import IdentityService
from mop.iam.session import SessionService
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    settings = request.app.state.settings
    audit_context = request_audit_context(request)
    user = IdentityService(session).authenticate(
        payload.username,
        payload.password,
        max_failures=settings.login_max_failures,
        lockout_minutes=settings.login_lockout_minutes,
    )
    if user is None:
        AuditService(session).record(
            action="auth.login.failure",
            object_type="user_session",
            outcome="failure",
            actor_username=payload.username,
            details={"reason": "invalid_credentials_or_locked"},
            **audit_context,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    raw_token = SessionService(session, settings.session_ttl_minutes).create(user)
    AuditService(session).record(
        action="auth.login.success",
        object_type="user_session",
        object_id=str(user.id),
        outcome="success",
        actor_user_id=user.id,
        actor_username=user.username,
        **audit_context,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    user = None
    if token:
        user = SessionService(session, settings.session_ttl_minutes).resolve(token)
        SessionService(session, settings.session_ttl_minutes).revoke(token)
    if user is not None:
        AuditService(session).record(
            action="auth.logout",
            object_type="user_session",
            object_id=str(user.id),
            outcome="success",
            actor_user_id=user.id,
            actor_username=user.username,
            **request_audit_context(request),
        )
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me", response_model=CurrentUserRead)
def me(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return CurrentUserRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        enabled=user.enabled,
        permissions=AuthorizationService(session).permission_codes(user.id),
    )
