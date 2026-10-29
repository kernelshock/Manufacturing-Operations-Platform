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
    Integer,
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


class Supplier(Base):
    __tablename__ = "md_supplier"
    __table_args__ = (
        CheckConstraint(
            "supply_category IN ('UNKNOWN', 'PRODUCT', 'PROCESS', 'SERVICE', 'MIXED')",
            name="ck_md_supplier_supply_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supply_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UNKNOWN"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SupplierSourceMapping(Base):
    __tablename__ = "md_supplier_source_mapping"
    __table_args__ = (
        UniqueConstraint(
            "external_system",
            "external_code",
            name="uq_md_supplier_source_mapping_system_code",
        ),
        CheckConstraint(
            "mapping_status IN ('MAPPED', 'REVIEW_REQUIRED', 'REJECTED')",
            name="ck_md_supplier_source_mapping_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    supplier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_supplier.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    external_system: Mapped[str] = mapped_column(String(40), nullable=False)
    external_code: Mapped[str] = mapped_column(String(80), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_category_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SupplierArticle(Base):
    __tablename__ = "md_supplier_article"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "article_id", name="uq_md_supplier_article_pair"
        ),
        CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="ck_md_supplier_article_lead_time_nonnegative",
        ),
        CheckConstraint(
            "minimum_order_quantity IS NULL OR minimum_order_quantity > 0",
            name="ck_md_supplier_article_moq_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_supplier.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_article_code: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_order_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 8), nullable=True
    )
    order_uom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class BOMRevision(Base):
    __tablename__ = "md_bom_revision"
    __table_args__ = (
        UniqueConstraint(
            "parent_article_revision_id",
            "revision_no",
            name="uq_md_bom_revision_parent_revision_no",
        ),
        UniqueConstraint(
            "parent_article_revision_id",
            "source_fingerprint",
            name="uq_md_bom_revision_parent_fingerprint",
        ),
        CheckConstraint("revision_no > 0", name="ck_md_bom_revision_no_positive"),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_bom_revision_status",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_md_bom_revision_effectivity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parent_article_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article_revision.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_batch_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BOMComponent(Base):
    __tablename__ = "md_bom_component"
    __table_args__ = (
        UniqueConstraint(
            "bom_revision_id",
            "source_relation_key",
            name="uq_md_bom_component_relation_key",
        ),
        CheckConstraint("quantity > 0", name="ck_md_bom_component_quantity_positive"),
        CheckConstraint(
            "scrap_factor IS NULL OR scrap_factor >= 0",
            name="ck_md_bom_component_scrap_nonnegative",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name="ck_md_bom_component_effectivity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    bom_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_bom_revision.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    child_article_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    child_revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_article_revision.id", ondelete="RESTRICT"), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    source_uom_raw: Mapped[str] = mapped_column(String(80), nullable=False)
    uom_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=True
    )
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_relation_key: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    scrap_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8), nullable=True
    )
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class RoutingRevision(Base):
    __tablename__ = "md_routing_revision"
    __table_args__ = (
        UniqueConstraint(
            "article_revision_id",
            "revision_no",
            name="uq_md_routing_revision_article_revision_no",
        ),
        UniqueConstraint(
            "article_revision_id",
            "source_fingerprint",
            name="uq_md_routing_revision_article_fingerprint",
        ),
        CheckConstraint(
            "revision_no > 0",
            name="ck_md_routing_revision_no_positive",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_routing_revision_status",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_md_routing_revision_effectivity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article_revision.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT"
    )
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_batch_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RoutingOperation(Base):
    __tablename__ = "md_routing_operation"
    __table_args__ = (
        UniqueConstraint(
            "routing_revision_id",
            "sequence_no",
            name="uq_md_routing_operation_sequence",
        ),
        CheckConstraint(
            "sequence_no > 0",
            name="ck_md_routing_operation_sequence_positive",
        ),
        CheckConstraint(
            "operation_kind IN "
            "('PHYSICAL_PRODUCTION', 'COSTING_ONLY', 'ADMINISTRATIVE', "
            "'COMPLETION_MARKER', 'UNKNOWN')",
            name="ck_md_routing_operation_kind",
        ),
        CheckConstraint(
            "nominal_rate IS NULL OR nominal_rate > 0",
            name="ck_md_routing_operation_nominal_rate_positive",
        ),
        CheckConstraint(
            "(nominal_rate IS NULL AND rate_uom IS NULL) OR "
            "(nominal_rate IS NOT NULL AND rate_uom IS NOT NULL)",
            name="ck_md_routing_operation_rate_pair",
        ),
        CheckConstraint(
            "NOT completion_marker OR NOT schedulable",
            name="ck_md_routing_operation_completion_not_schedulable",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    routing_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_routing_revision.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_operation_code: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    area_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core_area.id", ondelete="RESTRICT"), nullable=True
    )
    work_center_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core_work_center.id", ondelete="RESTRICT"), nullable=True
    )
    operation_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    schedulable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    completion_marker: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    nominal_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 8), nullable=True
    )
    rate_uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResourceAssignment(Base):
    __tablename__ = "md_resource_assignment"
    __table_args__ = (
        UniqueConstraint(
            "routing_operation_id",
            "resource_id",
            name="uq_md_resource_assignment_operation_resource",
        ),
        CheckConstraint(
            "capacity_factor IS NULL OR capacity_factor > 0",
            name="ck_md_resource_assignment_capacity_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    routing_operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_routing_operation.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_resource.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    capacity_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8), nullable=True
    )
    source_batch_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
