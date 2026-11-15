"""Register plant-scoped governance capabilities for explicit IAM assignment.

Revision ID: 0035_g7_6
Revises: 0034_g7_6
"""
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa

revision = "0035_g7_6"
down_revision = "0034_g7_6"
branch_labels = None
depends_on = None

CAPABILITIES = {
    "read": "Read planning governance cases",
    "purchasing": "Review and close planning governance cases as Purchasing",
    "production": "Review planning governance cases as Production Management",
    "quality": "Review planning governance cases as Quality",
    "direction": "Review, reject and close planning governance cases as Direction",
}
PERMISSIONS = [
    {"id": uuid5(NAMESPACE_URL, f"faic-mop/g7/planning.governance.{name}"),
     "code": f"planning.governance.{name}", "description": description}
    for name, description in CAPABILITIES.items()
]


def upgrade():
    permissions = sa.table(
        "iam_permission", sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()), sa.column("description", sa.String()),
    )
    op.bulk_insert(permissions, PERMISSIONS)


def downgrade():
    role_permissions = sa.table("iam_role_permission", sa.column("permission_id", sa.Uuid()))
    permissions = sa.table("iam_permission", sa.column("id", sa.Uuid()))
    ids = [entry["id"] for entry in PERMISSIONS]
    op.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(ids)))
    op.execute(permissions.delete().where(permissions.c.id.in_(ids)))
