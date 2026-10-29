"""G2.3 supplier master.

Revision ID: 0008_g2_3
Revises: 0007_g2_2
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_g2_3"
down_revision = "0007_g2_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "md_supplier",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("supply_category", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "supply_category IN ('UNKNOWN', 'PRODUCT', 'PROCESS', 'SERVICE', 'MIXED')",
            name="ck_md_supplier_supply_category",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_md_supplier_code"),
    )

    op.create_table(
        "md_supplier_source_mapping",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("external_system", sa.String(length=40), nullable=False),
        sa.Column("external_code", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_category_raw", sa.String(length=255), nullable=True),
        sa.Column("mapping_status", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mapping_status IN ('MAPPED', 'REVIEW_REQUIRED', 'REJECTED')",
            name="ck_md_supplier_source_mapping_status",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["md_supplier.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["iam_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_system",
            "external_code",
            name="uq_md_supplier_source_mapping_system_code",
        ),
    )
    op.create_index(
        "ix_md_supplier_source_mapping_supplier_id",
        "md_supplier_source_mapping",
        ["supplier_id"],
    )

    op.create_table(
        "md_supplier_article",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_article_code", sa.String(length=120), nullable=True),
        sa.Column("preferred", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column(
            "minimum_order_quantity",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column("order_uom_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="ck_md_supplier_article_lead_time_nonnegative",
        ),
        sa.CheckConstraint(
            "minimum_order_quantity IS NULL OR minimum_order_quantity > 0",
            name="ck_md_supplier_article_moq_positive",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["md_supplier.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["md_article.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_uom_id"], ["md_uom.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id", "article_id", name="uq_md_supplier_article_pair"
        ),
    )
    op.create_index(
        "ix_md_supplier_article_supplier_id",
        "md_supplier_article",
        ["supplier_id"],
    )
    op.create_index(
        "ix_md_supplier_article_article_id",
        "md_supplier_article",
        ["article_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_md_supplier_article_article_id", table_name="md_supplier_article"
    )
    op.drop_index(
        "ix_md_supplier_article_supplier_id", table_name="md_supplier_article"
    )
    op.drop_table("md_supplier_article")
    op.drop_index(
        "ix_md_supplier_source_mapping_supplier_id",
        table_name="md_supplier_source_mapping",
    )
    op.drop_table("md_supplier_source_mapping")
    op.drop_table("md_supplier")
