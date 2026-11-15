"""PostgreSQL storage for G7.6 exception snapshots and decision events."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class GovernanceCaseRecord(Base):
    """An immutable snapshot of the evidence used to open an exception."""

    __tablename__ = "planning_governance_case"
    __table_args__ = (
        Index("ix_planning_governance_case_plant_created", "plant_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    plant_id: Mapped[UUID] = mapped_column(ForeignKey("core_plant.id", ondelete="RESTRICT"))
    article_id: Mapped[UUID] = mapped_column(ForeignKey("md_article.id", ondelete="RESTRICT"))
    uom_id: Mapped[UUID] = mapped_column(ForeignKey("md_uom.id", ondelete="RESTRICT"))
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict] = mapped_column(JSONB)


class GovernanceEventRecord(Base):
    """An ordered event with its audited identity and retry information."""

    __tablename__ = "planning_governance_event"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_planning_governance_event_revision"),
        CheckConstraint(
            "kind IN ('SUBMIT', 'ACKNOWLEDGE', 'APPROVE', 'REJECT', 'CLOSE')",
            name="ck_planning_governance_event_kind",
        ),
        CheckConstraint(
            "actor_role IN ('PLANNER', 'PURCHASING', 'QUALITY', 'PRODUCTION_MANAGER', 'DIRECTOR')",
            name="ck_planning_governance_event_actor_role",
        ),
        UniqueConstraint("case_id", "revision", name="uq_planning_governance_event_revision"),
        UniqueConstraint("actor_id", "idempotency_key", name="uq_planning_governance_event_retry"),
        UniqueConstraint("audit_entry_id", name="uq_planning_governance_event_audit"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_governance_case.id", ondelete="RESTRICT")
    )
    revision: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("iam_user.id", ondelete="RESTRICT"))
    actor_role: Mapped[str] = mapped_column(String(24))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(64))
    audit_entry_id: Mapped[UUID] = mapped_column(ForeignKey("audit_event.id", ondelete="RESTRICT"))
