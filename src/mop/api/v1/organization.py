"""Organization / plant / area / work-center / resource API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/core", tags=["core"])


def service(session: Session = Depends(get_session)) -> OrganizationService:
    return OrganizationService(session)


def _translate_write(operation):
    try:
        return operation()
    except CoreParentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CoreConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreate, app: OrganizationService = Depends(service)):
    return _translate_write(lambda: app.create_organization(payload))


@router.get("/organizations", response_model=list[OrganizationRead])
def list_organizations(app: OrganizationService = Depends(service)):
    return app.list_organizations()


@router.post("/plants", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
def create_plant(payload: PlantCreate, app: OrganizationService = Depends(service)):
    return _translate_write(lambda: app.create_plant(payload))


@router.get("/plants", response_model=list[PlantRead])
def list_plants(organization_id: UUID | None = None, app: OrganizationService = Depends(service)):
    return app.list_plants(organization_id)


@router.post("/areas", response_model=AreaRead, status_code=status.HTTP_201_CREATED)
def create_area(payload: AreaCreate, app: OrganizationService = Depends(service)):
    return _translate_write(lambda: app.create_area(payload))


@router.get("/areas", response_model=list[AreaRead])
def list_areas(plant_id: UUID | None = None, app: OrganizationService = Depends(service)):
    return app.list_areas(plant_id)


@router.post("/work-centers", response_model=WorkCenterRead, status_code=status.HTTP_201_CREATED)
def create_work_center(payload: WorkCenterCreate, app: OrganizationService = Depends(service)):
    return _translate_write(lambda: app.create_work_center(payload))


@router.get("/work-centers", response_model=list[WorkCenterRead])
def list_work_centers(area_id: UUID | None = None, app: OrganizationService = Depends(service)):
    return app.list_work_centers(area_id)


@router.post("/resources", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate, app: OrganizationService = Depends(service)):
    return _translate_write(lambda: app.create_resource(payload))


@router.get("/resources", response_model=list[ResourceRead])
def list_resources(work_center_id: UUID | None = None, app: OrganizationService = Depends(service)):
    return app.list_resources(work_center_id)
