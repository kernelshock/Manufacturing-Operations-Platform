"""Add immutable receipt lots and disposition events."""

from alembic import op
import sqlalchemy as sa

revision = "0037_g7_6"
down_revision = "0036_g7_6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mat_receipt_lot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("receipt_line_ref", sa.String(128), nullable=False),
        sa.Column("lot_ref", sa.String(128), nullable=False),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("mat_location.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uom_id", sa.Uuid(), sa.ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("movement_id", sa.Uuid(), sa.ForeignKey("mat_movement.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.UniqueConstraint("receipt_line_ref", "lot_ref", name="uq_mat_receipt_lot_reference"),
        sa.CheckConstraint("quantity > 0", name="ck_mat_receipt_lot_quantity"),
    )
    op.create_index("ix_mat_receipt_lot_stock", "mat_receipt_lot", ["article_id", "location_id"])
    op.create_table(
        "mat_receipt_decision",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lot_id", sa.Uuid(), sa.ForeignKey("mat_receipt_lot.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("decision_ref", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("verified_release_quantity", sa.Numeric(24, 8)),
        sa.Column("movement_id", sa.Uuid(), sa.ForeignKey("mat_movement.id", ondelete="RESTRICT"), unique=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("lot_id", "revision", name="uq_mat_receipt_decision_revision"),
        sa.UniqueConstraint("lot_id", "decision_ref", name="uq_mat_receipt_decision_reference"),
        sa.CheckConstraint("quantity > 0 AND revision > 0", name="ck_mat_receipt_decision_values"),
    )
    op.execute("""
        CREATE FUNCTION mop_receipt_reject_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'receipt evidence is append-only';
        END; $$
    """)
    for table in ("mat_receipt_lot", "mat_receipt_decision"):
        op.execute(f"""
            CREATE TRIGGER trg_receipt_append_only
            BEFORE UPDATE OR DELETE OR TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION mop_receipt_reject_mutation()
        """)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM mat_receipt_lot)")):
        raise RuntimeError("receipt lot history must be preserved before downgrade")
    op.drop_table("mat_receipt_decision")
    op.drop_table("mat_receipt_lot")
    op.execute("DROP FUNCTION mop_receipt_reject_mutation()")
