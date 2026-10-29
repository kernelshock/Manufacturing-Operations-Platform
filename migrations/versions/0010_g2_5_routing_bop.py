"""G2.5 revisioned Routing/BOP and G1 resource assignments.

Revision ID: 0010_g2_5
Revises: 0009_g2_4
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_g2_5"
down_revision = "0009_g2_4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "md_routing_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_revision_id", sa.Uuid(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_batch_id", sa.Uuid(), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_no > 0",
            name="ck_md_routing_revision_no_positive",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_routing_revision_status",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_md_routing_revision_effectivity",
        ),
        sa.ForeignKeyConstraint(
            ["article_revision_id"],
            ["md_article_revision.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_revision_id",
            "revision_no",
            name="uq_md_routing_revision_article_revision_no",
        ),
        sa.UniqueConstraint(
            "article_revision_id",
            "source_fingerprint",
            name="uq_md_routing_revision_article_fingerprint",
        ),
    )
    op.create_index(
        "ix_md_routing_revision_article_revision_id",
        "md_routing_revision",
        ["article_revision_id"],
    )

    op.create_table(
        "md_routing_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("routing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("source_operation_code", sa.String(length=30), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("work_center_id", sa.Uuid(), nullable=True),
        sa.Column("operation_kind", sa.String(length=30), nullable=False),
        sa.Column("schedulable", sa.Boolean(), nullable=False),
        sa.Column("completion_marker", sa.Boolean(), nullable=False),
        sa.Column(
            "nominal_rate",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column("rate_uom", sa.String(length=50), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence_no > 0",
            name="ck_md_routing_operation_sequence_positive",
        ),
        sa.CheckConstraint(
            "operation_kind IN "
            "('PHYSICAL_PRODUCTION', 'COSTING_ONLY', 'ADMINISTRATIVE', "
            "'COMPLETION_MARKER', 'UNKNOWN')",
            name="ck_md_routing_operation_kind",
        ),
        sa.CheckConstraint(
            "nominal_rate IS NULL OR nominal_rate > 0",
            name="ck_md_routing_operation_nominal_rate_positive",
        ),
        sa.CheckConstraint(
            "(nominal_rate IS NULL AND rate_uom IS NULL) OR "
            "(nominal_rate IS NOT NULL AND rate_uom IS NOT NULL)",
            name="ck_md_routing_operation_rate_pair",
        ),
        sa.CheckConstraint(
            "NOT completion_marker OR NOT schedulable",
            name="ck_md_routing_operation_completion_not_schedulable",
        ),
        sa.ForeignKeyConstraint(
            ["routing_revision_id"],
            ["md_routing_revision.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["core_area.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["work_center_id"],
            ["core_work_center.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "routing_revision_id",
            "sequence_no",
            name="uq_md_routing_operation_sequence",
        ),
    )
    op.create_index(
        "ix_md_routing_operation_routing_revision_id",
        "md_routing_operation",
        ["routing_revision_id"],
    )

    op.create_table(
        "md_resource_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("routing_operation_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("principal", sa.Boolean(), nullable=False),
        sa.Column(
            "capacity_factor",
            sa.Numeric(precision=12, scale=8),
            nullable=True,
        ),
        sa.Column("source_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "capacity_factor IS NULL OR capacity_factor > 0",
            name="ck_md_resource_assignment_capacity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["routing_operation_id"],
            ["md_routing_operation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["core_resource.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "routing_operation_id",
            "resource_id",
            name="uq_md_resource_assignment_operation_resource",
        ),
    )
    op.create_index(
        "ix_md_resource_assignment_routing_operation_id",
        "md_resource_assignment",
        ["routing_operation_id"],
    )
    op.create_index(
        "ix_md_resource_assignment_resource_id",
        "md_resource_assignment",
        ["resource_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_md_resource_assignment_resource_id",
        table_name="md_resource_assignment",
    )
    op.drop_index(
        "ix_md_resource_assignment_routing_operation_id",
        table_name="md_resource_assignment",
    )
    op.drop_table("md_resource_assignment")
    op.drop_index(
        "ix_md_routing_operation_routing_revision_id",
        table_name="md_routing_operation",
    )
    op.drop_table("md_routing_operation")
    op.drop_index(
        "ix_md_routing_revision_article_revision_id",
        table_name="md_routing_revision",
    )
    op.drop_table("md_routing_revision")
