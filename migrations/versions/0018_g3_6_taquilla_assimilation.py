"""G3.6 Taquilla assimilation staging.

Revision ID: 0018_g3_6
Revises: 0017_g3_5
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_g3_6"
down_revision = "0017_g3_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demand_taquilla_assimilation_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("target_taquilla_id", sa.Uuid(), nullable=True),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("mapping_version", sa.String(length=80), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("taquilla_code", sa.String(length=80), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("vehicle_topology", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("accepted_lines", sa.Integer(), nullable=False),
        sa.Column("rejected_lines", sa.Integer(), nullable=False),
        sa.Column("imported_by", sa.Uuid(), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'VALIDATED', 'REVIEW_REQUIRED', 'REJECTED', 'APPLIED')",
            name="ck_demand_taquilla_assimilation_status",
        ),
        sa.CheckConstraint(
            "vehicle_topology IN ('SIMPLE', 'DOUBLE_DECK')",
            name="ck_demand_taquilla_assimilation_topology",
        ),
        sa.CheckConstraint(
            "accepted_lines >= 0 AND rejected_lines >= 0",
            name="ck_demand_taquilla_assimilation_counts",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["demand_production_plan.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_taquilla_id"],
            ["demand_taquilla.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["imported_by"],
            ["iam_user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "payload_fingerprint",
            "parser_version",
            name="uq_demand_taquilla_assimilation_identity",
        ),
    )
    op.create_index(
        "ix_demand_taquilla_assimilation_batch_plan_id",
        "demand_taquilla_assimilation_batch",
        ["plan_id"],
    )
    op.create_index(
        "ix_demand_taquilla_assimilation_batch_target_taquilla_id",
        "demand_taquilla_assimilation_batch",
        ["target_taquilla_id"],
    )

    op.create_table(
        "demand_taquilla_assimilation_document",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_key", sa.String(length=200), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["demand_taquilla_assimilation_batch.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "source_document_key",
            name="uq_demand_taquilla_assimilation_document_key",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "source_sha256",
            name="uq_demand_taquilla_assimilation_document_sha",
        ),
    )
    op.create_index(
        "ix_demand_taquilla_assimilation_document_batch_id",
        "demand_taquilla_assimilation_document",
        ["batch_id"],
    )

    op.create_table(
        "demand_taquilla_assimilation_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_line_key", sa.String(length=200), nullable=False),
        sa.Column("source_article_system", sa.String(length=40), nullable=False),
        sa.Column("source_article_code", sa.String(length=80), nullable=False),
        sa.Column("resolved_article_id", sa.Uuid(), nullable=True),
        sa.Column(
            "requested_quantity",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column("deck_position", sa.String(length=20), nullable=False),
        sa.Column("target_product_line_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "requested_quantity > 0",
            name="ck_demand_taquilla_assimilation_line_quantity",
        ),
        sa.CheckConstraint(
            "deck_position IN ('SINGLE', 'UPPER', 'LOWER')",
            name="ck_demand_taquilla_assimilation_line_deck",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["demand_taquilla_assimilation_batch.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["demand_taquilla_assimilation_document.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_article_id"],
            ["md_article.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_product_line_id"],
            ["demand_taquilla_product_line.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "source_line_key",
            name="uq_demand_taquilla_assimilation_line_key",
        ),
    )
    op.create_index(
        "ix_demand_taquilla_assimilation_line_batch_id",
        "demand_taquilla_assimilation_line",
        ["batch_id"],
    )
    op.create_index(
        "ix_demand_taquilla_assimilation_line_document_id",
        "demand_taquilla_assimilation_line",
        ["document_id"],
    )

    op.create_table(
        "demand_taquilla_assimilation_issue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_document_key", sa.String(length=200), nullable=True),
        sa.Column("source_line_key", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('WARNING', 'ERROR', 'BLOCKER')",
            name="ck_demand_taquilla_assimilation_issue_severity",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["demand_taquilla_assimilation_batch.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_demand_taquilla_assimilation_issue_batch_id",
        "demand_taquilla_assimilation_issue",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_demand_taquilla_assimilation_issue_batch_id",
        table_name="demand_taquilla_assimilation_issue",
    )
    op.drop_table("demand_taquilla_assimilation_issue")

    op.drop_index(
        "ix_demand_taquilla_assimilation_line_document_id",
        table_name="demand_taquilla_assimilation_line",
    )
    op.drop_index(
        "ix_demand_taquilla_assimilation_line_batch_id",
        table_name="demand_taquilla_assimilation_line",
    )
    op.drop_table("demand_taquilla_assimilation_line")

    op.drop_index(
        "ix_demand_taquilla_assimilation_document_batch_id",
        table_name="demand_taquilla_assimilation_document",
    )
    op.drop_table("demand_taquilla_assimilation_document")

    op.drop_index(
        "ix_demand_taquilla_assimilation_batch_target_taquilla_id",
        table_name="demand_taquilla_assimilation_batch",
    )
    op.drop_index(
        "ix_demand_taquilla_assimilation_batch_plan_id",
        table_name="demand_taquilla_assimilation_batch",
    )
    op.drop_table("demand_taquilla_assimilation_batch")
