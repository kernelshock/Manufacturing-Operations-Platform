"""G4.1 scheduling domain and scenario foundation.

Revision ID: 0019_g4_1
Revises: 0018_g3_6
Create Date: 2026-11-02
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0019_g4_1"
down_revision = "0018_g3_6"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")
APS_READ_ID = UUID("10000000-0000-0000-0000-000000000018")
APS_EDIT_ID = UUID("10000000-0000-0000-0000-000000000019")


def upgrade() -> None:
    op.create_table(
        "aps_scheduling_scenario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("horizon_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planning_timezone", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT', 'READY', 'ARCHIVED')", name="ck_aps_scenario_status"),
        sa.CheckConstraint("horizon_end > horizon_start", name="ck_aps_scenario_horizon"),
        sa.ForeignKeyConstraint(["plan_id"], ["demand_production_plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_code", name="uq_aps_scheduling_scenario_scenario_code"),
    )
    op.create_index("ix_aps_scheduling_scenario_plan_id", "aps_scheduling_scenario", ["plan_id"])

    op.create_table(
        "aps_scheduling_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("algorithm_key", sa.String(length=80), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("run_number > 0", name="ck_aps_run_number_positive"),
        sa.CheckConstraint("status IN ('CREATED', 'CANCELLED')", name="ck_aps_run_status"),
        sa.ForeignKeyConstraint(["scenario_id"], ["aps_scheduling_scenario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_id", "run_number", name="uq_aps_run_scenario_number"),
    )
    op.create_index("ix_aps_scheduling_run_scenario_id", "aps_scheduling_run", ["scenario_id"])

    permission_table = sa.table("iam_permission", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("description", sa.String()))
    op.bulk_insert(permission_table, [
        {"id": APS_READ_ID, "code": "aps.read", "description": "Read APS scheduling scenarios and planning runs"},
        {"id": APS_EDIT_ID, "code": "aps.edit", "description": "Create or modify APS scheduling scenarios and planning runs"},
    ])
    role_permission_table = sa.table("iam_role_permission", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid()))
    op.bulk_insert(role_permission_table, [
        {"role_id": ADMIN_ROLE_ID, "permission_id": APS_READ_ID},
        {"role_id": ADMIN_ROLE_ID, "permission_id": APS_EDIT_ID},
    ])


def downgrade() -> None:
    for permission_id in (APS_EDIT_ID, APS_READ_ID):
        op.execute(sa.text("DELETE FROM iam_role_permission WHERE role_id = :role_id AND permission_id = :permission_id").bindparams(role_id=ADMIN_ROLE_ID, permission_id=permission_id))
        op.execute(sa.text("DELETE FROM iam_permission WHERE id = :permission_id").bindparams(permission_id=permission_id))
    op.drop_index("ix_aps_scheduling_run_scenario_id", table_name="aps_scheduling_run")
    op.drop_table("aps_scheduling_run")
    op.drop_index("ix_aps_scheduling_scenario_plan_id", table_name="aps_scheduling_scenario")
    op.drop_table("aps_scheduling_scenario")
