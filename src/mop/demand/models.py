"""Operational demand persistence models for G3."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mop.persistence.base import Base


class ProductionPlan(Base):
    __tablename__ = "demand_production_plan"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'OPEN', 'COMPLETED', 'CANCELLED')",
            name="ck_demand_production_plan_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_number: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    taquillas: Mapped[list["Taquilla"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Taquilla(Base):
    __tablename__ = "demand_taquilla"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "sequence_no", name="uq_demand_taquilla_plan_sequence"
        ),
        CheckConstraint(
            "sequence_no > 0",
            name="ck_demand_taquilla_sequence_positive",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'READY', 'COMPLETED', 'CANCELLED')",
            name="ck_demand_taquilla_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("demand_production_plan.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    taquilla_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    plan: Mapped[ProductionPlan] = relationship(back_populates="taquillas")
