"""Isolated what-if models for G4.7."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class WhatIfScenario(Base):
    __tablename__ = "aps_whatif_scenario"
    __table_args__ = (
        UniqueConstraint("scenario_code", name="uq_aps_whatif_scenario_code"),
        CheckConstraint(
            "status IN ('DRAFT', 'EVALUATED', 'APPLIED', 'DISCARDED')",
            name="ck_aps_whatif_status",
        ),
        CheckConstraint(
            "(status = 'EVALUATED' AND candidate_run_id IS NOT NULL AND evaluated_at IS NOT NULL) "
            "OR (status = 'APPLIED' AND candidate_run_id IS NOT NULL AND evaluated_at IS NOT NULL AND applied_publication_id IS NOT NULL AND applied_at IS NOT NULL) "
            "OR (status = 'DISCARDED' AND discarded_at IS NOT NULL) "
            "OR status = 'DRAFT'",
            name="ck_aps_whatif_lifecycle",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scenario_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_publication_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_schedule_publication.id", ondelete="RESTRICT"), nullable=False
    )
    baseline_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_publication_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("aps_schedule_publication.id", ondelete="RESTRICT"), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WhatIfException(Base):
    __tablename__ = "aps_whatif_exception"
    __table_args__ = (
        CheckConstraint(
            "exception_type IN ('RESOURCE_BLACKOUT', 'RESOURCE_CAPACITY_FACTOR')",
            name="ck_aps_whatif_exception_type",
        ),
        CheckConstraint("end_at > start_at", name="ck_aps_whatif_exception_interval"),
        CheckConstraint(
            "(exception_type = 'RESOURCE_BLACKOUT' AND capacity_factor IS NULL) OR "
            "(exception_type = 'RESOURCE_CAPACITY_FACTOR' AND capacity_factor > 0)",
            name="ck_aps_whatif_exception_payload",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    whatif_scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_whatif_scenario.id", ondelete="RESTRICT"), nullable=False
    )
    exception_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity_factor: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
