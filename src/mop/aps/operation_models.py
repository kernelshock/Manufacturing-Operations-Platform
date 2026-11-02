"""Immutable operation snapshots for G4.2."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class PlanningOperation(Base):
    __tablename__ = "aps_planning_operation"
    __table_args__ = (
        UniqueConstraint("run_id", "product_line_id", "routing_operation_id", name="uq_aps_planning_operation_source"),
        CheckConstraint("routing_sequence_no > 0", name="ck_aps_planning_operation_sequence_positive"),
        CheckConstraint("requested_quantity > 0", name="ck_aps_planning_operation_quantity_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("demand_production_plan.id", ondelete="RESTRICT"), nullable=False)
    taquilla_id: Mapped[UUID] = mapped_column(ForeignKey("demand_taquilla.id", ondelete="RESTRICT"), nullable=False)
    product_line_id: Mapped[UUID] = mapped_column(ForeignKey("demand_taquilla_product_line.id", ondelete="RESTRICT"), nullable=False)
    article_id: Mapped[UUID] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False)
    routing_revision_id: Mapped[UUID] = mapped_column(ForeignKey("md_routing_revision.id", ondelete="RESTRICT"), nullable=False)
    routing_operation_id: Mapped[UUID] = mapped_column(ForeignKey("md_routing_operation.id", ondelete="RESTRICT"), nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    deck_position: Mapped[str] = mapped_column(String(20), nullable=False)
    product_sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    routing_sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_operation_code: Mapped[str] = mapped_column(String(30), nullable=False)
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    operation_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    schedulable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    completion_marker: Mapped[bool] = mapped_column(Boolean, nullable=False)
    area_id: Mapped[UUID | None] = mapped_column(ForeignKey("core_area.id", ondelete="RESTRICT"), nullable=True)
    work_center_id: Mapped[UUID | None] = mapped_column(ForeignKey("core_work_center.id", ondelete="RESTRICT"), nullable=True)
    nominal_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    rate_uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    routing_source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
