"""Finite-capacity schedule models for G4.4."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class ScheduledOperation(Base):
    __tablename__ = "aps_scheduled_operation"
    __table_args__ = (
        UniqueConstraint("run_id", "planning_operation_id", name="uq_aps_scheduled_operation_source"),
        CheckConstraint("planned_finish > planned_start", name="ck_aps_scheduled_operation_interval"),
        CheckConstraint("processing_seconds > 0", name="ck_aps_scheduled_operation_processing_positive"),
        CheckConstraint("sequence_no > 0", name="ck_aps_scheduled_operation_sequence_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=False)
    planning_operation_id: Mapped[UUID] = mapped_column(ForeignKey("aps_planning_operation.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_finish: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_seconds: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    nominal_rate: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    normalized_rate_uom: Mapped[str] = mapped_column(String(40), nullable=False)
    algorithm_key: Mapped[str] = mapped_column(String(80), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)


class ScheduledOperationSegment(Base):
    __tablename__ = "aps_scheduled_operation_segment"
    __table_args__ = (
        UniqueConstraint("scheduled_operation_id", "segment_no", name="uq_aps_schedule_segment_number"),
        CheckConstraint("segment_no > 0", name="ck_aps_schedule_segment_number_positive"),
        CheckConstraint("end_at > start_at", name="ck_aps_schedule_segment_interval"),
        CheckConstraint("effective_rate_per_hour > 0", name="ck_aps_schedule_segment_rate_positive"),
        CheckConstraint("produced_quantity > 0", name="ck_aps_schedule_segment_quantity_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheduled_operation_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduled_operation.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False)
    availability_interval_id: Mapped[UUID] = mapped_column(ForeignKey("aps_resource_availability_interval.id", ondelete="RESTRICT"), nullable=False)
    segment_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    produced_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
