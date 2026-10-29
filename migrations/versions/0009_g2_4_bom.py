"""G2.4 revisioned BOM and recursive component relations.

Revision ID: 0009_g2_4
Revises: 0008_g2_3
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_g2_4"
down_revision = "0008_g2_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "md_bom_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_article_revision_id", sa.Uuid(), nullable=False),
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
            name="ck_md_bom_revision_no_positive",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_bom_revision_status",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_md_bom_revision_effectivity",
        ),
        sa.ForeignKeyConstraint(
            ["parent_article_revision_id"],
            ["md_article_revision.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_article_revision_id",
            "revision_no",
            name="uq_md_bom_revision_parent_revision_no",
        ),
        sa.UniqueConstraint(
            "parent_article_revision_id",
            "source_fingerprint",
            name="uq_md_bom_revision_parent_fingerprint",
        ),
    )
    op.create_index(
        "ix_md_bom_revision_parent_article_revision_id",
        "md_bom_revision",
        ["parent_article_revision_id"],
    )

    op.create_table(
        "md_bom_component",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bom_revision_id", sa.Uuid(), nullable=False),
        sa.Column("child_article_id", sa.Uuid(), nullable=False),
        sa.Column("child_revision_id", sa.Uuid(), nullable=True),
        sa.Column(
            "quantity",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column("source_uom_raw", sa.String(length=80), nullable=False),
        sa.Column("uom_id", sa.Uuid(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("source_relation_key", sa.String(length=200), nullable=True),
        sa.Column(
            "scrap_factor",
            sa.Numeric(precision=12, scale=8),
            nullable=True,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_md_bom_component_quantity_positive",
        ),
        sa.CheckConstraint(
            "scrap_factor IS NULL OR scrap_factor >= 0",
            name="ck_md_bom_component_scrap_nonnegative",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name="ck_md_bom_component_effectivity",
        ),
        sa.ForeignKeyConstraint(
            ["bom_revision_id"], ["md_bom_revision.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["child_article_id"], ["md_article.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["child_revision_id"], ["md_article_revision.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["uom_id"], ["md_uom.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bom_revision_id",
            "source_relation_key",
            name="uq_md_bom_component_relation_key",
        ),
    )
    op.create_index(
        "ix_md_bom_component_bom_revision_id",
        "md_bom_component",
        ["bom_revision_id"],
    )
    op.create_index(
        "ix_md_bom_component_child_article_id",
        "md_bom_component",
        ["child_article_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_md_bom_component_child_article_id",
        table_name="md_bom_component",
    )
    op.drop_index(
        "ix_md_bom_component_bom_revision_id",
        table_name="md_bom_component",
    )
    op.drop_table("md_bom_component")
    op.drop_index(
        "ix_md_bom_revision_parent_article_revision_id",
        table_name="md_bom_revision",
    )
    op.drop_table("md_bom_revision")
