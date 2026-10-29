"""G2.6 manufacturing calendars and effectivity.

Revision ID: 0011_g2_6
Revises: 0010_g2_5
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_g2_6"
down_revision = "0010_g2_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "md_manufacturing_calendar",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("plant_id", sa.Uuid(), nullable=True),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("work_center_id", sa.Uuid(), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_no > 0",
            name="ck_md_manufacturing_calendar_revision_positive",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_manufacturing_calendar_status",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_md_manufacturing_calendar_effectivity",
        ),
        sa.CheckConstraint(
            "("
            "CASE WHEN plant_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN area_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN work_center_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN resource_id IS NOT NULL THEN 1 ELSE 0 END"
            ") = 1",
            name="ck_md_manufacturing_calendar_one_target",
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["core_plant.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["area_id"], ["core_area.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["work_center_id"],
            ["core_work_center.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["core_resource.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "code",
            "revision_no",
            name="uq_md_manufacturing_calendar_code_revision",
        ),
    )

    op.create_table(
        "md_calendar_weekly_window",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("calendar_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("spans_midnight", sa.Boolean(), nullable=False),
        sa.Column(
            "capacity_factor",
            sa.Numeric(precision=12, scale=8),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_md_calendar_weekly_window_weekday",
        ),
        sa.CheckConstraint(
            "start_minute >= 0 AND start_minute <= 1439",
            name="ck_md_calendar_weekly_window_start",
        ),
        sa.CheckConstraint(
            "end_minute >= 1 AND end_minute <= 1440",
            name="ck_md_calendar_weekly_window_end",
        ),
        sa.CheckConstraint(
            "(NOT spans_midnight AND end_minute > start_minute) OR "
            "(spans_midnight AND end_minute < start_minute)",
            name="ck_md_calendar_weekly_window_shape",
        ),
        sa.CheckConstraint(
            "capacity_factor > 0",
            name="ck_md_calendar_weekly_window_capacity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            ["md_manufacturing_calendar.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "calendar_id",
            "weekday",
            "start_minute",
            "end_minute",
            "spans_midnight",
            name="uq_md_calendar_weekly_window_exact",
        ),
    )
    op.create_index(
        "ix_md_calendar_weekly_window_calendar_id",
        "md_calendar_weekly_window",
        ["calendar_id"],
    )

    op.create_table(
        "md_calendar_exception",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("calendar_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("exception_kind", sa.String(length=30), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=True),
        sa.Column("end_minute", sa.Integer(), nullable=True),
        sa.Column(
            "capacity_factor",
            sa.Numeric(precision=12, scale=8),
            nullable=True,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "exception_kind IN ('CLOSED', 'AVAILABLE_OVERRIDE')",
            name="ck_md_calendar_exception_kind",
        ),
        sa.CheckConstraint(
            "(start_minute IS NULL AND end_minute IS NULL) OR "
            "(start_minute IS NOT NULL AND end_minute IS NOT NULL)",
            name="ck_md_calendar_exception_minute_pair",
        ),
        sa.CheckConstraint(
            "start_minute IS NULL OR "
            "(start_minute >= 0 AND start_minute <= 1439)",
            name="ck_md_calendar_exception_start",
        ),
        sa.CheckConstraint(
            "end_minute IS NULL OR "
            "(end_minute >= 1 AND end_minute <= 1440)",
            name="ck_md_calendar_exception_end",
        ),
        sa.CheckConstraint(
            "start_minute IS NULL OR end_minute > start_minute",
            name="ck_md_calendar_exception_shape",
        ),
        sa.CheckConstraint(
            "(exception_kind = 'CLOSED' AND capacity_factor IS NULL) OR "
            "(exception_kind = 'AVAILABLE_OVERRIDE' AND "
            "start_minute IS NOT NULL AND capacity_factor > 0)",
            name="ck_md_calendar_exception_semantics",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            ["md_manufacturing_calendar.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_md_calendar_exception_calendar_id",
        "md_calendar_exception",
        ["calendar_id"],
    )
    op.create_index(
        "ix_md_calendar_exception_local_date",
        "md_calendar_exception",
        ["local_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_md_calendar_exception_local_date",
        table_name="md_calendar_exception",
    )
    op.drop_index(
        "ix_md_calendar_exception_calendar_id",
        table_name="md_calendar_exception",
    )
    op.drop_table("md_calendar_exception")
    op.drop_index(
        "ix_md_calendar_weekly_window_calendar_id",
        table_name="md_calendar_weekly_window",
    )
    op.drop_table("md_calendar_weekly_window")
    op.drop_table("md_manufacturing_calendar")
