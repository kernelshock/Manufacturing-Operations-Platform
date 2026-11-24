"""G7.6 durable exception snapshots and append-only governance events.

Revision ID: 0034_g7_6
Revises: 0033_g6_6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0034_g7_6"
down_revision = "0033_g6_6"
branch_labels = None
depends_on = None

CASE_TABLE = "planning_governance_case"
EVENT_TABLE = "planning_governance_event"


def upgrade():
    op.create_table(
        CASE_TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plant_id", sa.Uuid(), sa.ForeignKey("core_plant.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uom_id", sa.Uuid(), sa.ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("creator_id", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_planning_governance_case_plant_created",
        CASE_TABLE,
        ["plant_id", "created_at", "id"],
    )
    op.create_table(
        EVENT_TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey(f"{CASE_TABLE}.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(24), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_refs", JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("audit_entry_id", sa.Uuid(), sa.ForeignKey("audit_event.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_planning_governance_event_revision"),
        sa.CheckConstraint(
            "kind IN ('SUBMIT', 'ACKNOWLEDGE', 'APPROVE', 'REJECT', 'CLOSE')",
            name="ck_planning_governance_event_kind",
        ),
        sa.CheckConstraint(
            "actor_role IN ('PLANNER', 'PURCHASING', 'QUALITY', 'PRODUCTION_MANAGER', 'DIRECTOR')",
            name="ck_planning_governance_event_actor_role",
        ),
        sa.UniqueConstraint("case_id", "revision", name="uq_planning_governance_event_revision"),
        sa.UniqueConstraint("actor_id", "idempotency_key", name="uq_planning_governance_event_retry"),
        sa.UniqueConstraint("audit_entry_id", name="uq_planning_governance_event_audit"),
    )
    op.execute("""
        CREATE FUNCTION mop_governance_reject_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'planning governance records are append-only';
        END; $$
    """)
    for table in (CASE_TABLE, EVENT_TABLE):
        op.execute(f"""
            CREATE TRIGGER trg_governance_append_only
            BEFORE UPDATE OR DELETE OR TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION mop_governance_reject_mutation()
        """)


def downgrade():
    op.drop_table(EVENT_TABLE)
    op.drop_table(CASE_TABLE)
    op.execute("DROP FUNCTION mop_governance_reject_mutation()")
