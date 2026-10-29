"""G1.5 append-only audit trail.

Revision ID: 0004_g1_5
Revises: 0003_g1_4
Create Date: 2026-10-28
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_g1_5"
down_revision = "0003_g1_4"
branch_labels = None
depends_on = None

AUDIT_READ_PERMISSION_ID = UUID("10000000-0000-0000-0000-000000000013")
ADMIN_ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_username", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("object_type", sa.String(length=128), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=True),
        sa.Column("scope_type", sa.String(length=32), nullable=True),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_occurred_at", "audit_event", ["occurred_at"])
    op.create_index("ix_audit_event_action", "audit_event", ["action"])
    op.create_index("ix_audit_event_actor_user_id", "audit_event", ["actor_user_id"])

    op.execute(
        """
        CREATE FUNCTION mop_audit_reject_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_event is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_event_append_only
        BEFORE UPDATE OR DELETE ON audit_event
        FOR EACH ROW
        EXECUTE FUNCTION mop_audit_reject_mutation();
        """
    )

    permission_table = sa.table(
        "iam_permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [{
            "id": AUDIT_READ_PERMISSION_ID,
            "code": "audit.read",
            "description": "Read immutable platform audit events",
        }],
    )

    role_permission_table = sa.table(
        "iam_role_permission",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        role_permission_table,
        [{"role_id": ADMIN_ROLE_ID, "permission_id": AUDIT_READ_PERMISSION_ID}],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM iam_role_permission WHERE role_id = :role_id AND permission_id = :permission_id"
        ).bindparams(role_id=ADMIN_ROLE_ID, permission_id=AUDIT_READ_PERMISSION_ID)
    )
    op.execute(
        sa.text("DELETE FROM iam_permission WHERE id = :permission_id").bindparams(
            permission_id=AUDIT_READ_PERMISSION_ID
        )
    )
    op.execute("DROP TRIGGER IF EXISTS trg_audit_event_append_only ON audit_event")
    op.execute("DROP FUNCTION IF EXISTS mop_audit_reject_mutation()")
    op.drop_index("ix_audit_event_actor_user_id", table_name="audit_event")
    op.drop_index("ix_audit_event_action", table_name="audit_event")
    op.drop_index("ix_audit_event_occurred_at", table_name="audit_event")
    op.drop_table("audit_event")
