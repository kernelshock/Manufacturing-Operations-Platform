"""Link receipt lots to independently verified purchase order evidence."""

from alembic import op
import sqlalchemy as sa

revision = "0039_g7_6"
down_revision = "0038_g7_6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mat_receipt_lot", sa.Column("purchase_order_evidence_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_mat_receipt_lot_purchase_evidence", "mat_receipt_lot", "int_proc_evidence_event",
        ["purchase_order_evidence_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_mat_receipt_lot_purchase_evidence", "mat_receipt_lot", ["purchase_order_evidence_id"],
    )


def downgrade():
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM mat_receipt_lot WHERE purchase_order_evidence_id IS NOT NULL)"
    )):
        raise RuntimeError("receipt purchase evidence must be preserved before downgrade")
    op.drop_index("ix_mat_receipt_lot_purchase_evidence", table_name="mat_receipt_lot")
    op.drop_constraint("fk_mat_receipt_lot_purchase_evidence", "mat_receipt_lot", type_="foreignkey")
    op.drop_column("mat_receipt_lot", "purchase_order_evidence_id")
