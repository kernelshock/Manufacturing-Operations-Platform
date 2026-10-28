"""G1.4 local identity, sessions and RBAC.

Revision ID: 0003_g1_4
Revises: 0002_g1_3
Create Date: 2026-10-28
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0003_g1_4"
down_revision = "0002_g1_3"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")
PERMISSIONS = [
    (UUID("10000000-0000-0000-0000-000000000001"), "admin.users", "Manage local users and role assignments"),
    (UUID("10000000-0000-0000-0000-000000000002"), "admin.roles", "Manage roles and role permissions"),
    (UUID("10000000-0000-0000-0000-000000000003"), "core.organization.read", "Read organizations"),
    (UUID("10000000-0000-0000-0000-000000000004"), "core.organization.write", "Create or modify organizations"),
    (UUID("10000000-0000-0000-0000-000000000005"), "core.plant.read", "Read plants"),
    (UUID("10000000-0000-0000-0000-000000000006"), "core.plant.write", "Create or modify plants"),
    (UUID("10000000-0000-0000-0000-000000000007"), "core.area.read", "Read areas"),
    (UUID("10000000-0000-0000-0000-000000000008"), "core.area.write", "Create or modify areas"),
    (UUID("10000000-0000-0000-0000-000000000009"), "core.workcenter.read", "Read work centers"),
    (UUID("10000000-0000-0000-0000-000000000010"), "core.workcenter.write", "Create or modify work centers"),
    (UUID("10000000-0000-0000-0000-000000000011"), "core.resource.read", "Read resources"),
    (UUID("10000000-0000-0000-0000-000000000012"), "core.resource.write", "Create or modify resources"),
]


def upgrade() -> None:
    op.create_table(
        "iam_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_iam_user_username"),
    )

    op.create_table(
        "iam_role",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_iam_role_code"),
    )

    op.create_table(
        "iam_permission",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_iam_permission_code"),
    )

    op.create_table(
        "iam_role_permission",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["iam_role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["iam_permission.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "iam_user_role_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), server_default="global", nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type IN ('organization', 'plant', 'area') AND scope_id IS NOT NULL)",
            name="ck_iam_assignment_scope",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["iam_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["iam_role.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_iam_assignment_user_id", "iam_user_role_assignment", ["user_id"])
    op.create_index("ix_iam_assignment_role_id", "iam_user_role_assignment", ["role_id"])
    op.create_index(
        "uq_iam_assignment_global",
        "iam_user_role_assignment",
        ["user_id", "role_id"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'global'"),
    )
    op.create_index(
        "uq_iam_assignment_scoped",
        "iam_user_role_assignment",
        ["user_id", "role_id", "scope_type", "scope_id"],
        unique=True,
        postgresql_where=sa.text("scope_type <> 'global'"),
    )

    op.create_table(
        "iam_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["iam_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_iam_session_token_hash"),
    )
    op.create_index("ix_iam_session_user_id", "iam_session", ["user_id"])
    op.create_index("ix_iam_session_expires_at", "iam_session", ["expires_at"])

    permission_table = sa.table(
        "iam_permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [{"id": permission_id, "code": code, "description": description} for permission_id, code, description in PERMISSIONS],
    )

    role_table = sa.table(
        "iam_role",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("active", sa.Boolean()),
        sa.column("system", sa.Boolean()),
    )
    op.bulk_insert(
        role_table,
        [{
            "id": ADMIN_ROLE_ID,
            "code": "ADMIN",
            "name": "Platform Administrator",
            "description": "Built-in global administrator role",
            "active": True,
            "system": True,
        }],
    )

    role_permission_table = sa.table(
        "iam_role_permission",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        role_permission_table,
        [{"role_id": ADMIN_ROLE_ID, "permission_id": permission_id} for permission_id, _, _ in PERMISSIONS],
    )


def downgrade() -> None:
    op.drop_index("ix_iam_session_expires_at", table_name="iam_session")
    op.drop_index("ix_iam_session_user_id", table_name="iam_session")
    op.drop_table("iam_session")
    op.drop_index("uq_iam_assignment_scoped", table_name="iam_user_role_assignment")
    op.drop_index("uq_iam_assignment_global", table_name="iam_user_role_assignment")
    op.drop_index("ix_iam_assignment_role_id", table_name="iam_user_role_assignment")
    op.drop_index("ix_iam_assignment_user_id", table_name="iam_user_role_assignment")
    op.drop_table("iam_user_role_assignment")
    op.drop_table("iam_role_permission")
    op.drop_table("iam_permission")
    op.drop_table("iam_role")
    op.drop_table("iam_user")
