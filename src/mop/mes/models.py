"""G5.1 MES execution dispatch foundation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
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
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED')",
            name="ck_mes_execution_operation_status",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND actual_start IS NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
            "(status IN ('RUNNING', 'PAUSED') AND actual_start IS NOT NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
            "(status = 'COMPLETED' AND actual_start IS NOT NULL AND actual_finish IS NOT NULL AND produced_quantity IS NOT NULL)",
            name="ck_mes_execution_operation_lifecycle",
        ),
        CheckConstraint(
            "actual_finish IS NULL OR actual_finish >= actual_start",
            name="ck_mes_execution_actual_interval",
        ),
        CheckConstraint(
            "produced_quantity IS NULL OR produced_quantity > 0",
            name="ck_mes_execution_produced_quantity_positive",
        ),
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
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_finish: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    produced_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    started_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    completed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    actual_resource_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=True
    )
    resource_deviation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class ExecutionOperationEvent(Base):
    __tablename__ = "mes_execution_operation_event"
    __table_args__ = (
        UniqueConstraint(
            "execution_operation_id",
            "event_type",
            name="uq_mes_execution_operation_event_type",
        ),
        CheckConstraint(
            "event_type IN ('START', 'COMPLETE')",
            name="ck_mes_execution_operation_event_type_g5_2",
        ),
        CheckConstraint(
            "(event_type = 'START' AND produced_quantity IS NULL) OR "
            "(event_type = 'COMPLETE' AND produced_quantity IS NOT NULL AND produced_quantity > 0)",
            name="ck_mes_execution_operation_event_quantity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    execution_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    produced_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class ExecutionSetup(Base):
    __tablename__ = "mes_execution_setup"
    __table_args__ = (
        UniqueConstraint("execution_operation_id", name="uq_mes_execution_setup_operation"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_mes_execution_setup_interval",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    execution_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    finished_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExecutionInterruption(Base):
    __tablename__ = "mes_execution_interruption"
    __table_args__ = (
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_mes_execution_interruption_interval",
        ),
        CheckConstraint(
            "length(trim(reason_code)) > 0",
            name="ck_mes_execution_interruption_reason_code",
        ),
        Index(
            "uq_mes_execution_open_interruption",
            "execution_operation_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    execution_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    ended_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
