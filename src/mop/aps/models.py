"""Persistence models for G4 APS."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mop.persistence.base import Base


class SchedulingScenario(Base):
    __tablename__ = "aps_scheduling_scenario"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'READY', 'ARCHIVED')", name="ck_aps_scenario_status"),
        CheckConstraint("horizon_end > horizon_start", name="ck_aps_scenario_horizon"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("demand_production_plan.id", ondelete="RESTRICT"), nullable=False, index=True)
    scenario_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planning_timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    runs: Mapped[list["SchedulingRun"]] = relationship(back_populates="scenario")


class SchedulingRun(Base):
    __tablename__ = "aps_scheduling_run"
    __table_args__ = (
        UniqueConstraint("scenario_id", "run_number", name="uq_aps_run_scenario_number"),
        CheckConstraint("run_number > 0", name="ck_aps_run_number_positive"),
        CheckConstraint("status IN ('CREATED', 'CANCELLED')", name="ck_aps_run_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_scenario.id", ondelete="RESTRICT"), nullable=False, index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_key: Mapped[str] = mapped_column(String(80), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CREATED")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scenario: Mapped[SchedulingScenario] = relationship(back_populates="runs")
