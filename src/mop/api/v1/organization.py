"""Organization / plant / area / work-center / resource API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.core.schemas import (
    AreaCreate,
    AreaRead,
    OrganizationCreate,
    OrganizationRead,
    PlantCreate,
    PlantRead,
    ResourceCreate,
    ResourceRead,
    WorkCenterCreate,
    WorkCenterRead,
)
from mop.core.service import CoreConflictError, CoreParentNotFoundError, OrganizationService
from mop.iam.authorization import AuthorizationService, PermissionDeniedError
from mop.iam.dependencies import get_current_user
from mop.iam.models import User
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/core", tags=["core"])


def service(session: Session = Depends(get_session)) -> OrganizationService:
    return OrganizationService(session)


def authorization(session: Session = Depends(get_session)) -> AuthorizationService:
    return AuthorizationService(session)


def _translate_write(operation):
    try:
        return operation()
    except CoreParentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CoreConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _require(
    authz: AuthorizationService,
    user: User,
    permission_code: str,
    scope_type: str = "global",
    scope_id: UUID | None = None,
) -> None:
    try:
        authz.require(user.id, permission_code, scope_type, scope_id)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied") from exc


def _audit_create(
    *,
    session: Session,
    request: Request,
    user: User,
    action: str,
    object_type: str,
    object_id: UUID,
    scope_type: str | None = None,
    scope_id: UUID | None = None,
    details: dict | None = None,
) -> None:
    AuditService(session).record(
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        scope_type=scope_type,
        scope_id=scope_id,
        outcome="success",
        actor_user_id=user.id,
        actor_username=user.username,
        details=details,
        **request_audit_context(request),
    )


@router.post("/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    request: Request,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require(authz, user, "core.organization.write")
    created = _translate_write(lambda: app.create_organization(payload))
    _audit_create(
        session=session,
        request=request,
        user=user,
        action="core.organization.create",
        object_type="organization",
        object_id=created.id,
        details={"code": created.code},
    )
    return created


@router.get("/organizations", response_model=list[OrganizationRead])
def list_organizations(
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
):
    _require(authz, user, "core.organization.read")
    return app.list_organizations()


@router.post("/plants", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
def create_plant(
    payload: PlantCreate,
    request: Request,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require(authz, user, "core.plant.write", "organization", payload.organization_id)
    created = _translate_write(lambda: app.create_plant(payload))
    _audit_create(
        session=session,
        request=request,
        user=user,
        action="core.plant.create",
        object_type="plant",
        object_id=created.id,
        scope_type="organization",
        scope_id=payload.organization_id,
        details={"code": created.code},
    )
    return created


@router.get("/plants", response_model=list[PlantRead])
def list_plants(
    organization_id: UUID | None = None,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
):
    if organization_id is None:
        _require(authz, user, "core.plant.read")
    else:
        _require(authz, user, "core.plant.read", "organization", organization_id)
    return app.list_plants(organization_id)


@router.post("/areas", response_model=AreaRead, status_code=status.HTTP_201_CREATED)
def create_area(
    payload: AreaCreate,
    request: Request,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require(authz, user, "core.area.write", "plant", payload.plant_id)
    created = _translate_write(lambda: app.create_area(payload))
    _audit_create(
        session=session,
        request=request,
        user=user,
        action="core.area.create",
        object_type="area",
        object_id=created.id,
        scope_type="plant",
        scope_id=payload.plant_id,
        details={"code": created.code},
    )
    return created


@router.get("/areas", response_model=list[AreaRead])
def list_areas(
    plant_id: UUID | None = None,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
):
    if plant_id is None:
        _require(authz, user, "core.area.read")
    else:
        _require(authz, user, "core.area.read", "plant", plant_id)
    return app.list_areas(plant_id)


@router.post("/work-centers", response_model=WorkCenterRead, status_code=status.HTTP_201_CREATED)
def create_work_center(
    payload: WorkCenterCreate,
    request: Request,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require(authz, user, "core.workcenter.write", "area", payload.area_id)
    created = _translate_write(lambda: app.create_work_center(payload))
    _audit_create(
        session=session,
        request=request,
        user=user,
        action="core.workcenter.create",
        object_type="work_center",
        object_id=created.id,
        scope_type="area",
        scope_id=payload.area_id,
        details={"code": created.code},
    )
    return created


@router.get("/work-centers", response_model=list[WorkCenterRead])
def list_work_centers(
    area_id: UUID | None = None,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
):
    if area_id is None:
        _require(authz, user, "core.workcenter.read")
    else:
        _require(authz, user, "core.workcenter.read", "area", area_id)
    return app.list_work_centers(area_id)


@router.post("/resources", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    payload: ResourceCreate,
    request: Request,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require(authz, user, "core.resource.write", "work_center", payload.work_center_id)
    created = _translate_write(lambda: app.create_resource(payload))
    _audit_create(
        session=session,
        request=request,
        user=user,
        action="core.resource.create",
        object_type="resource",
        object_id=created.id,
        scope_type="work_center",
        scope_id=payload.work_center_id,
        details={"code": created.code, "resource_type": created.resource_type},
    )
    return created


@router.get("/resources", response_model=list[ResourceRead])
def list_resources(
    work_center_id: UUID | None = None,
    app: OrganizationService = Depends(service),
    authz: AuthorizationService = Depends(authorization),
    user: User = Depends(get_current_user),
):
    if work_center_id is None:
        _require(authz, user, "core.resource.read")
    else:
        _require(authz, user, "core.resource.read", "work_center", work_center_id)
    return app.list_resources(work_center_id)
