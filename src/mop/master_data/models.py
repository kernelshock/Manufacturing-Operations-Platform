"""Canonical Master Data persistence models for G2."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mop.persistence.base import Base


class UnitOfMeasure(Base):
    __tablename__ = "md_uom"
    __table_args__ = (
        CheckConstraint(
            "dimension IN ('COUNT', 'LENGTH', 'MASS', 'VOLUME', 'OTHER')",
            name="ck_md_uom_dimension",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    aliases: Mapped[list["UnitOfMeasureAlias"]] = relationship(back_populates="uom")
    articles: Mapped[list["Article"]] = relationship(back_populates="default_uom")
    product_configuration_widths: Mapped[list["ProductConfiguration"]] = relationship(
        back_populates="width_uom"
    )


class UnitOfMeasureAlias(Base):
    __tablename__ = "md_uom_alias"
    __table_args__ = (
        UniqueConstraint("source_system", "raw_value", name="uq_md_uom_alias_source_raw"),
        CheckConstraint(
            "mapping_status IN ('MAPPED', 'UNMAPPED', 'REVIEW_REQUIRED')",
            name="ck_md_uom_alias_mapping_status",
        ),
        CheckConstraint(
            "conversion_factor IS NULL OR conversion_factor > 0",
            name="ck_md_uom_alias_conversion_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(80), nullable=False)
    uom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=True
    )
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    conversion_factor: Mapped[Decimal | None] = mapped_column(Numeric(24, 12), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )

    uom: Mapped[UnitOfMeasure | None] = relationship(back_populates="aliases")


class Article(Base):
    __tablename__ = "md_article"
    __table_args__ = (
        UniqueConstraint(
            "external_system", "external_code", name="uq_md_article_source_code"
        ),
        CheckConstraint(
            "article_kind IN ('UNKNOWN', 'PURCHASED', 'MANUFACTURED', "
            "'FINISHED_PRODUCT', 'CONSUMABLE', 'SERVICE')",
            name="ck_md_article_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_system: Mapped[str] = mapped_column(String(40), nullable=False)
    external_code: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_description: Mapped[str] = mapped_column(Text, nullable=False)
    article_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    default_uom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    default_uom: Mapped[UnitOfMeasure | None] = relationship(back_populates="articles")
    revisions: Mapped[list["ArticleRevision"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    product_configuration: Mapped["ProductConfiguration | None"] = relationship(
        back_populates="article", uselist=False
    )


class ArticleRevision(Base):
    __tablename__ = "md_article_revision"
    __table_args__ = (
        UniqueConstraint(
            "article_id", "source_fingerprint", name="uq_md_article_revision_fingerprint"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_article_revision_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    revision_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    source_batch_id: Mapped[UUID | None] = mapped_column(nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )

    article: Mapped[Article] = relationship(back_populates="revisions")


class ProductConfiguration(Base):
    __tablename__ = "md_product_configuration"
    __table_args__ = (
        UniqueConstraint("article_id", name="uq_md_product_configuration_article"),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="ck_md_product_configuration_width_positive",
        ),
        CheckConstraint(
            "(width IS NULL AND width_uom_id IS NULL) OR "
            "(width IS NOT NULL AND width_uom_id IS NOT NULL)",
            name="ck_md_product_configuration_width_pair",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    family_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    family_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_class: Mapped[str] = mapped_column("class", String(64), nullable=False)
    width: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    width_uom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=True
    )
    configuration_string: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    article: Mapped[Article] = relationship(back_populates="product_configuration")
    width_uom: Mapped[UnitOfMeasure | None] = relationship(
        back_populates="product_configuration_widths"
    )
