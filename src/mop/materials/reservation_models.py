"""G6.5 — append-only allocation/release events, independent of physical stock."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from mop.persistence.base import Base


class MaterialReservationEvent(Base):
    __tablename__ = "mat_reservation_event"
    __table_args__ = (
        CheckConstraint("kind IN ('HOLD', 'RELEASE')", name="ck_mat_res_kind"),
        CheckConstraint("quantity > 0", name="ck_mat_res_positive"),
        CheckConstraint(
            "(kind = 'HOLD' AND release_of_id IS NULL AND reason_code IS NULL) OR "
            "(kind = 'RELEASE' AND release_of_id IS NOT NULL AND reason_code IS NOT NULL)",
            name="ck_mat_res_shape",
        ),
        UniqueConstraint("idempotency_key", name="uq_mat_res_idempotency"),
        Index("ix_mat_res_article_location", "article_id", "location_id"),
        Index("ix_mat_res_taquilla_article", "taquilla_id", "article_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("demand_production_plan.id", ondelete="RESTRICT"), nullable=False)
    taquilla_id: Mapped[UUID] = mapped_column(ForeignKey("demand_taquilla.id", ondelete="RESTRICT"), nullable=False)
    article_id: Mapped[UUID] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("mat_location.id", ondelete="RESTRICT"), nullable=False)
    uom_id: Mapped[UUID] = mapped_column(ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    bom_effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    release_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mat_reservation_event.id", ondelete="RESTRICT"), nullable=True
    )
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
