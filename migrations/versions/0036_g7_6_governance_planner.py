"""Register the scoped planning capability for G7.6 intake."""

from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa

revision = "0036_g7_6"
down_revision = "0035_g7_6"
branch_labels = None
depends_on = None

CODE = "planning.governance.planner"
PERMISSION_ID = uuid5(NAMESPACE_URL, f"faic-mop/g7/{CODE}")


def upgrade():
    permissions = sa.table(
        "iam_permission", sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()), sa.column("description", sa.String()),
    )
    op.bulk_insert(permissions, [{
        "id": PERMISSION_ID, "code": CODE,
        "description": "Submit verified material stoppage cases as Planning",
    }])


def downgrade():
    grants = sa.table("iam_role_permission", sa.column("permission_id", sa.Uuid()))
    permissions = sa.table("iam_permission", sa.column("id", sa.Uuid()))
    op.execute(grants.delete().where(grants.c.permission_id == PERMISSION_ID))
    op.execute(permissions.delete().where(permissions.c.id == PERMISSION_ID))
