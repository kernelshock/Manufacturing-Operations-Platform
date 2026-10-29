"""G2.2 product configurations.

Revision ID: 0007_g2_2
Revises: 0006_g2_1
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_g2_2"
down_revision = "0006_g2_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "md_product_configuration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("family_code", sa.String(length=64), nullable=False),
        sa.Column("family_name", sa.String(length=255), nullable=False),
        sa.Column("model_code", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("class", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("width_uom_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_string", sa.Text(), nullable=False),
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
            "width IS NULL OR width > 0",
            name="ck_md_product_configuration_width_positive",
        ),
        sa.CheckConstraint(
            "(width IS NULL AND width_uom_id IS NULL) OR "
            "(width IS NOT NULL AND width_uom_id IS NOT NULL)",
            name="ck_md_product_configuration_width_pair",
        ),
        sa.ForeignKeyConstraint(["article_id"], ["md_article.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["width_uom_id"], ["md_uom.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", name="uq_md_product_configuration_article"),
    )
    op.create_index(
        "ix_md_product_configuration_article_id",
        "md_product_configuration",
        ["article_id"],
    )
    op.create_index(
        "ix_md_product_configuration_family_code",
        "md_product_configuration",
        ["family_code"],
    )
    op.create_index(
        "ix_md_product_configuration_model_code",
        "md_product_configuration",
        ["model_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_md_product_configuration_model_code",
        table_name="md_product_configuration",
    )
    op.drop_index(
        "ix_md_product_configuration_family_code",
        table_name="md_product_configuration",
    )
    op.drop_index(
        "ix_md_product_configuration_article_id",
        table_name="md_product_configuration",
    )
    op.drop_table("md_product_configuration")
