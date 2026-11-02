"""G4.3 calendar and capacity projection.

Revision ID: 0021_g4_3
Revises: 0020_g4_2
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_g4_3"
down_revision = "0020_g4_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_aps_run_status", "aps_scheduling_run", type_="check")
    op.create_check_constraint(
        "ck_aps_run_status",
        "aps_scheduling_run",
        "status IN ('CREATED', 'EXPANDED', 'CAPACITY_PROJECTED', 'CANCELLED')",
    )

    op.create_table(
        "aps_capacity_candidate",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("planning_operation_id", sa.Uuid(), nullable=False),
        sa.Column("routing_operation_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("source_mode", sa.String(length=30), nullable=False),
        sa.Column("resource_assignment_id", sa.Uuid(), nullable=True),
        sa.Column("assignment_capacity_factor", sa.Numeric(12, 8), nullable=False),
        sa.CheckConstraint("source_mode IN ('EXPLICIT_ASSIGNMENT', 'WORK_CENTER_POOL')", name="ck_aps_capacity_candidate_source_mode"),
        sa.CheckConstraint("assignment_capacity_factor > 0", name="ck_aps_capacity_candidate_assignment_factor"),
        sa.ForeignKeyConstraint(["run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["planning_operation_id"], ["aps_planning_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_operation_id"], ["md_routing_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_assignment_id"], ["md_resource_assignment.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "planning_operation_id", "resource_id", name="uq_aps_capacity_candidate_source"),
    )

    op.create_table(
        "aps_resource_availability_interval",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("calendar_id", sa.Uuid(), nullable=False),
        sa.Column("calendar_code", sa.String(length=80), nullable=False),
        sa.Column("calendar_revision_no", sa.Integer(), nullable=False),
        sa.Column("target_scope", sa.String(length=20), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calendar_capacity_factor", sa.Numeric(12, 8), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.CheckConstraint("end_at > start_at", name="ck_aps_resource_availability_interval_shape"),
        sa.CheckConstraint("calendar_capacity_factor > 0", name="ck_aps_resource_availability_calendar_factor"),
        sa.ForeignKeyConstraint(["run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["calendar_id"], ["md_manufacturing_calendar.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "resource_id", "start_at", "end_at", name="uq_aps_resource_availability_interval"),
    )


def downgrade() -> None:
    op.drop_table("aps_resource_availability_interval")
    op.drop_table("aps_capacity_candidate")
    op.drop_constraint("ck_aps_run_status", "aps_scheduling_run", type_="check")
    op.create_check_constraint(
        "ck_aps_run_status",
        "aps_scheduling_run",
        "status IN ('CREATED', 'EXPANDED', 'CANCELLED')",
    )
