"""G2.7 Prolowin immutable staging, DQ and reconciliation.

Revision ID: 0012_g2_7
Revises: 0011_g2_6
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_g2_7"
down_revision = "0011_g2_6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "int_import_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("mapping_version", sa.String(length=80), nullable=False),
        sa.Column("imported_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("accepted_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "source_type IN "
            "('COMPLETE_ARTICLE_STRUCTURE', 'DIRECT_ARTICLE_STRUCTURE')",
            name="ck_int_import_batch_source_type",
        ),
        sa.CheckConstraint(
            "status IN "
            "('RECEIVED', 'PARSED', 'VALIDATED', 'REJECTED', "
            "'APPLIED', 'RECONCILED')",
            name="ck_int_import_batch_status",
        ),
        sa.CheckConstraint(
            "accepted_rows >= 0 AND rejected_rows >= 0",
            name="ck_int_import_batch_row_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["imported_by"], ["iam_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "source_sha256",
            "parser_version",
            name="uq_int_import_batch_identity",
        ),
    )

    op.create_table(
        "int_prolowin_structure_row",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("root_article_code", sa.String(length=80), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_row_no", sa.Integer(), nullable=False),
        sa.Column("article_code", sa.String(length=80), nullable=False),
        sa.Column("operation_code", sa.String(length=30), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column(
            "quantity", sa.Numeric(precision=24, scale=8), nullable=False
        ),
        sa.Column("uom_raw", sa.String(length=80), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_int_prolowin_structure_quantity_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["int_import_batch.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "source_row_no",
            name="uq_int_prolowin_structure_row_no",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "row_hash",
            name="uq_int_prolowin_structure_row_hash",
        ),
    )
    op.create_index(
        "ix_int_prolowin_structure_row_batch_id",
        "int_prolowin_structure_row",
        ["batch_id"],
    )

    op.create_table(
        "int_prolowin_complete_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("root_article_code", sa.String(length=80), nullable=False),
        sa.Column(
            "root_quantity", sa.Numeric(precision=24, scale=8), nullable=False
        ),
        sa.Column("root_uom_raw", sa.String(length=80), nullable=False),
        sa.Column("report_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "normalized_fingerprint", sa.String(length=64), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["int_import_batch.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            name="uq_int_prolowin_complete_snapshot_batch",
        ),
    )
    op.create_index(
        "ix_int_prolowin_complete_snapshot_batch_id",
        "int_prolowin_complete_snapshot",
        ["batch_id"],
    )

    op.create_table(
        "int_prolowin_flat_requirement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("article_code", sa.String(length=80), nullable=False),
        sa.Column(
            "quantity", sa.Numeric(precision=24, scale=8), nullable=False
        ),
        sa.Column("uom_raw", sa.String(length=80), nullable=False),
        sa.Column("source_fin_row_id", sa.Uuid(), nullable=False),
        sa.Column("is_root", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_int_prolowin_flat_quantity_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["int_prolowin_complete_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_fin_row_id"],
            ["int_prolowin_structure_row.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "article_code",
            name="uq_int_prolowin_flat_requirement_article",
        ),
    )
    op.create_index(
        "ix_int_prolowin_flat_requirement_snapshot_id",
        "int_prolowin_flat_requirement",
        ["snapshot_id"],
    )

    op.create_table(
        "int_source_operation_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("article_code", sa.String(length=80), nullable=False),
        sa.Column(
            "source_operation_code", sa.String(length=30), nullable=False
        ),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column(
            "quantity", sa.Numeric(precision=24, scale=8), nullable=False
        ),
        sa.Column("uom_raw", sa.String(length=80), nullable=False),
        sa.Column("source_row_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_int_source_operation_quantity_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["int_prolowin_complete_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"],
            ["int_prolowin_structure_row.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "source_row_id",
            name="uq_int_source_operation_state_row",
        ),
    )
    op.create_index(
        "ix_int_source_operation_state_snapshot_id",
        "int_source_operation_state",
        ["snapshot_id"],
    )

    op.create_table(
        "int_prolowin_direct_relation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("root_article_code", sa.String(length=80), nullable=False),
        sa.Column("source_row_no", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column(
            "parent_article_code", sa.String(length=80), nullable=False
        ),
        sa.Column("parent_description_raw", sa.Text(), nullable=True),
        sa.Column(
            "child_article_code", sa.String(length=80), nullable=False
        ),
        sa.Column("child_description_raw", sa.Text(), nullable=True),
        sa.Column(
            "quantity", sa.Numeric(precision=24, scale=8), nullable=False
        ),
        sa.Column("uom_raw", sa.String(length=80), nullable=False),
        sa.Column(
            "source_relation_key", sa.String(length=200), nullable=False
        ),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_int_prolowin_direct_relation_quantity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["int_import_batch.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "source_row_no",
            name="uq_int_prolowin_direct_relation_row_no",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "row_hash",
            name="uq_int_prolowin_direct_relation_row_hash",
        ),
    )
    op.create_index(
        "ix_int_prolowin_direct_relation_batch_id",
        "int_prolowin_direct_relation",
        ["batch_id"],
    )

    op.create_table(
        "dq_issue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_key", sa.String(length=200), nullable=False),
        sa.Column("rule_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_row_id", sa.Uuid(), nullable=True),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'ERROR', 'BLOCKER')",
            name="ck_dq_issue_severity",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACCEPTED', 'RESOLVED', 'WAIVED')",
            name="ck_dq_issue_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["int_import_batch.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["iam_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dq_issue_batch_id", "dq_issue", ["batch_id"])

    op.create_table(
        "int_reconciliation_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("root_article_revision_id", sa.Uuid(), nullable=False),
        sa.Column("bom_revision_id", sa.Uuid(), nullable=False),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "tolerance", sa.Numeric(precision=24, scale=12), nullable=False
        ),
        sa.Column("compared_items", sa.Integer(), nullable=False),
        sa.Column("matching_items", sa.Integer(), nullable=False),
        sa.Column("mismatching_items", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('MATCH', 'MATCH_WITH_WARNINGS', 'MISMATCH', 'BLOCKED')",
            name="ck_int_reconciliation_run_status",
        ),
        sa.CheckConstraint(
            "compared_items >= 0 AND matching_items >= 0 "
            "AND mismatching_items >= 0",
            name="ck_int_reconciliation_run_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["int_import_batch.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["root_article_revision_id"],
            ["md_article_revision.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bom_revision_id"],
            ["md_bom_revision.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_int_reconciliation_run_batch_id",
        "int_reconciliation_run",
        ["batch_id"],
    )
    op.create_index(
        "ix_int_reconciliation_run_bom_revision_id",
        "int_reconciliation_run",
        ["bom_revision_id"],
    )

    op.create_table(
        "int_reconciliation_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Uuid(), nullable=False),
        sa.Column("article_code", sa.String(length=80), nullable=False),
        sa.Column(
            "source_fin_quantity",
            sa.Numeric(precision=24, scale=12),
            nullable=True,
        ),
        sa.Column("source_uom_raw", sa.String(length=80), nullable=True),
        sa.Column(
            "calculated_quantity",
            sa.Numeric(precision=24, scale=12),
            nullable=True,
        ),
        sa.Column(
            "calculated_uom_raw", sa.String(length=80), nullable=True
        ),
        sa.Column("comparison_uom", sa.String(length=120), nullable=False),
        sa.Column(
            "variance", sa.Numeric(precision=24, scale=12), nullable=True
        ),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.CheckConstraint(
            "result IN ('MATCH', 'MISMATCH', 'SOURCE_ONLY', 'CALCULATED_ONLY')",
            name="ck_int_reconciliation_item_result",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"],
            ["int_reconciliation_run.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_run_id",
            "article_code",
            "comparison_uom",
            name="uq_int_reconciliation_item_key",
        ),
    )
    op.create_index(
        "ix_int_reconciliation_item_reconciliation_run_id",
        "int_reconciliation_item",
        ["reconciliation_run_id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION mop_prolowin_reject_staging_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'Prolowin staging rows are immutable';
        END;
        $$;
        """
    )
    for table in (
        "int_prolowin_structure_row",
        "int_prolowin_direct_relation",
    ):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION mop_prolowin_reject_staging_mutation();
            """
        )


def downgrade() -> None:
    for table in (
        "int_prolowin_direct_relation",
        "int_prolowin_structure_row",
    ):
        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};"
        )
    op.execute(
        "DROP FUNCTION IF EXISTS mop_prolowin_reject_staging_mutation();"
    )

    op.drop_index(
        "ix_int_reconciliation_item_reconciliation_run_id",
        table_name="int_reconciliation_item",
    )
    op.drop_table("int_reconciliation_item")
    op.drop_index(
        "ix_int_reconciliation_run_bom_revision_id",
        table_name="int_reconciliation_run",
    )
    op.drop_index(
        "ix_int_reconciliation_run_batch_id",
        table_name="int_reconciliation_run",
    )
    op.drop_table("int_reconciliation_run")
    op.drop_index("ix_dq_issue_batch_id", table_name="dq_issue")
    op.drop_table("dq_issue")
    op.drop_index(
        "ix_int_prolowin_direct_relation_batch_id",
        table_name="int_prolowin_direct_relation",
    )
    op.drop_table("int_prolowin_direct_relation")
    op.drop_index(
        "ix_int_source_operation_state_snapshot_id",
        table_name="int_source_operation_state",
    )
    op.drop_table("int_source_operation_state")
    op.drop_index(
        "ix_int_prolowin_flat_requirement_snapshot_id",
        table_name="int_prolowin_flat_requirement",
    )
    op.drop_table("int_prolowin_flat_requirement")
    op.drop_index(
        "ix_int_prolowin_complete_snapshot_batch_id",
        table_name="int_prolowin_complete_snapshot",
    )
    op.drop_table("int_prolowin_complete_snapshot")
    op.drop_index(
        "ix_int_prolowin_structure_row_batch_id",
        table_name="int_prolowin_structure_row",
    )
    op.drop_table("int_prolowin_structure_row")
    op.drop_table("int_import_batch")
