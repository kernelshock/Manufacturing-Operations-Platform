"""Transport schemas for G4 APS foundation."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ScenarioStatus = Literal["DRAFT", "READY", "ARCHIVED"]
RunStatus = Literal["CREATED", "EXPANDED", "CAPACITY_PROJECTED", "SCHEDULED", "CANCELLED"]


def _trim(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("value must not be empty")
    return value


class SchedulingScenarioCreate(BaseModel):
    plan_id: UUID
    scenario_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    horizon_start: datetime
    horizon_end: datetime
    planning_timezone: str = Field(min_length=1, max_length=80)

    _code = field_validator("scenario_code")(_trim)
    _name = field_validator("name")(_trim)
    _timezone = field_validator("planning_timezone")(_trim)

    @field_validator("planning_timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("planning_timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("horizon_start", "horizon_end")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planning horizon timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def valid_horizon(self):
        if self.horizon_end <= self.horizon_start:
            raise ValueError("horizon_end must be after horizon_start")
        return self


class SchedulingScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    plan_id: UUID
    scenario_code: str
    name: str
    description: str | None
    horizon_start: datetime
    horizon_end: datetime
    planning_timezone: str
    status: ScenarioStatus
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class SchedulingScenarioHorizonUpdate(BaseModel):
    horizon_start: datetime
    horizon_end: datetime
    planning_timezone: str = Field(min_length=1, max_length=80)

    @field_validator("planning_timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        value = _trim(value)
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("planning_timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("horizon_start", "horizon_end")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planning horizon timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def valid_horizon(self):
        if self.horizon_end <= self.horizon_start:
            raise ValueError("horizon_end must be after horizon_start")
        return self


class SchedulingScenarioStatusUpdate(BaseModel):
    status: ScenarioStatus


class SchedulingRunCreate(BaseModel):
    algorithm_key: str = Field(min_length=1, max_length=80)
    algorithm_version: str = Field(min_length=1, max_length=80)
    _algorithm_key = field_validator("algorithm_key")(_trim)
    _algorithm_version = field_validator("algorithm_version")(_trim)


class SchedulingRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scenario_id: UUID
    run_number: int
    algorithm_key: str
    algorithm_version: str
    status: RunStatus
    input_fingerprint: str | None
    expanded_at: datetime | None
    operation_count: int
    replan_from_run_id: UUID | None
    replan_reason: str | None
    created_by: UUID | None
    created_at: datetime
