"""G5.5 rework case and alternative execution path.

Revision ID: 0029_g5_5
Revises: 0028_g5_4
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_g5_5"
down_revision = "0028_g5_4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mes_rework_case",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("product_line_id", sa.Uuid(), nullable=False),
        sa.Column("source_execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("return_execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("case_code", sa.String(80), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_mes_rework_case_quantity"),
        sa.CheckConstraint("status IN ('OPEN', 'IN_PROGRESS', 'READY_TO_RETURN', 'RETURNED', 'CANCELLED')", name="ck_mes_rework_case_status"),
        sa.CheckConstraint("(status = 'RETURNED' AND returned_at IS NOT NULL) OR (status <> 'RETURNED' AND returned_at IS NULL)", name="ck_mes_rework_case_return_state"),
        sa.ForeignKeyConstraint(["dispatch_id"], ["mes_execution_dispatch.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_line_id"], ["demand_taquilla_product_line.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_execution_operation_id"], ["mes_execution_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["return_execution_operation_id"], ["mes_execution_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["returned_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dispatch_id", "case_code", name="uq_mes_rework_dispatch_case"),
    )
    op.create_table(
        "mes_rework_step",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("routing_operation_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("operation_code", sa.String(30), nullable=False),
        sa.Column("operation_description", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_finish", sa.DateTime(timezone=True), nullable=True),
        sa.Column("produced_quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("started_by", sa.Uuid(), nullable=True),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("sequence_no > 0", name="ck_mes_rework_step_sequence"),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED')", name="ck_mes_rework_step_status"),
        sa.CheckConstraint(
            "(status = 'PENDING' AND actual_start IS NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
            "(status = 'RUNNING' AND actual_start IS NOT NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
            "(status = 'COMPLETED' AND actual_start IS NOT NULL AND actual_finish IS NOT NULL AND produced_quantity IS NOT NULL)",
            name="ck_mes_rework_step_lifecycle",
        ),
        sa.CheckConstraint("actual_finish IS NULL OR actual_finish >= actual_start", name="ck_mes_rework_step_interval"),
        sa.CheckConstraint("produced_quantity IS NULL OR produced_quantity > 0", name="ck_mes_rework_step_quantity"),
        sa.ForeignKeyConstraint(["case_id"], ["mes_rework_case.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["routing_operation_id"], ["md_routing_operation.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["core_resource.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["started_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["completed_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "sequence_no", name="uq_mes_rework_step_sequence"),
    )


def downgrade() -> None:
    op.drop_table("mes_rework_step")
    op.drop_table("mes_rework_case")
