"""G3.3 vehicle and deck topology.

Revision ID: 0015_g3_3
Revises: 0014_g3_2
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_g3_3"
down_revision = "0014_g3_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "demand_taquilla",
        sa.Column(
            "vehicle_topology",
            sa.String(length=20),
            server_default="SIMPLE",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_demand_taquilla_vehicle_topology",
        "demand_taquilla",
        "vehicle_topology IN ('SIMPLE', 'DOUBLE_DECK')",
    )

    op.add_column(
        "demand_taquilla_product_line",
        sa.Column(
            "deck_position",
            sa.String(length=20),
            server_default="SINGLE",
            nullable=False,
        ),
    )
    op.add_column(
        "demand_taquilla_product_line",
        sa.Column("source_document_key", sa.String(length=200), nullable=True),
    )
    op.create_check_constraint(
        "ck_demand_taquilla_product_line_deck_position",
        "demand_taquilla_product_line",
        "deck_position IN ('SINGLE', 'UPPER', 'LOWER')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_demand_taquilla_product_line_deck_position",
        "demand_taquilla_product_line",
        type_="check",
    )
    op.drop_column("demand_taquilla_product_line", "source_document_key")
    op.drop_column("demand_taquilla_product_line", "deck_position")
    op.drop_constraint(
        "ck_demand_taquilla_vehicle_topology",
        "demand_taquilla",
        type_="check",
    )
    op.drop_column("demand_taquilla", "vehicle_topology")
