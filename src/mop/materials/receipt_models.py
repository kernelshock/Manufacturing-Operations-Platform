"""Persistent receipt identity and immutable lot decisions."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class MaterialReceiptLot(Base):
    __tablename__ = "mat_receipt_lot"
    __table_args__ = (
        UniqueConstraint("receipt_line_ref", "lot_ref", name="uq_mat_receipt_lot_reference"),
        Index("ix_mat_receipt_lot_stock", "article_id", "location_id"),
        CheckConstraint("quantity > 0", name="ck_mat_receipt_lot_quantity"),
        Index("ix_mat_receipt_lot_purchase_evidence", "purchase_order_evidence_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    receipt_line_ref: Mapped[str] = mapped_column(String(128))
    lot_ref: Mapped[str] = mapped_column(String(128))
    article_id: Mapped[UUID] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"))
    location_id: Mapped[UUID] = mapped_column(ForeignKey("mat_location.id", ondelete="RESTRICT"))
    uom_id: Mapped[UUID] = mapped_column(ForeignKey("md_uom.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    purchase_order_evidence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("int_proc_evidence_event.id", ondelete="RESTRICT"),
    )
    movement_id: Mapped[UUID] = mapped_column(ForeignKey("mat_movement.id", ondelete="RESTRICT"), unique=True)


class MaterialReceiptDecision(Base):
    __tablename__ = "mat_receipt_decision"
    __table_args__ = (
        UniqueConstraint("lot_id", "revision", name="uq_mat_receipt_decision_revision"),
        UniqueConstraint("lot_id", "decision_ref", name="uq_mat_receipt_decision_reference"),
        CheckConstraint("quantity > 0 AND revision > 0", name="ck_mat_receipt_decision_values"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("mat_receipt_lot.id", ondelete="RESTRICT"))
    revision: Mapped[int]
    action: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(24))
    decision_ref: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    verified_release_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    movement_id: Mapped[UUID | None] = mapped_column(ForeignKey("mat_movement.id", ondelete="RESTRICT"), unique=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
