"""G3.1 production plan and Taquilla foundation.

Revision ID: 0013_g3_1
Revises: 0012_g2_7
Create Date: 2026-10-29
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0013_g3_1"
down_revision = "0012_g2_7"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")
DEMAND_READ_ID = UUID("10000000-0000-0000-0000-000000000016")
DEMAND_EDIT_ID = UUID("10000000-0000-0000-0000-000000000017")


def upgrade() -> None:
    op.create_table(
        "demand_production_plan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_number", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'OPEN', 'COMPLETED', 'CANCELLED')",
            name="ck_demand_production_plan_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_number", name="uq_demand_production_plan_plan_number"),
    )

    op.create_table(
        "demand_taquilla",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("taquilla_code", sa.String(length=80), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence_no > 0",
            name="ck_demand_taquilla_sequence_positive",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'READY', 'COMPLETED', 'CANCELLED')",
            name="ck_demand_taquilla_status",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["demand_production_plan.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_id", "sequence_no", name="uq_demand_taquilla_plan_sequence"
        ),
        sa.UniqueConstraint("taquilla_code", name="uq_demand_taquilla_taquilla_code"),
    )
    op.create_index(
        "ix_demand_taquilla_plan_id", "demand_taquilla", ["plan_id"]
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
                "id": DEMAND_READ_ID,
                "code": "demand.read",
                "description": "Read production plans and Taquilla demand",
            },
            {
                "id": DEMAND_EDIT_ID,
                "code": "demand.edit",
                "description": "Create or modify production plans and Taquilla demand",
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
            {"role_id": ADMIN_ROLE_ID, "permission_id": DEMAND_READ_ID},
            {"role_id": ADMIN_ROLE_ID, "permission_id": DEMAND_EDIT_ID},
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM iam_role_permission "
            "WHERE role_id = :role_id AND permission_id = :permission_id"
        ).bindparams(role_id=ADMIN_ROLE_ID, permission_id=DEMAND_EDIT_ID)
    )
    op.execute(
        sa.text(
            "DELETE FROM iam_role_permission "
            "WHERE role_id = :role_id AND permission_id = :permission_id"
        ).bindparams(role_id=ADMIN_ROLE_ID, permission_id=DEMAND_READ_ID)
    )
    op.execute(
        sa.text("DELETE FROM iam_permission WHERE id = :permission_id").bindparams(
            permission_id=DEMAND_EDIT_ID
        )
    )
    op.execute(
        sa.text("DELETE FROM iam_permission WHERE id = :permission_id").bindparams(
            permission_id=DEMAND_READ_ID
        )
    )
    op.drop_index("ix_demand_taquilla_plan_id", table_name="demand_taquilla")
    op.drop_table("demand_taquilla")
    op.drop_table("demand_production_plan")
