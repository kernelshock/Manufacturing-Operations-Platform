"""G5.3 setup, interruption and deviation evidence.

Revision ID: 0027_g5_3
Revises: 0026_g5_2
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0027_g5_3"
down_revision = "0026_g5_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_mes_execution_operation_status",
        "mes_execution_operation",
        type_="check",
    )
    op.drop_constraint(
        "ck_mes_execution_operation_lifecycle",
        "mes_execution_operation",
        type_="check",
    )

    op.add_column(
        "mes_execution_operation",
        sa.Column("actual_resource_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "mes_execution_operation",
        sa.Column("resource_deviation_reason", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_mes_execution_operation_actual_resource",
        "mes_execution_operation",
        "core_resource",
        ["actual_resource_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_mes_execution_operation_status",
        "mes_execution_operation",
        "status IN ('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED')",
    )
    op.create_check_constraint(
        "ck_mes_execution_operation_lifecycle",
        "mes_execution_operation",
        "(status = 'PENDING' AND actual_start IS NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
        "(status IN ('RUNNING', 'PAUSED') AND actual_start IS NOT NULL AND actual_finish IS NULL AND produced_quantity IS NULL) OR "
        "(status = 'COMPLETED' AND actual_start IS NOT NULL AND actual_finish IS NOT NULL AND produced_quantity IS NOT NULL)",
    )

    op.create_table(
        "mes_execution_setup",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("started_by", sa.Uuid(), nullable=True),
        sa.Column("finished_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_mes_execution_setup_interval",
        ),
        sa.ForeignKeyConstraint(
            ["execution_operation_id"],
            ["mes_execution_operation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["started_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["finished_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_operation_id",
            name="uq_mes_execution_setup_operation",
        ),
    )

    op.create_table(
        "mes_execution_interruption",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_operation_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column("started_by", sa.Uuid(), nullable=True),
        sa.Column("ended_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_mes_execution_interruption_interval",
        ),
        sa.CheckConstraint(
            "length(trim(reason_code)) > 0",
            name="ck_mes_execution_interruption_reason_code",
        ),
        sa.ForeignKeyConstraint(
            ["execution_operation_id"],
            ["mes_execution_operation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["started_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_mes_execution_open_interruption",
        "mes_execution_interruption",
        ["execution_operation_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_mes_execution_open_interruption",
        table_name="mes_execution_interruption",
    )
    op.drop_table("mes_execution_interruption")
    op.drop_table("mes_execution_setup")

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
        "fk_mes_execution_operation_actual_resource",
        "mes_execution_operation",
        type_="foreignkey",
    )
    op.drop_column("mes_execution_operation", "resource_deviation_reason")
    op.drop_column("mes_execution_operation", "actual_resource_id")

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
