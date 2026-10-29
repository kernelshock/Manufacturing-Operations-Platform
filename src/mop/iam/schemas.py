"""Identity and authorization schemas."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ScopeType = Literal["global", "organization", "plant", "area"]


def _normalize_username(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("username must not be empty")
    return normalized


def _normalize_role_code(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("role code must not be empty")
    return normalized


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)

    _username = field_validator("username")(_normalize_username)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=512)
    enabled: bool = True

    _username = field_validator("username")(_normalize_username)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    enabled: bool


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

    _code = field_validator("code")(_normalize_role_code)


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    active: bool
    system: bool


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    description: str


class RoleAssignmentCreate(BaseModel):
    role_id: UUID
    scope_type: ScopeType = "global"
    scope_id: UUID | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "RoleAssignmentCreate":
        if self.scope_type == "global" and self.scope_id is not None:
            raise ValueError("global scope must not have scope_id")
        if self.scope_type != "global" and self.scope_id is None:
            raise ValueError("scoped assignment requires scope_id")
        return self


class RoleAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    role_id: UUID
    scope_type: str
    scope_id: UUID | None


class CurrentUserRead(UserRead):
    permissions: list[str]
