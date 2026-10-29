"""Immutable Prolowin staging, data-quality and reconciliation models."""

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
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from mop.persistence.base import Base


class ImportBatch(Base):
    __tablename__ = "int_import_batch"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_sha256",
            "parser_version",
            name="uq_int_import_batch_identity",
        ),
        CheckConstraint(
            "source_type IN "
            "('COMPLETE_ARTICLE_STRUCTURE', 'DIRECT_ARTICLE_STRUCTURE')",
            name="ck_int_import_batch_source_type",
        ),
        CheckConstraint(
            "status IN "
            "('RECEIVED', 'PARSED', 'VALIDATED', 'REJECTED', "
            "'APPLIED', 'RECONCILED')",
            name="ck_int_import_batch_status",
        ),
        CheckConstraint(
            "accepted_rows >= 0 AND rejected_rows >= 0",
            name="ck_int_import_batch_row_counts_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    exported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(80), nullable=False)
    imported_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="RECEIVED"
    )
    accepted_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rejected_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )


class ProlowinStructureRow(Base):
    __tablename__ = "int_prolowin_structure_row"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "source_row_no",
            name="uq_int_prolowin_structure_row_no",
        ),
        UniqueConstraint(
            "batch_id",
            "row_hash",
            name="uq_int_prolowin_structure_row_hash",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_int_prolowin_structure_quantity_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_import_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    root_article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    operation_code: Mapped[str] = mapped_column(String(30), nullable=False)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    uom_raw: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ProlowinCompleteSnapshot(Base):
    __tablename__ = "int_prolowin_complete_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            name="uq_int_prolowin_complete_snapshot_batch",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_import_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    root_article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    root_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    root_uom_raw: Mapped[str] = mapped_column(String(80), nullable=False)
    report_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )


class ProlowinFlatRequirement(Base):
    __tablename__ = "int_prolowin_flat_requirement"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "article_code",
            name="uq_int_prolowin_flat_requirement_article",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_int_prolowin_flat_quantity_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_prolowin_complete_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    uom_raw: Mapped[str] = mapped_column(String(80), nullable=False)
    source_fin_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_prolowin_structure_row.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_root: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class SourceOperationState(Base):
    __tablename__ = "int_source_operation_state"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "source_row_id",
            name="uq_int_source_operation_state_row",
        ),
        CheckConstraint(
            "quantity >= 0",
            name="ck_int_source_operation_quantity_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_prolowin_complete_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    source_operation_code: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    uom_raw: Mapped[str] = mapped_column(String(80), nullable=False)
    source_row_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_prolowin_structure_row.id", ondelete="RESTRICT"),
        nullable=False,
    )


class ProlowinDirectRelation(Base):
    __tablename__ = "int_prolowin_direct_relation"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "source_row_no",
            name="uq_int_prolowin_direct_relation_row_no",
        ),
        UniqueConstraint(
            "batch_id",
            "row_hash",
            name="uq_int_prolowin_direct_relation_row_hash",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_int_prolowin_direct_relation_quantity_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_import_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    root_article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    source_row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_article_code: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    parent_description_raw: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    child_article_code: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    child_description_raw: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    uom_raw: Mapped[str] = mapped_column(String(80), nullable=False)
    source_relation_key: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class DataQualityIssue(Base):
    __tablename__ = "dq_issue"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'ERROR', 'BLOCKER')",
            name="ck_dq_issue_severity",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'ACCEPTED', 'RESOLVED', 'WAIVED')",
            name="ck_dq_issue_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_import_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN"
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("iam_user.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReconciliationRun(Base):
    __tablename__ = "int_reconciliation_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('MATCH', 'MATCH_WITH_WARNINGS', 'MISMATCH', 'BLOCKED')",
            name="ck_int_reconciliation_run_status",
        ),
        CheckConstraint(
            "compared_items >= 0 AND matching_items >= 0 "
            "AND mismatching_items >= 0",
            name="ck_int_reconciliation_run_counts_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_import_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    root_article_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_article_revision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bom_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("md_bom_revision.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    tolerance: Mapped[Decimal] = mapped_column(
        Numeric(24, 12), nullable=False, default=Decimal("0")
    )
    compared_items: Mapped[int] = mapped_column(Integer, nullable=False)
    matching_items: Mapped[int] = mapped_column(Integer, nullable=False)
    mismatching_items: Mapped[int] = mapped_column(Integer, nullable=False)


class ReconciliationItem(Base):
    __tablename__ = "int_reconciliation_item"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_run_id",
            "article_code",
            "comparison_uom",
            name="uq_int_reconciliation_item_key",
        ),
        CheckConstraint(
            "result IN ('MATCH', 'MISMATCH', 'SOURCE_ONLY', 'CALCULATED_ONLY')",
            name="ck_int_reconciliation_item_result",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reconciliation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("int_reconciliation_run.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    article_code: Mapped[str] = mapped_column(String(80), nullable=False)
    source_fin_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 12), nullable=True
    )
    source_uom_raw: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    calculated_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 12), nullable=True
    )
    calculated_uom_raw: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    comparison_uom: Mapped[str] = mapped_column(String(120), nullable=False)
    variance: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 12), nullable=True
    )
    result: Mapped[str] = mapped_column(String(30), nullable=False)
