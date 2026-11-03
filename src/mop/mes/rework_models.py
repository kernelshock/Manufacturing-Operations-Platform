"""G5.5 governed rework cases and alternate execution route steps."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class ReworkCase(Base):
    __tablename__ = "mes_rework_case"
    __table_args__ = (
        UniqueConstraint("dispatch_id", "case_code", name="uq_mes_rework_dispatch_case"),
        CheckConstraint("quantity > 0", name="ck_mes_rework_case_quantity"),
        CheckConstraint("status IN ('OPEN', 'IN_PROGRESS', 'READY_TO_RETURN', 'RETURNED', 'CANCELLED')", name="ck_mes_rework_case_status"),
        CheckConstraint("(status = 'RETURNED' AND returned_at IS NOT NULL) OR (status <> 'RETURNED' AND returned_at IS NULL)", name="ck_mes_rework_case_return_state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dispatch_id: Mapped[UUID] = mapped_column(ForeignKey("mes_execution_dispatch.id", ondelete="RESTRICT"), nullable=False)
    product_line_id: Mapped[UUID] = mapped_column(ForeignKey("demand_taquilla_product_line.id", ondelete="RESTRICT"), nullable=False)
    source_execution_operation_id: Mapped[UUID] = mapped_column(ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False)
    return_execution_operation_id: Mapped[UUID] = mapped_column(ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False)
    case_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)


class ReworkStep(Base):
    __tablename__ = "mes_rework_step"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_no", name="uq_mes_rework_step_sequence"),
        CheckConstraint("sequence_no > 0", name="ck_mes_rework_step_sequence"),
        CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED')", name="ck_mes_rework_step_status"),
        CheckConstraint(
            "(status = 'PENDING' AND actual_start IS NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
            "(status = 'RUNNING' AND actual_start IS NOT NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
            "(status = 'COMPLETED' AND actual_start IS NOT NULL AND actual_finish IS NOT NULL AND produced_quantity IS NOT NULL)",
            name="ck_mes_rework_step_lifecycle",
        ),
        CheckConstraint("actual_finish IS NULL OR actual_finish >= actual_start", name="ck_mes_rework_step_interval"),
        CheckConstraint("produced_quantity IS NULL OR produced_quantity > 0", name="ck_mes_rework_step_quantity"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("mes_rework_case.id", ondelete="RESTRICT"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    routing_operation_id: Mapped[UUID] = mapped_column(ForeignKey("md_routing_operation.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("core_resource.id", ondelete="RESTRICT"), nullable=False)
    operation_code: Mapped[str] = mapped_column(String(30), nullable=False)
    operation_description: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_finish: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    produced_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    started_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)
    completed_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
