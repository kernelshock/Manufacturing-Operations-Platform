"""G6.2 — operational inventory sites, locations and immutable movement ledger."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from mop.persistence.base import Base


class MaterialWarehouse(Base):
    __tablename__ = "mat_warehouse"
    __table_args__ = (UniqueConstraint("plant_id", "code", name="uq_mat_warehouse_plant_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plant_id: Mapped[UUID] = mapped_column(ForeignKey("core_plant.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaterialLocation(Base):
    __tablename__ = "mat_location"
    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uq_mat_location_wh_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("mat_warehouse.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaterialMovement(Base):
    """Append-only signed posting. Reversals insert a separate opposite row."""
    __tablename__ = "mat_movement"
    __table_args__ = (
        UniqueConstraint("source_system", "idempotency_key", name="uq_mat_movement_source_idem"),
        UniqueConstraint("reversal_of_id", name="uq_mat_movement_reversal_once"),
        CheckConstraint("quantity > 0", name="ck_mat_movement_quantity_positive"),
        CheckConstraint("signed_quantity <> 0", name="ck_mat_movement_signed_nonzero"),
        CheckConstraint(
            "(kind IN ('OPENING', 'RECEIPT', 'ADJUSTMENT_IN') AND signed_quantity > 0) OR "
            "(kind IN ('ISSUE', 'ADJUSTMENT_OUT') AND signed_quantity < 0) OR "
            "(kind = 'REVERSAL' AND reversal_of_id IS NOT NULL)",
            name="ck_mat_movement_kind_sign"
        ),
        Index("ix_mat_movement_balance", "article_id", "location_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("mat_location.id", ondelete="RESTRICT"), nullable=False)
    uom_id: Mapped[UUID] = mapped_column(ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    reversal_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("mat_movement.id", ondelete="RESTRICT"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
