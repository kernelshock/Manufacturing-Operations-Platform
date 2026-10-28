"""Local session authentication API."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

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
    user = IdentityService(session).authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    raw_token = SessionService(session, settings.session_ttl_minutes).create(user)
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
    if token:
        SessionService(session, settings.session_ttl_minutes).revoke(token)
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
