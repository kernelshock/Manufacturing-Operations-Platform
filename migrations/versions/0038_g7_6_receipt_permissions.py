"""Register scoped receipt capabilities."""

from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa

revision = "0038_g7_6"
down_revision = "0037_g7_6"
branch_labels = None
depends_on = None

PERMISSIONS = [
    {"id": uuid5(NAMESPACE_URL, f"faic-mop/g7/{code}"), "code": code, "description": description}
    for code, description in (
        ("materials.receipt.receive", "Receive material lots into quarantine"),
        ("materials.receipt.read", "Read receipt lots and disposition balances"),
    )
]


def upgrade():
    permissions = sa.table(
        "iam_permission", sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()), sa.column("description", sa.String()),
    )
    op.bulk_insert(permissions, PERMISSIONS)


def downgrade():
    grants = sa.table("iam_role_permission", sa.column("permission_id", sa.Uuid()))
    permissions = sa.table("iam_permission", sa.column("id", sa.Uuid()))
    ids = [permission["id"] for permission in PERMISSIONS]
    op.execute(grants.delete().where(grants.c.permission_id.in_(ids)))
    op.execute(permissions.delete().where(permissions.c.id.in_(ids)))
