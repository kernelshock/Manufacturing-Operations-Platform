"""G3.5 lifecycle and historical completion.

Revision ID: 0017_g3_5
Revises: 0016_g3_4
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_g3_5"
down_revision = "0016_g3_4"
branch_labels = None
depends_on = None


def _add(table: str, prefix: str) -> None:
    for column in (
        sa.Column("historical_completion_classification", sa.String(length=20), nullable=True),
        sa.Column("historical_completion_note", sa.Text(), nullable=True),
        sa.Column("historical_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("historical_completed_by", sa.Uuid(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), nullable=True),
    ):
        op.add_column(table, column)

    op.create_foreign_key(
        f"fk_{prefix}_historical_completed_by",
        table,
        "iam_user",
        ["historical_completed_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        f"fk_{prefix}_cancelled_by",
        table,
        "iam_user",
        ["cancelled_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        f"ck_{prefix}_historical_classification",
        table,
        "historical_completion_classification IS NULL OR "
        "historical_completion_classification IN ('ON_TIME', 'DELAYED')",
    )
    op.create_check_constraint(
        f"ck_{prefix}_historical_complete",
        table,
        "(historical_completion_classification IS NULL "
        "AND historical_completed_at IS NULL AND historical_completed_by IS NULL) OR "
        "(historical_completion_classification IS NOT NULL "
        "AND historical_completed_at IS NOT NULL AND historical_completed_by IS NOT NULL)",
    )
    op.create_check_constraint(
        f"ck_{prefix}_historical_status",
        table,
        "historical_completion_classification IS NULL OR status = 'COMPLETED'",
    )
    op.create_check_constraint(
        f"ck_{prefix}_cancellation_complete",
        table,
        "(cancellation_reason IS NULL AND cancelled_at IS NULL AND cancelled_by IS NULL) OR "
        "(cancellation_reason IS NOT NULL AND cancelled_at IS NOT NULL AND cancelled_by IS NOT NULL)",
    )
    op.create_check_constraint(
        f"ck_{prefix}_cancellation_status",
        table,
        "cancellation_reason IS NULL OR status = 'CANCELLED'",
    )


def _drop(table: str, prefix: str) -> None:
    for name in (
        f"ck_{prefix}_cancellation_status",
        f"ck_{prefix}_cancellation_complete",
        f"ck_{prefix}_historical_status",
        f"ck_{prefix}_historical_complete",
        f"ck_{prefix}_historical_classification",
    ):
        op.drop_constraint(name, table, type_="check")

    op.drop_constraint(f"fk_{prefix}_cancelled_by", table, type_="foreignkey")
    op.drop_constraint(
        f"fk_{prefix}_historical_completed_by",
        table,
        type_="foreignkey",
    )
    for column in (
        "cancelled_by",
        "cancelled_at",
        "cancellation_reason",
        "historical_completed_by",
        "historical_completed_at",
        "historical_completion_note",
        "historical_completion_classification",
    ):
        op.drop_column(table, column)


def upgrade() -> None:
    _add("demand_production_plan", "demand_production_plan")
    _add("demand_taquilla", "demand_taquilla")


def downgrade() -> None:
    _drop("demand_taquilla", "demand_taquilla")
    _drop("demand_production_plan", "demand_production_plan")
