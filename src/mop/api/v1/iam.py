"""Administrative identity and RBAC API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import get_current_user, require_global_permission
from mop.iam.models import User
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
def create_user(
    payload: UserCreate,
    request: Request,
    app: IdentityService = Depends(identity),
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_user(payload))
    AuditService(session).record(
        action="iam.user.create",
        object_type="user",
        object_id=str(created.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"username": created.username},
        **request_audit_context(request),
    )
    return created


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
def create_role(
    payload: RoleCreate,
    request: Request,
    app: IdentityService = Depends(identity),
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_role(payload))
    AuditService(session).record(
        action="iam.role.create",
        object_type="role",
        object_id=str(created.id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"code": created.code},
        **request_audit_context(request),
    )
    return created


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
def grant_permission(
    role_id: UUID,
    permission_code: str,
    request: Request,
    app: IdentityService = Depends(identity),
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _translate(lambda: app.grant_permission(role_id, permission_code))
    AuditService(session).record(
        action="iam.role.permission.grant",
        object_type="role",
        object_id=str(role_id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"permission": permission_code},
        **request_audit_context(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/roles",
    response_model=RoleAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_global_permission("admin.users"))],
)
def assign_role(
    user_id: UUID,
    payload: RoleAssignmentCreate,
    request: Request,
    app: IdentityService = Depends(identity),
    actor: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    assignment = _translate(lambda: app.assign_role(user_id, payload))
    AuditService(session).record(
        action="iam.user.role.assign",
        object_type="user_role_assignment",
        object_id=str(assignment.id),
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details={"user_id": str(user_id), "role_id": str(assignment.role_id)},
        **request_audit_context(request),
    )
    return assignment
