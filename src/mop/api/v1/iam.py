"""Administrative identity and RBAC API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from mop.iam.dependencies import require_global_permission
from mop.iam.schemas import (
    PermissionRead,
    RoleAssignmentCreate,
    RoleAssignmentRead,
    RoleCreate,
    RoleRead,
    UserCreate,
    UserRead,
)
from mop.iam.service import IdentityConflictError, IdentityNotFoundError, IdentityService
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/iam", tags=["iam"])


def identity(session: Session = Depends(get_session)) -> IdentityService:
    return IdentityService(session)


def _translate(operation):
    try:
        return operation()
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_global_permission("admin.users"))],
)
def create_user(payload: UserCreate, app: IdentityService = Depends(identity)):
    return _translate(lambda: app.create_user(payload))


@router.get(
    "/users",
    response_model=list[UserRead],
    dependencies=[Depends(require_global_permission("admin.users"))],
)
def list_users(app: IdentityService = Depends(identity)):
    return app.list_users()


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_global_permission("admin.roles"))],
)
def create_role(payload: RoleCreate, app: IdentityService = Depends(identity)):
    return _translate(lambda: app.create_role(payload))


@router.get(
    "/roles",
    response_model=list[RoleRead],
    dependencies=[Depends(require_global_permission("admin.roles"))],
)
def list_roles(app: IdentityService = Depends(identity)):
    return app.list_roles()


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    dependencies=[Depends(require_global_permission("admin.roles"))],
)
def list_permissions(app: IdentityService = Depends(identity)):
    return app.list_permissions()


@router.post(
    "/roles/{role_id}/permissions/{permission_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_global_permission("admin.roles"))],
)
def grant_permission(role_id: UUID, permission_code: str, app: IdentityService = Depends(identity)):
    _translate(lambda: app.grant_permission(role_id, permission_code))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/roles",
    response_model=RoleAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_global_permission("admin.users"))],
)
def assign_role(user_id: UUID, payload: RoleAssignmentCreate, app: IdentityService = Depends(identity)):
    return _translate(lambda: app.assign_role(user_id, payload))
