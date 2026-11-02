"""G4.4 finite-capacity sequencing engine.

Revision ID: 0022_g4_4
Revises: 0021_g4_3
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_g4_4"
down_revision = "0021_g4_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_aps_run_status", "aps_scheduling_run", type_="check")
    op.create_check_constraint(
        "ck_aps_run_status",
        "aps_scheduling_run",
        "status IN ('CREATED', 'EXPANDED', 'CAPACITY_PROJECTED', 'SCHEDULED', 'CANCELLED')",
    )

    op.create_table(
        "aps_scheduled_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("planning_operation_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_finish", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_seconds", sa.Numeric(24, 6), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("nominal_rate", sa.Numeric(24, 8), nullable=False),
        sa.Column("normalized_rate_uom", sa.String(length=40), nullable=False),
        sa.Column("algorithm_key", sa.String(length=80), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.CheckConstraint("planned_finish > planned_start", name="ck_aps_scheduled_operation_interval"),
        sa.CheckConstraint("processing_seconds > 0", name="ck_aps_scheduled_operation_processing_positive"),
        sa.CheckConstraint("sequence_no > 0", name="ck_aps_scheduled_operation_sequence_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["planning_operation_id"], ["aps_planning_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "planning_operation_id", name="uq_aps_scheduled_operation_source"),
    )

    op.create_table(
        "aps_scheduled_operation_segment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_operation_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("availability_interval_id", sa.Uuid(), nullable=False),
        sa.Column("segment_no", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_rate_per_hour", sa.Numeric(24, 8), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(24, 8), nullable=False),
        sa.CheckConstraint("segment_no > 0", name="ck_aps_schedule_segment_number_positive"),
        sa.CheckConstraint("end_at > start_at", name="ck_aps_schedule_segment_interval"),
        sa.CheckConstraint("effective_rate_per_hour > 0", name="ck_aps_schedule_segment_rate_positive"),
        sa.CheckConstraint("produced_quantity > 0", name="ck_aps_schedule_segment_quantity_positive"),
        sa.ForeignKeyConstraint(["scheduled_operation_id"], ["aps_scheduled_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["availability_interval_id"], ["aps_resource_availability_interval.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheduled_operation_id", "segment_no", name="uq_aps_schedule_segment_number"),
    )


def downgrade() -> None:
    op.drop_table("aps_scheduled_operation_segment")
    op.drop_table("aps_scheduled_operation")
    op.drop_constraint("ck_aps_run_status", "aps_scheduling_run", type_="check")
    op.create_check_constraint(
        "ck_aps_run_status",
        "aps_scheduling_run",
        "status IN ('CREATED', 'EXPANDED', 'CAPACITY_PROJECTED', 'CANCELLED')",
    )
