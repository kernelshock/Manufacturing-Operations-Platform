"""G6.4 measured material consumption and linked ledger corrections.

Revision ID: 0031_g6_4
Revises: 0030_g6_2
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_g6_4"
down_revision = "0030_g6_2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mat_consumption",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("execution_operation_id", sa.Uuid(), sa.ForeignKey("mes_execution_operation.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("mat_location.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uom_id", sa.Uuid(), sa.ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("stock_movement_id", sa.Uuid(), sa.ForeignKey("mat_movement.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("evidence_reference", sa.String(128), nullable=False),
        sa.Column("reversal_of_id", sa.Uuid(), sa.ForeignKey("mat_consumption.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reason_code", sa.String(80), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('CONSUME', 'REVERSE')", name="ck_mat_consumption_kind"),
        sa.CheckConstraint("quantity > 0", name="ck_mat_consumption_positive"),
        sa.CheckConstraint(
            "(kind = 'CONSUME' AND reversal_of_id IS NULL AND reason_code IS NULL) OR "
            "(kind = 'REVERSE' AND reversal_of_id IS NOT NULL AND reason_code IS NOT NULL)",
            name="ck_mat_consumption_reversal_shape",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_mat_consumption_idempotency"),
        sa.UniqueConstraint("stock_movement_id", name="uq_mat_consumption_stock_movement"),
        sa.UniqueConstraint("reversal_of_id", name="uq_mat_consumption_reversal_once"),
    )
    op.create_index("ix_mat_consumption_operation", "mat_consumption", ["execution_operation_id", "created_at"])
    op.create_index("ix_mat_consumption_article", "mat_consumption", ["article_id", "created_at"])
    op.execute("""
        CREATE FUNCTION mop_material_consumption_reject_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'mat_consumption is append-only';
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_mat_consumption_append_only
        BEFORE UPDATE OR DELETE ON mat_consumption FOR EACH ROW
        EXECUTE FUNCTION mop_material_consumption_reject_mutation()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_mat_consumption_append_only ON mat_consumption")
    op.execute("DROP FUNCTION IF EXISTS mop_material_consumption_reject_mutation()")
    op.drop_index("ix_mat_consumption_article", table_name="mat_consumption")
    op.drop_index("ix_mat_consumption_operation", table_name="mat_consumption")
    op.drop_table("mat_consumption")
