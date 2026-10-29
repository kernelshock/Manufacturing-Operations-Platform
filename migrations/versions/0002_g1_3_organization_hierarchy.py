"""G1.3 organization hierarchy.

Revision ID: 0002_g1_3
Revises: 0001_g1_2
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_g1_3"
down_revision = "0001_g1_2"
branch_labels = None
depends_on = None


def _common_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "core_organization",
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_core_organization_code"),
    )

    op.create_table(
        "core_plant",
        *_common_columns(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["core_organization.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_core_plant_org_code"),
    )
    op.create_index("ix_core_plant_organization_id", "core_plant", ["organization_id"])

    op.create_table(
        "core_area",
        *_common_columns(),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["plant_id"], ["core_plant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plant_id", "code", name="uq_core_area_plant_code"),
    )
    op.create_index("ix_core_area_plant_id", "core_area", ["plant_id"])

    op.create_table(
        "core_work_center",
        *_common_columns(),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["core_area.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("area_id", "code", name="uq_core_work_center_area_code"),
    )
    op.create_index("ix_core_work_center_area_id", "core_work_center", ["area_id"])

    op.create_table(
        "core_resource",
        *_common_columns(),
        sa.Column("work_center_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), server_default="generic", nullable=False),
        sa.ForeignKeyConstraint(["work_center_id"], ["core_work_center.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_center_id", "code", name="uq_core_resource_wc_code"),
    )
    op.create_index("ix_core_resource_work_center_id", "core_resource", ["work_center_id"])


def downgrade() -> None:
    op.drop_index("ix_core_resource_work_center_id", table_name="core_resource")
    op.drop_table("core_resource")
    op.drop_index("ix_core_work_center_area_id", table_name="core_work_center")
    op.drop_table("core_work_center")
    op.drop_index("ix_core_area_plant_id", table_name="core_area")
    op.drop_table("core_area")
    op.drop_index("ix_core_plant_organization_id", table_name="core_plant")
    op.drop_table("core_plant")
    op.drop_table("core_organization")
