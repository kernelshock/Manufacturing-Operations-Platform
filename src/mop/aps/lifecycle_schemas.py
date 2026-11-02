"""Schemas for G4.5 schedule lifecycle, replan and publication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mop.aps.schemas import SchedulingRunRead


class ReplanCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)
    algorithm_key: str | None = Field(default=None, min_length=1, max_length=80)
    algorithm_version: str | None = Field(default=None, min_length=1, max_length=80)


class PublishScheduleRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=4000)


class SchedulePublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scenario_id: UUID
    run_id: UUID
    version_no: int
    status: str
    supersedes_publication_id: UUID | None
    publish_reason: str | None
    schedule_fingerprint: str
    published_by: UUID | None
    published_at: datetime


class ReplanResult(BaseModel):
    source_run_id: UUID
    run: SchedulingRunRead


class PublishResult(BaseModel):
    publication: SchedulePublicationRead
    superseded_publication_id: UUID | None
    idempotent_replay: bool
