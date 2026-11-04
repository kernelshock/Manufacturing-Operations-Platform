"""G6.5 immutable material reservations and releases.

Revision ID: 0032_g6_5
Revises: 0031_g6_4
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_g6_5"
down_revision = "0031_g6_4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mat_reservation_event",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("demand_production_plan.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("taquilla_id", sa.Uuid(), sa.ForeignKey("demand_taquilla.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("md_article.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("mat_location.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uom_id", sa.Uuid(), sa.ForeignKey("md_uom.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("signed_quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("bom_effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("source_reference", sa.String(128), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=True),
        sa.Column("release_of_id", sa.Uuid(), sa.ForeignKey("mat_reservation_event.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('HOLD', 'RELEASE')", name="ck_mat_res_kind"),
        sa.CheckConstraint("quantity > 0", name="ck_mat_res_positive"),
        sa.CheckConstraint(
            "(kind = 'HOLD' AND release_of_id IS NULL AND reason_code IS NULL) OR "
            "(kind = 'RELEASE' AND release_of_id IS NOT NULL AND reason_code IS NOT NULL)",
            name="ck_mat_res_shape"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_mat_res_idempotency"),
    )
    op.create_index("ix_mat_res_article_location", "mat_reservation_event", ["article_id", "location_id"])
    op.create_index("ix_mat_res_taquilla_article", "mat_reservation_event", ["taquilla_id", "article_id"])
    op.execute("""
        CREATE FUNCTION mop_material_reservation_reject_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'mat_reservation_event is append-only';
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_mat_reservation_append_only
        BEFORE UPDATE OR DELETE ON mat_reservation_event FOR EACH ROW
        EXECUTE FUNCTION mop_material_reservation_reject_mutation()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_mat_reservation_append_only ON mat_reservation_event")
    op.execute("DROP FUNCTION IF EXISTS mop_material_reservation_reject_mutation()")
    op.drop_index("ix_mat_res_taquilla_article", table_name="mat_reservation_event")
    op.drop_index("ix_mat_res_article_location", table_name="mat_reservation_event")
    op.drop_table("mat_reservation_event")
