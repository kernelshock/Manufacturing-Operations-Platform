"""Inspection policies and cryptographically signed receipt release."""

from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0040_g7_6"
down_revision = "0039_g7_6"
branch_labels = None
depends_on = None

PERMISSIONS = {
    "configure": "Configure receipt inspection criteria",
    "engineering": "Release engineering material as Engineering",
    "laboratory": "Release engineering material as Laboratory",
    "area": "Release material as its responsible area leader",
}
TABLES = ("mat_receipt_signer_key", "mat_receipt_signer_revocation",
          "mat_receipt_inspection_policy", "mat_receipt_release_evidence")


def user_column(name):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False)


def upgrade():
    op.create_table(TABLES[0],
        sa.Column("id", sa.Uuid(), primary_key=True),
        user_column("user_id"),
        sa.Column("public_key", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("identity_reference", sa.String(128), nullable=False),
        user_column("registered_by"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("octet_length(public_key) = 32", name="ck_receipt_signer_key_length"),
    )
    op.create_table(TABLES[1],
        sa.Column("key_id", sa.Uuid(), sa.ForeignKey(f"{TABLES[0]}.id", ondelete="RESTRICT"), primary_key=True),
        user_column("actor_id"),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(TABLES[2],
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lot_id", sa.Uuid(), sa.ForeignKey("mat_receipt_lot.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("engineering_defined", sa.Boolean(), nullable=False),
        sa.Column("responsible_area_id", sa.Uuid(), sa.ForeignKey("core_area.id", ondelete="RESTRICT")),
        sa.Column("criteria", JSONB(), nullable=False),
        user_column("configured_by"),
        sa.Column("configured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("lot_id", "revision", name="uq_receipt_policy_revision"),
        sa.CheckConstraint("revision > 0 AND (engineering_defined OR responsible_area_id IS NOT NULL)",
                           name="ck_receipt_policy_scope"),
    )
    op.create_table(TABLES[3],
        sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("mat_receipt_decision.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("policy_id", sa.Uuid(), sa.ForeignKey(f"{TABLES[2]}.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("key_id", sa.Uuid(), sa.ForeignKey(f"{TABLES[0]}.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.Column("signed_payload", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("octet_length(document) BETWEEN 1 AND 1048576 AND octet_length(signature) = 64",
                           name="ck_receipt_release_bytes"),
    )
    for table in TABLES:
        op.execute(f"""
            CREATE TRIGGER trg_receipt_append_only
            BEFORE UPDATE OR DELETE OR TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION mop_receipt_reject_mutation()
        """)
    permissions = sa.table("iam_permission", sa.column("id", sa.Uuid()),
                           sa.column("code", sa.String()), sa.column("description", sa.String()))
    op.bulk_insert(permissions, [
        {"id": uuid5(NAMESPACE_URL, f"faic-mop/g7/materials.release.{name}"),
         "code": f"materials.release.{name}", "description": description}
        for name, description in PERMISSIONS.items()
    ])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM mat_receipt_release_evidence)")):
        raise RuntimeError("signed release evidence must be preserved before downgrade")
    grants = sa.table("iam_role_permission", sa.column("permission_id", sa.Uuid()))
    permissions = sa.table("iam_permission", sa.column("id", sa.Uuid()))
    ids = [uuid5(NAMESPACE_URL, f"faic-mop/g7/materials.release.{name}") for name in PERMISSIONS]
    op.execute(grants.delete().where(grants.c.permission_id.in_(ids)))
    op.execute(permissions.delete().where(permissions.c.id.in_(ids)))
    for table in reversed(TABLES):
        op.drop_table(table)
