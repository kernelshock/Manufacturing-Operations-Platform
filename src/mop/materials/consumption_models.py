"""G6.4 measured consumption bound to G5 execution and G6 immutable ledger."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from mop.persistence.base import Base


class MaterialConsumption(Base):
    __tablename__ = "mat_consumption"
    __table_args__ = (
        CheckConstraint("kind IN ('CONSUME', 'REVERSE')", name="ck_mat_consumption_kind"),
        CheckConstraint("quantity > 0", name="ck_mat_consumption_positive"),
        CheckConstraint(
            "(kind = 'CONSUME' AND reversal_of_id IS NULL AND reason_code IS NULL) OR "
            "(kind = 'REVERSE' AND reversal_of_id IS NOT NULL AND reason_code IS NOT NULL)",
            name="ck_mat_consumption_reversal_shape",
        ),
        UniqueConstraint("idempotency_key", name="uq_mat_consumption_idempotency"),
        UniqueConstraint("stock_movement_id", name="uq_mat_consumption_stock_movement"),
        UniqueConstraint("reversal_of_id", name="uq_mat_consumption_reversal_once"),
        Index("ix_mat_consumption_operation", "execution_operation_id", "created_at"),
        Index("ix_mat_consumption_article", "article_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    execution_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False
    )
    article_id: Mapped[UUID] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("mat_location.id", ondelete="RESTRICT"), nullable=False)
    uom_id: Mapped[UUID] = mapped_column(ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    stock_movement_id: Mapped[UUID] = mapped_column(
        ForeignKey("mat_movement.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    reversal_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mat_consumption.id", ondelete="RESTRICT"), nullable=True
    )
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
