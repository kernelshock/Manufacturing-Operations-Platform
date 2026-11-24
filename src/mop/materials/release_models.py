"""Immutable signing credentials, inspection policies and release evidence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class ReceiptSignerKey(Base):
    __tablename__ = "mat_receipt_signer_key"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    public_key: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    identity_reference: Mapped[str] = mapped_column(String(128))
    registered_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReceiptSignerRevocation(Base):
    __tablename__ = "mat_receipt_signer_revocation"

    key_id: Mapped[UUID] = mapped_column(ForeignKey("mat_receipt_signer_key.id", ondelete="RESTRICT"), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(String(1000))
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReceiptInspectionPolicy(Base):
    __tablename__ = "mat_receipt_inspection_policy"
    __table_args__ = (UniqueConstraint("lot_id", "revision", name="uq_receipt_policy_revision"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("mat_receipt_lot.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    engineering_defined: Mapped[bool] = mapped_column(Boolean)
    responsible_area_id: Mapped[UUID | None] = mapped_column(ForeignKey("core_area.id", ondelete="RESTRICT"))
    criteria: Mapped[list[str]] = mapped_column(JSONB)
    configured_by: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    configured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReceiptReleaseEvidence(Base):
    __tablename__ = "mat_receipt_release_evidence"

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("mat_receipt_decision.id", ondelete="RESTRICT"), primary_key=True)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("mat_receipt_inspection_policy.id", ondelete="RESTRICT"))
    key_id: Mapped[UUID] = mapped_column(ForeignKey("mat_receipt_signer_key.id", ondelete="RESTRICT"))
    document: Mapped[bytes] = mapped_column(LargeBinary)
    document_sha256: Mapped[str] = mapped_column(String(64))
    signature: Mapped[bytes] = mapped_column(LargeBinary)
    signed_payload: Mapped[bytes] = mapped_column(LargeBinary)
