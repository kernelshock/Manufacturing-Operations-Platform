"""G4.7 isolated what-if and exception evaluation.

Revision ID: 0024_g4_7
Revises: 0023_g4_5
"""

from alembic import op
import sqlalchemy as sa

revision = "0024_g4_7"
down_revision = "0023_g4_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aps_whatif_scenario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("baseline_publication_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_run_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_publication_id", sa.Uuid(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'EVALUATED', 'APPLIED', 'DISCARDED')",
            name="ck_aps_whatif_status",
        ),
        sa.CheckConstraint(
            "(status = 'EVALUATED' AND candidate_run_id IS NOT NULL AND evaluated_at IS NOT NULL) "
            "OR (status = 'APPLIED' AND candidate_run_id IS NOT NULL AND evaluated_at IS NOT NULL AND applied_publication_id IS NOT NULL AND applied_at IS NOT NULL) "
            "OR (status = 'DISCARDED' AND discarded_at IS NOT NULL) "
            "OR status = 'DRAFT'",
            name="ck_aps_whatif_lifecycle",
        ),
        sa.ForeignKeyConstraint(["baseline_publication_id"], ["aps_schedule_publication.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_publication_id"], ["aps_schedule_publication.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_code", name="uq_aps_whatif_scenario_code"),
    )

    op.create_table(
        "aps_whatif_exception",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("whatif_scenario_id", sa.Uuid(), nullable=False),
        sa.Column("exception_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity_factor", sa.Numeric(12, 8), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "exception_type IN ('RESOURCE_BLACKOUT', 'RESOURCE_CAPACITY_FACTOR')",
            name="ck_aps_whatif_exception_type",
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_aps_whatif_exception_interval"),
        sa.CheckConstraint(
            "(exception_type = 'RESOURCE_BLACKOUT' AND capacity_factor IS NULL) OR "
            "(exception_type = 'RESOURCE_CAPACITY_FACTOR' AND capacity_factor > 0)",
            name="ck_aps_whatif_exception_payload",
        ),
        sa.ForeignKeyConstraint(["whatif_scenario_id"], ["aps_whatif_scenario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("aps_whatif_exception")
    op.drop_table("aps_whatif_scenario")
