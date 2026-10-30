"""Operational demand persistence models for G3."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
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
        CheckConstraint(
            "vehicle_topology IN ('SIMPLE', 'DOUBLE_DECK')",
            name="ck_demand_taquilla_vehicle_topology",
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
    vehicle_topology: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SIMPLE"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    plan: Mapped[ProductionPlan] = relationship(back_populates="taquillas")
    product_lines: Mapped[list["TaquillaProductLine"]] = relationship(
        back_populates="taquilla", cascade="all, delete-orphan"
    )


class TaquillaProductLine(Base):
    __tablename__ = "demand_taquilla_product_line"
    __table_args__ = (
        UniqueConstraint(
            "taquilla_id",
            "sequence_no",
            name="uq_demand_taquilla_product_line_sequence",
        ),
        UniqueConstraint(
            "taquilla_id",
            "source_line_key",
            name="uq_demand_taquilla_product_line_source_key",
        ),
        CheckConstraint(
            "sequence_no > 0",
            name="ck_demand_taquilla_product_line_sequence_positive",
        ),
        CheckConstraint(
            "requested_quantity > 0",
            name="ck_demand_taquilla_product_line_quantity_positive",
        ),
        CheckConstraint(
            "deck_position IN ('SINGLE', 'UPPER', 'LOWER')",
            name="ck_demand_taquilla_product_line_deck_position",
        ),
        CheckConstraint(
            "routing_binding_mode IS NULL OR routing_binding_mode IN ('RESOLVED', 'OVERRIDE')",
            name="ck_demand_taquilla_product_line_routing_binding_mode",
        ),
        CheckConstraint(
            "(routing_revision_id IS NULL AND routing_binding_mode IS NULL "
            "AND routing_effective_at IS NULL AND routing_override_reason IS NULL "
            "AND routing_bound_at IS NULL AND routing_bound_by IS NULL) OR "
            "(routing_revision_id IS NOT NULL AND routing_binding_mode IS NOT NULL "
            "AND routing_effective_at IS NOT NULL AND routing_bound_at IS NOT NULL "
            "AND routing_bound_by IS NOT NULL)",
            name="ck_demand_taquilla_product_line_routing_binding_complete",
        ),
        CheckConstraint(
            "(routing_binding_mode = 'OVERRIDE' AND routing_override_reason IS NOT NULL) OR "
            "(routing_binding_mode IS DISTINCT FROM 'OVERRIDE' AND routing_override_reason IS NULL)",
            name="ck_demand_taquilla_product_line_routing_override_reason",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    taquilla_id: Mapped[UUID] = mapped_column(
        ForeignKey("demand_taquilla.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    source_line_key: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    deck_position: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SINGLE"
    )
    source_document_key: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    routing_revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_routing_revision.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    routing_binding_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    routing_effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    routing_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_bound_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    routing_bound_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    taquilla: Mapped[Taquilla] = relationship(back_populates="product_lines")
