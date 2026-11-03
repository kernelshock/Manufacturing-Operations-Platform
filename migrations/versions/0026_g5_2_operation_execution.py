"""G5.2 operation start, finish and quantity capture.

Revision ID: 0026_g5_2
Revises: 0025_g5_1
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0026_g5_2"
down_revision = "0025_g5_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_mes_execution_operation_status_g5_1",
        "mes_execution_operation",
        type_="check",
    )

    op.add_column(
        "mes_execution_operation",
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mes_execution_operation",
        sa.Column("actual_finish", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mes_execution_operation",
        sa.Column("produced_quantity", sa.Numeric(24, 8), nullable=True),
    )
    op.add_column(
        "mes_execution_operation",
        sa.Column("started_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "mes_execution_operation",
        sa.Column("completed_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_mes_execution_operation_started_by_iam_user",
        "mes_execution_operation",
        "iam_user",
        ["started_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_mes_execution_operation_completed_by_iam_user",
        "mes_execution_operation",
        "iam_user",
        ["completed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_mes_execution_operation_status",
        "mes_execution_operation",
        "status IN ('PENDING', 'RUNNING', 'COMPLETED')",
    )
    op.create_check_constraint(
        "ck_mes_execution_operation_lifecycle",
        "mes_execution_operation",
        "(status = 'PENDING' AND actual_start IS NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
        "(status = 'RUNNING' AND actual_start IS NOT NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
        "(status = 'COMPLETED' AND actual_start IS NOT NULL AND actual_finish IS NOT NULL AND produced_quantity IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_mes_execution_actual_interval",
        "mes_execution_operation",
        "actual_finish IS NULL OR actual_finish >= actual_start",
    )
    op.create_check_constraint(
        "ck_mes_execution_produced_quantity_positive",
        "mes_execution_operation",
        "produced_quantity IS NULL OR produced_quantity > 0",
    )

    op.create_table(
        "mes_execution_operation_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('START', 'COMPLETE')",
            name="ck_mes_execution_operation_event_type_g5_2",
        ),
        sa.CheckConstraint(
            "(event_type = 'START' AND produced_quantity IS NULL) OR "
            "(event_type = 'COMPLETE' AND produced_quantity IS NOT NULL AND produced_quantity > 0)",
            name="ck_mes_execution_operation_event_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["execution_operation_id"],
            ["mes_execution_operation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["iam_user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_operation_id",
            "event_type",
            name="uq_mes_execution_operation_event_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("mes_execution_operation_event")

    op.drop_constraint(
        "ck_mes_execution_produced_quantity_positive",
        "mes_execution_operation",
        type_="check",
    )
    op.drop_constraint(
        "ck_mes_execution_actual_interval",
        "mes_execution_operation",
        type_="check",
    )
    op.drop_constraint(
        "ck_mes_execution_operation_lifecycle",
        "mes_execution_operation",
        type_="check",
    )
    op.drop_constraint(
        "ck_mes_execution_operation_status",
        "mes_execution_operation",
        type_="check",
    )
    op.drop_constraint(
        "fk_mes_execution_operation_completed_by_iam_user",
        "mes_execution_operation",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_mes_execution_operation_started_by_iam_user",
        "mes_execution_operation",
        type_="foreignkey",
    )
    op.drop_column("mes_execution_operation", "completed_by")
    op.drop_column("mes_execution_operation", "started_by")
    op.drop_column("mes_execution_operation", "produced_quantity")
    op.drop_column("mes_execution_operation", "actual_finish")
    op.drop_column("mes_execution_operation", "actual_start")
    op.create_check_constraint(
        "ck_mes_execution_operation_status_g5_1",
        "mes_execution_operation",
        "status IN ('PENDING')",
    )
