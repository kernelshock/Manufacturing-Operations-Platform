"""G5.1 MES execution dispatch foundation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class ExecutionDispatch(Base):
    __tablename__ = "mes_execution_dispatch"
    __table_args__ = (
        UniqueConstraint("publication_id", name="uq_mes_dispatch_publication"),
        CheckConstraint(
            "status IN ('DRAFT', 'RELEASED', 'CANCELLED')",
            name="ck_mes_dispatch_status",
        ),
        CheckConstraint(
            "(status = 'RELEASED' AND released_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL) OR "
            "status = 'DRAFT'",
            name="ck_mes_dispatch_lifecycle",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dispatch_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    publication_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_schedule_publication.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_scheduling_scenario.id", ondelete="RESTRICT"),
        nullable=False,
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_scheduling_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("demand_production_plan.id", ondelete="RESTRICT"),
        nullable=False,
    )
    publication_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExecutionOperation(Base):
    __tablename__ = "mes_execution_operation"
    __table_args__ = (
        UniqueConstraint(
            "dispatch_id",
            "published_operation_id",
            name="uq_mes_execution_operation_published",
        ),
        CheckConstraint("routing_sequence_no > 0", name="ck_mes_execution_routing_sequence_positive"),
        CheckConstraint("product_sequence_no > 0", name="ck_mes_execution_product_sequence_positive"),
        CheckConstraint("requested_quantity > 0", name="ck_mes_execution_requested_quantity_positive"),
        CheckConstraint("planned_finish > planned_start", name="ck_mes_execution_planned_interval"),
        CheckConstraint("status IN ('PENDING')", name="ck_mes_execution_operation_status_g5_1"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dispatch_id: Mapped[UUID] = mapped_column(
        ForeignKey("mes_execution_dispatch.id", ondelete="RESTRICT"), nullable=False
    )
    publication_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_schedule_publication.id", ondelete="RESTRICT"), nullable=False
    )
    published_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_published_scheduled_operation.id", ondelete="RESTRICT"),
        nullable=False,
    )
    planning_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("aps_planning_operation.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("demand_production_plan.id", ondelete="RESTRICT"), nullable=False
    )
    taquilla_id: Mapped[UUID] = mapped_column(
        ForeignKey("demand_taquilla.id", ondelete="RESTRICT"), nullable=False
    )
    product_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("demand_taquilla_product_line.id", ondelete="RESTRICT"), nullable=False
    )
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False
    )
    routing_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_routing_revision.id", ondelete="RESTRICT"), nullable=False
    )
    routing_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_routing_operation.id", ondelete="RESTRICT"), nullable=False
    )
    planned_resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False
    )
    area_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core_area.id", ondelete="RESTRICT"), nullable=True
    )
    work_center_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core_work_center.id", ondelete="RESTRICT"), nullable=True
    )
    deck_position: Mapped[str] = mapped_column(String(20), nullable=False)
    product_sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    routing_sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_code: Mapped[str] = mapped_column(String(30), nullable=False)
    operation_description: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_finish: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
