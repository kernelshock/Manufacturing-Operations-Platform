"""G5.4 transfer / handoff and WIP traceability.

Revision ID: 0028_g5_4
Revises: 0027_g5_3
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_g5_4"
down_revision = "0027_g5_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mes_execution_handoff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("product_line_id", sa.Uuid(), nullable=False),
        sa.Column("from_execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("to_execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transferred_by", sa.Uuid(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sequence_no > 0", name="ck_mes_execution_handoff_sequence_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_mes_execution_handoff_quantity_positive"),
        sa.CheckConstraint(
            "status IN ('TRANSFERRED', 'RECEIVED')",
            name="ck_mes_execution_handoff_status",
        ),
        sa.CheckConstraint(
            "(status = 'TRANSFERRED' AND received_at IS NULL) OR "
            "(status = 'RECEIVED' AND received_at IS NOT NULL)",
            name="ck_mes_execution_handoff_lifecycle",
        ),
        sa.CheckConstraint(
            "received_at IS NULL OR received_at >= transferred_at",
            name="ck_mes_execution_handoff_interval",
        ),
        sa.ForeignKeyConstraint(["dispatch_id"], ["mes_execution_dispatch.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_line_id"], ["demand_taquilla_product_line.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["from_execution_operation_id"],
            ["mes_execution_operation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_execution_operation_id"],
            ["mes_execution_operation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["transferred_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["received_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_execution_operation_id",
            "to_execution_operation_id",
            "sequence_no",
            name="uq_mes_execution_handoff_edge_sequence",
        ),
    )


def downgrade() -> None:
    op.drop_table("mes_execution_handoff")
