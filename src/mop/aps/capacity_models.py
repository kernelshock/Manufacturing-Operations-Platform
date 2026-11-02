"""Capacity projection models for G4.3."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class CapacityCandidate(Base):
    __tablename__ = "aps_capacity_candidate"
    __table_args__ = (
        UniqueConstraint("run_id", "planning_operation_id", "resource_id", name="uq_aps_capacity_candidate_source"),
        CheckConstraint("source_mode IN ('EXPLICIT_ASSIGNMENT', 'WORK_CENTER_POOL')", name="ck_aps_capacity_candidate_source_mode"),
        CheckConstraint("assignment_capacity_factor > 0", name="ck_aps_capacity_candidate_assignment_factor"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=False)
    planning_operation_id: Mapped[UUID] = mapped_column(ForeignKey("aps_planning_operation.id", ondelete="RESTRICT"), nullable=False)
    routing_operation_id: Mapped[UUID] = mapped_column(ForeignKey("md_routing_operation.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_assignment_id: Mapped[UUID | None] = mapped_column(ForeignKey("md_resource_assignment.id", ondelete="RESTRICT"), nullable=True)
    assignment_capacity_factor: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)


class ResourceAvailabilityInterval(Base):
    __tablename__ = "aps_resource_availability_interval"
    __table_args__ = (
        UniqueConstraint("run_id", "resource_id", "start_at", "end_at", name="uq_aps_resource_availability_interval"),
        CheckConstraint("end_at > start_at", name="ck_aps_resource_availability_interval_shape"),
        CheckConstraint("calendar_capacity_factor > 0", name="ck_aps_resource_availability_calendar_factor"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False)
    calendar_id: Mapped[UUID] = mapped_column(ForeignKey("md_manufacturing_calendar.id", ondelete="RESTRICT"), nullable=False)
    calendar_code: Mapped[str] = mapped_column(String(80), nullable=False)
    calendar_revision_no: Mapped[int] = mapped_column(nullable=False)
    target_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calendar_capacity_factor: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
