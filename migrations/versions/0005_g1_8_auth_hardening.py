"""G1.8 authentication hardening.

Revision ID: 0005_g1_8
Revises: 0004_g1_5
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_g1_8"
down_revision = "0004_g1_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_user",
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "iam_user",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("iam_user", "locked_until")
    op.drop_column("iam_user", "failed_login_count")
