"""Published schedule lifecycle models for G4.5."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class SchedulePublication(Base):
    __tablename__ = "aps_schedule_publication"
    __table_args__ = (
        UniqueConstraint("scenario_id", "version_no", name="uq_aps_publication_scenario_version"),
        UniqueConstraint("run_id", name="uq_aps_publication_run"),
        CheckConstraint("version_no > 0", name="ck_aps_publication_version_positive"),
        CheckConstraint("status IN ('CURRENT', 'SUPERSEDED')", name="ck_aps_publication_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_scenario.id", ondelete="RESTRICT"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CURRENT")
    supersedes_publication_id: Mapped[UUID | None] = mapped_column(ForeignKey("aps_schedule_publication.id", ondelete="RESTRICT"), nullable=True)
    publish_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublishedScheduledOperation(Base):
    __tablename__ = "aps_published_scheduled_operation"
    __table_args__ = (
        UniqueConstraint("publication_id", "source_scheduled_operation_id", name="uq_aps_published_operation_source"),
        CheckConstraint("planned_finish > planned_start", name="ck_aps_published_operation_interval"),
        CheckConstraint("sequence_no > 0", name="ck_aps_published_operation_sequence_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(ForeignKey("aps_schedule_publication.id", ondelete="RESTRICT"), nullable=False)
    source_scheduled_operation_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduled_operation.id", ondelete="RESTRICT"), nullable=False)
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


class PublishedScheduledOperationSegment(Base):
    __tablename__ = "aps_published_scheduled_operation_segment"
    __table_args__ = (
        UniqueConstraint("published_operation_id", "segment_no", name="uq_aps_published_segment_number"),
        CheckConstraint("segment_no > 0", name="ck_aps_published_segment_number_positive"),
        CheckConstraint("end_at > start_at", name="ck_aps_published_segment_interval"),
        CheckConstraint("effective_rate_per_hour > 0", name="ck_aps_published_segment_rate_positive"),
        CheckConstraint("produced_quantity > 0", name="ck_aps_published_segment_quantity_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    published_operation_id: Mapped[UUID] = mapped_column(ForeignKey("aps_published_scheduled_operation.id", ondelete="RESTRICT"), nullable=False)
    source_segment_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduled_operation_segment.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False)
    segment_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    produced_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
