"""Transport-independent schemas for the organizational core."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("code must not be empty")
    return normalized


class CoreEntityCreate(BaseModel):
    code: str = Field(max_length=64)
    name: str = Field(min_length=1, max_length=255)
    active: bool = True

    _normalize = field_validator("code")(_normalize_code)


class OrganizationCreate(CoreEntityCreate):
    pass


class PlantCreate(CoreEntityCreate):
    organization_id: UUID


class AreaCreate(CoreEntityCreate):
    plant_id: UUID


class WorkCenterCreate(CoreEntityCreate):
    area_id: UUID


class ResourceCreate(CoreEntityCreate):
    work_center_id: UUID
    resource_type: str = Field(default="generic", min_length=1, max_length=64)


class OrganizationRead(CoreEntityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class PlantRead(CoreEntityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID


class AreaRead(CoreEntityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    plant_id: UUID


class WorkCenterRead(CoreEntityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    area_id: UUID


class ResourceRead(CoreEntityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    work_center_id: UUID
    resource_type: str
