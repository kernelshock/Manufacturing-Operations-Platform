"""Application service for organizational master data."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.core.models import Area, Organization, Plant, Resource, WorkCenter
from mop.core.schemas import AreaCreate, OrganizationCreate, PlantCreate, ResourceCreate, WorkCenterCreate


class CoreConflictError(ValueError):
    """Raised when a contextual business-code uniqueness rule is violated."""


class CoreParentNotFoundError(LookupError):
    """Raised when a requested parent aggregate does not exist."""


class OrganizationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit(self, entity):
        try:
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.session.rollback()
            raise CoreConflictError("business code already exists in this parent scope") from exc

    def create_organization(self, data: OrganizationCreate) -> Organization:
        return self._commit(Organization(**data.model_dump()))

    def create_plant(self, data: PlantCreate) -> Plant:
        if self.session.get(Organization, data.organization_id) is None:
            raise CoreParentNotFoundError("organization not found")
        return self._commit(Plant(**data.model_dump()))

    def create_area(self, data: AreaCreate) -> Area:
        if self.session.get(Plant, data.plant_id) is None:
            raise CoreParentNotFoundError("plant not found")
        return self._commit(Area(**data.model_dump()))

    def create_work_center(self, data: WorkCenterCreate) -> WorkCenter:
        if self.session.get(Area, data.area_id) is None:
            raise CoreParentNotFoundError("area not found")
        return self._commit(WorkCenter(**data.model_dump()))

    def create_resource(self, data: ResourceCreate) -> Resource:
        if self.session.get(WorkCenter, data.work_center_id) is None:
            raise CoreParentNotFoundError("work center not found")
        payload = data.model_dump()
        payload["resource_type"] = payload["resource_type"].strip().lower()
        return self._commit(Resource(**payload))

    def list_organizations(self) -> Sequence[Organization]:
        return self.session.scalars(select(Organization).order_by(Organization.code)).all()

    def list_plants(self, organization_id: UUID | None = None) -> Sequence[Plant]:
        query = select(Plant)
        if organization_id is not None:
            query = query.where(Plant.organization_id == organization_id)
        return self.session.scalars(query.order_by(Plant.code)).all()

    def list_areas(self, plant_id: UUID | None = None) -> Sequence[Area]:
        query = select(Area)
        if plant_id is not None:
            query = query.where(Area.plant_id == plant_id)
        return self.session.scalars(query.order_by(Area.code)).all()

    def list_work_centers(self, area_id: UUID | None = None) -> Sequence[WorkCenter]:
        query = select(WorkCenter)
        if area_id is not None:
            query = query.where(WorkCenter.area_id == area_id)
        return self.session.scalars(query.order_by(WorkCenter.code)).all()

    def list_resources(self, work_center_id: UUID | None = None) -> Sequence[Resource]:
        query = select(Resource)
        if work_center_id is not None:
            query = query.where(Resource.work_center_id == work_center_id)
        return self.session.scalars(query.order_by(Resource.code)).all()
