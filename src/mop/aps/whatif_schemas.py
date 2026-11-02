"""Schemas for G4.7 what-if and exception evaluation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WhatIfCreate(BaseModel):
    scenario_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    baseline_publication_id: UUID


class WhatIfExceptionCreate(BaseModel):
    exception_type: str
    resource_id: UUID
    start_at: datetime
    end_at: datetime
    capacity_factor: Decimal | None = None
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        if self.exception_type == "RESOURCE_BLACKOUT":
            if self.capacity_factor is not None:
                raise ValueError("RESOURCE_BLACKOUT cannot define capacity_factor")
        elif self.exception_type == "RESOURCE_CAPACITY_FACTOR":
            if self.capacity_factor is None or self.capacity_factor <= 0:
                raise ValueError("RESOURCE_CAPACITY_FACTOR requires capacity_factor > 0")
        else:
            raise ValueError("unsupported what-if exception_type")
        return self


class WhatIfExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    whatif_scenario_id: UUID
    exception_type: str
    resource_id: UUID
    start_at: datetime
    end_at: datetime
    capacity_factor: Decimal | None
    reason: str
    created_at: datetime


class WhatIfScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scenario_code: str
    name: str
    description: str | None
    baseline_publication_id: UUID
    baseline_run_id: UUID
    candidate_run_id: UUID | None
    status: str
    created_by: UUID | None
    created_at: datetime
    evaluated_at: datetime | None
    applied_publication_id: UUID | None
    applied_at: datetime | None
    discarded_at: datetime | None


class WhatIfComparisonRead(BaseModel):
    whatif_scenario_id: UUID
    baseline_publication_id: UUID
    baseline_run_id: UUID
    candidate_run_id: UUID
    baseline_operation_count: int
    candidate_operation_count: int
    added_operation_count: int
    removed_operation_count: int
    timing_changed_count: int
    resource_changed_count: int
    baseline_start: datetime
    baseline_finish: datetime
    candidate_start: datetime
    candidate_finish: datetime
    makespan_delta_seconds: Decimal
    exception_count: int


class WhatIfEvaluationResult(BaseModel):
    scenario: WhatIfScenarioRead
    comparison: WhatIfComparisonRead


class WhatIfApplyResult(BaseModel):
    scenario: WhatIfScenarioRead
    publication_id: UUID
    superseded_publication_id: UUID | None
