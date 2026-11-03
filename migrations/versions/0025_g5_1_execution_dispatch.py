"""G5.1 MES execution dispatch foundation.

Revision ID: 0025_g5_1
Revises: 0024_g4_7
Create Date: 2026-11-02
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0025_g5_1"
down_revision = "0024_g4_7"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")
MES_READ_ID = UUID("10000000-0000-0000-0000-000000000020")
MES_EDIT_ID = UUID("10000000-0000-0000-0000-000000000021")


def upgrade() -> None:
    op.create_table(
        "mes_execution_dispatch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_code", sa.String(length=80), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("publication_version_no", sa.Integer(), nullable=False),
        sa.Column("schedule_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'RELEASED', 'CANCELLED')",
            name="ck_mes_dispatch_status",
        ),
        sa.CheckConstraint(
            "(status = 'RELEASED' AND released_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL) OR "
            "status = 'DRAFT'",
            name="ck_mes_dispatch_lifecycle",
        ),
        sa.ForeignKeyConstraint(["publication_id"], ["aps_schedule_publication.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scenario_id"], ["aps_scheduling_scenario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["aps_scheduling_run.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["demand_production_plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_id", name="uq_mes_dispatch_publication"),
        sa.UniqueConstraint("dispatch_code", name="uq_mes_execution_dispatch_dispatch_code"),
    )

    op.create_table(
        "mes_execution_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("published_operation_id", sa.Uuid(), nullable=False),
        sa.Column("planning_operation_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("taquilla_id", sa.Uuid(), nullable=False),
        sa.Column("product_line_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("routing_revision_id", sa.Uuid(), nullable=False),
        sa.Column("routing_operation_id", sa.Uuid(), nullable=False),
        sa.Column("planned_resource_id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("work_center_id", sa.Uuid(), nullable=True),
        sa.Column("deck_position", sa.String(length=20), nullable=False),
        sa.Column("product_sequence_no", sa.Integer(), nullable=False),
        sa.Column("routing_sequence_no", sa.Integer(), nullable=False),
        sa.Column("operation_code", sa.String(length=30), nullable=False),
        sa.Column("operation_description", sa.String(length=1000), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_finish", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("routing_sequence_no > 0", name="ck_mes_execution_routing_sequence_positive"),
        sa.CheckConstraint("product_sequence_no > 0", name="ck_mes_execution_product_sequence_positive"),
        sa.CheckConstraint("requested_quantity > 0", name="ck_mes_execution_requested_quantity_positive"),
        sa.CheckConstraint("planned_finish > planned_start", name="ck_mes_execution_planned_interval"),
        sa.CheckConstraint("status IN ('PENDING')", name="ck_mes_execution_operation_status_g5_1"),
        sa.ForeignKeyConstraint(["dispatch_id"], ["mes_execution_dispatch.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publication_id"], ["aps_schedule_publication.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_operation_id"], ["aps_published_scheduled_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["planning_operation_id"], ["aps_planning_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["demand_production_plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["taquilla_id"], ["demand_taquilla.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_line_id"], ["demand_taquilla_product_line.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["article_id"], ["md_article.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_revision_id"], ["md_routing_revision.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_operation_id"], ["md_routing_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["planned_resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["area_id"], ["core_area.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_center_id"], ["core_work_center.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dispatch_id",
            "published_operation_id",
            name="uq_mes_execution_operation_published",
        ),
    )

    permission_table = sa.table(
        "iam_permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [
            {
                "id": MES_READ_ID,
                "code": "mes.read",
                "description": "Read MES execution dispatches and operation snapshots",
            },
            {
                "id": MES_EDIT_ID,
                "code": "mes.edit",
                "description": "Create and govern MES execution dispatches",
            },
        ],
    )
    role_permission_table = sa.table(
        "iam_role_permission",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        role_permission_table,
        [
            {"role_id": ADMIN_ROLE_ID, "permission_id": MES_READ_ID},
            {"role_id": ADMIN_ROLE_ID, "permission_id": MES_EDIT_ID},
        ],
    )


def downgrade() -> None:
    for permission_id in (MES_EDIT_ID, MES_READ_ID):
        op.execute(
            sa.text(
                "DELETE FROM iam_role_permission "
                "WHERE role_id = :role_id AND permission_id = :permission_id"
            ).bindparams(role_id=ADMIN_ROLE_ID, permission_id=permission_id)
        )
        op.execute(
            sa.text(
                "DELETE FROM iam_permission WHERE id = :permission_id"
            ).bindparams(permission_id=permission_id)
        )

    op.drop_table("mes_execution_operation")
    op.drop_table("mes_execution_dispatch")
