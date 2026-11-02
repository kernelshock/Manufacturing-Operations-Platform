"""G4.5 schedule lifecycle replan publish.

Revision ID: 0023_g4_5
Revises: 0022_g4_4
"""

from alembic import op
import sqlalchemy as sa

revision = "0023_g4_5"
down_revision = "0022_g4_4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("aps_scheduling_run", sa.Column("replan_from_run_id", sa.Uuid(), nullable=True))
    op.add_column("aps_scheduling_run", sa.Column("replan_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_aps_run_replan_from",
        "aps_scheduling_run",
        "aps_scheduling_run",
        ["replan_from_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "aps_schedule_publication",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("supersedes_publication_id", sa.Uuid(), nullable=True),
        sa.Column("publish_reason", sa.Text(), nullable=True),
        sa.Column("schedule_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_aps_publication_version_positive"),
        sa.CheckConstraint("status IN ('CURRENT', 'SUPERSEDED')", name="ck_aps_publication_status"),
        sa.ForeignKeyConstraint(["scenario_id"], ["aps_scheduling_scenario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_publication_id"], ["aps_schedule_publication.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_id", "version_no", name="uq_aps_publication_scenario_version"),
        sa.UniqueConstraint("run_id", name="uq_aps_publication_run"),
    )

    op.create_table(
        "aps_published_scheduled_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("source_scheduled_operation_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("planned_finish > planned_start", name="ck_aps_published_operation_interval"),
        sa.CheckConstraint("sequence_no > 0", name="ck_aps_published_operation_sequence_positive"),
        sa.ForeignKeyConstraint(["publication_id"], ["aps_schedule_publication.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_scheduled_operation_id"], ["aps_scheduled_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["planning_operation_id"], ["aps_planning_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_id", "source_scheduled_operation_id", name="uq_aps_published_operation_source"),
    )

    op.create_table(
        "aps_published_scheduled_operation_segment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("published_operation_id", sa.Uuid(), nullable=False),
        sa.Column("source_segment_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("segment_no", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_rate_per_hour", sa.Numeric(24, 8), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(24, 8), nullable=False),
        sa.CheckConstraint("segment_no > 0", name="ck_aps_published_segment_number_positive"),
        sa.CheckConstraint("end_at > start_at", name="ck_aps_published_segment_interval"),
        sa.CheckConstraint("effective_rate_per_hour > 0", name="ck_aps_published_segment_rate_positive"),
        sa.CheckConstraint("produced_quantity > 0", name="ck_aps_published_segment_quantity_positive"),
        sa.ForeignKeyConstraint(["published_operation_id"], ["aps_published_scheduled_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_segment_id"], ["aps_scheduled_operation_segment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("published_operation_id", "segment_no", name="uq_aps_published_segment_number"),
    )


def downgrade() -> None:
    op.drop_table("aps_published_scheduled_operation_segment")
    op.drop_table("aps_published_scheduled_operation")
    op.drop_table("aps_schedule_publication")
    op.drop_constraint("fk_aps_run_replan_from", "aps_scheduling_run", type_="foreignkey")
    op.drop_column("aps_scheduling_run", "replan_reason")
    op.drop_column("aps_scheduling_run", "replan_from_run_id")
