"""G6.6 — source-evidenced procurement transcription for legacy Prolowin."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
    Integer, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint, func, text
)
from sqlalchemy.orm import Mapped, mapped_column
from mop.persistence.base import Base


class ProcurementCapture(Base):
    __tablename__ = "int_proc_capture"
    __table_args__ = (
        CheckConstraint("source_type IN ('MANUAL', 'SCREENSHOT', 'WEEKLY_SNAPSHOT')", name="ck_proc_cap_kind"),
        CheckConstraint("image_bytes IS NULL OR octet_length(image_bytes) <= 4194304", name="ck_proc_cap_image_size"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(150), nullable=False)
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    image_mime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    captured_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementEvidenceEvent(Base):
    __tablename__ = "int_proc_evidence_event"
    __table_args__ = (
        CheckConstraint("kind IN ('ORDER', 'RECEIPT', 'RESCHEDULE', 'CLAIM', 'ESCALATION')", name="ck_proc_event_kind"),
        CheckConstraint("review_status IN ('PENDING', 'VERIFIED', 'REJECTED')", name="ck_proc_event_status"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_proc_event_quantity"),
        CheckConstraint("accepted_quantity IS NULL OR (quantity IS NOT NULL AND accepted_quantity >= 0 AND accepted_quantity <= quantity)", name="ck_proc_event_accepted"),
        CheckConstraint(
            "(review_status = 'PENDING' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR "
            "(review_status <> 'PENDING' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_proc_event_review",
        ),
        UniqueConstraint("source_event_key", name="uq_proc_event_source_key"),
        Index("uq_proc_event_verified_business_key", "po_number", "line_number", "kind", "source_reference", unique=True, postgresql_where=text("review_status = 'VERIFIED'")),
        Index("ix_proc_event_order_line", "po_number", "line_number", "review_status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    capture_id: Mapped[UUID] = mapped_column(ForeignKey("int_proc_capture.id", ondelete="RESTRICT"), nullable=False)
    source_event_key: Mapped[str] = mapped_column(String(180), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    po_number: Mapped[str] = mapped_column(String(80), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_code: Mapped[str] = mapped_column(String(80), nullable=False)
    article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    uom_code: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    accepted_quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_promise_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revised_promise_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    continuity_safe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    mapped_supplier_id: Mapped[UUID | None] = mapped_column(ForeignKey("md_supplier.id", ondelete="RESTRICT"), nullable=True)
    mapped_article_id: Mapped[UUID | None] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=True)
    mapped_uom_id: Mapped[UUID | None] = mapped_column(ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(12), nullable=False, default="PENDING")
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
