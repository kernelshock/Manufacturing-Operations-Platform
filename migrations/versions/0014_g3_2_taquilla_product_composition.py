"""G3.2 Taquilla product composition.

Revision ID: 0014_g3_2
Revises: 0013_g3_1
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_g3_2"
down_revision = "0013_g3_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demand_taquilla_product_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taquilla_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column(
            "requested_quantity",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column("source_line_key", sa.String(length=200), nullable=True),
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
            "sequence_no > 0",
            name="ck_demand_taquilla_product_line_sequence_positive",
        ),
        sa.CheckConstraint(
            "requested_quantity > 0",
            name="ck_demand_taquilla_product_line_quantity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["md_article.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["taquilla_id"], ["demand_taquilla.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "taquilla_id",
            "sequence_no",
            name="uq_demand_taquilla_product_line_sequence",
        ),
        sa.UniqueConstraint(
            "taquilla_id",
            "source_line_key",
            name="uq_demand_taquilla_product_line_source_key",
        ),
    )
    op.create_index(
        "ix_demand_taquilla_product_line_article_id",
        "demand_taquilla_product_line",
        ["article_id"],
    )
    op.create_index(
        "ix_demand_taquilla_product_line_taquilla_id",
        "demand_taquilla_product_line",
        ["taquilla_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_demand_taquilla_product_line_taquilla_id",
        table_name="demand_taquilla_product_line",
    )
    op.drop_index(
        "ix_demand_taquilla_product_line_article_id",
        table_name="demand_taquilla_product_line",
    )
    op.drop_table("demand_taquilla_product_line")
