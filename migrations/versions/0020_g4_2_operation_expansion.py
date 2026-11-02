"""G4.2 operation expansion.

Revision ID: 0020_g4_2
Revises: 0019_g4_1
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_g4_2"
down_revision = "0019_g4_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_aps_run_status", "aps_scheduling_run", type_="check")
    op.add_column("aps_scheduling_run", sa.Column("input_fingerprint", sa.String(length=64), nullable=True))
    op.add_column("aps_scheduling_run", sa.Column("expanded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("aps_scheduling_run", sa.Column("operation_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_aps_run_status", "aps_scheduling_run", "status IN ('CREATED', 'EXPANDED', 'CANCELLED')")

    op.create_table(
        "aps_planning_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("taquilla_id", sa.Uuid(), nullable=False),
        sa.Column("product_line_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("routing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("routing_operation_id", sa.Uuid(), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("deck_position", sa.String(length=20), nullable=False),
        sa.Column("product_sequence_no", sa.Integer(), nullable=False),
        sa.Column("routing_sequence_no", sa.Integer(), nullable=False),
        sa.Column("source_operation_code", sa.String(length=30), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("operation_kind", sa.String(length=30), nullable=False),
        sa.Column("schedulable", sa.Boolean(), nullable=False),
        sa.Column("completion_marker", sa.Boolean(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("work_center_id", sa.Uuid(), nullable=True),
        sa.Column("nominal_rate", sa.Numeric(24, 8), nullable=True),
        sa.Column("rate_uom", sa.String(length=50), nullable=True),
        sa.Column("routing_source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "product_line_id", "routing_operation_id", name="uq_aps_planning_operation_source"),
        sa.ForeignKeyConstraint(["run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["demand_production_plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["taquilla_id"], ["demand_taquilla.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_line_id"], ["demand_taquilla_product_line.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["article_id"], ["md_article.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_revision_id"], ["md_routing_revision.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_operation_id"], ["md_routing_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["area_id"], ["core_area.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_center_id"], ["core_work_center.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    op.drop_table("aps_planning_operation")
    op.drop_constraint("ck_aps_run_status", "aps_scheduling_run", type_="check")
    op.drop_column("aps_scheduling_run", "operation_count")
    op.drop_column("aps_scheduling_run", "expanded_at")
    op.drop_column("aps_scheduling_run", "input_fingerprint")
    op.create_check_constraint("ck_aps_run_status", "aps_scheduling_run", "status IN ('CREATED', 'CANCELLED')")
