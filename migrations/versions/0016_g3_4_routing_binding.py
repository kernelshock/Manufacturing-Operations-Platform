"""G3.4 routing binding.

Revision ID: 0016_g3_4
Revises: 0015_g3_3
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_g3_4"
down_revision = "0015_g3_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("routing_revision_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("routing_binding_mode", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("routing_effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("routing_override_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("routing_bound_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("routing_bound_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_demand_taquilla_product_line_routing_revision",
        "demand_taquilla_product_line",
        "md_routing_revision",
        ["routing_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_demand_taquilla_product_line_routing_bound_by",
        "demand_taquilla_product_line",
        "iam_user",
        ["routing_bound_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_demand_taquilla_product_line_routing_revision_id",
        "demand_taquilla_product_line",
        ["routing_revision_id"],
    )
    op.create_check_constraint(
        "ck_demand_taquilla_product_line_routing_binding_mode",
        "demand_taquilla_product_line",
        "routing_binding_mode IS NULL OR routing_binding_mode IN ('RESOLVED', 'OVERRIDE')",
    )
    op.create_check_constraint(
        "ck_demand_taquilla_product_line_routing_binding_complete",
        "demand_taquilla_product_line",
        "(routing_revision_id IS NULL AND routing_binding_mode IS NULL "
        "AND routing_effective_at IS NULL AND routing_override_reason IS NULL "
        "AND routing_bound_at IS NULL AND routing_bound_by IS NULL) OR "
        "(routing_revision_id IS NOT NULL AND routing_binding_mode IS NOT NULL "
        "AND routing_effective_at IS NOT NULL AND routing_bound_at IS NOT NULL "
        "AND routing_bound_by IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_demand_taquilla_product_line_routing_override_reason",
        "demand_taquilla_product_line",
        "(routing_binding_mode = 'OVERRIDE' AND routing_override_reason IS NOT NULL) OR "
        "(routing_binding_mode IS DISTINCT FROM 'OVERRIDE' AND routing_override_reason IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_demand_taquilla_product_line_routing_override_reason",
        "demand_taquilla_product_line",
        type_="check",
    )
    op.drop_constraint(
        "ck_demand_taquilla_product_line_routing_binding_complete",
        "demand_taquilla_product_line",
        type_="check",
    )
    op.drop_constraint(
        "ck_demand_taquilla_product_line_routing_binding_mode",
        "demand_taquilla_product_line",
        type_="check",
    )
    op.drop_index(
        "ix_demand_taquilla_product_line_routing_revision_id",
        table_name="demand_taquilla_product_line",
    )
    op.drop_constraint(
        "fk_demand_taquilla_product_line_routing_bound_by",
        "demand_taquilla_product_line",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_demand_taquilla_product_line_routing_revision",
        "demand_taquilla_product_line",
        type_="foreignkey",
    )
    op.drop_column("demand_taquilla_product_line", "routing_bound_by")
    op.drop_column("demand_taquilla_product_line", "routing_bound_at")
    op.drop_column("demand_taquilla_product_line", "routing_override_reason")
    op.drop_column("demand_taquilla_product_line", "routing_effective_at")
    op.drop_column("demand_taquilla_product_line", "routing_binding_mode")
    op.drop_column("demand_taquilla_product_line", "routing_revision_id")
