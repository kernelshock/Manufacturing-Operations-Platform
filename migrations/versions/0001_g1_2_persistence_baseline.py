"""G1.2 persistence baseline.

Revision ID: 0001_g1_2
Revises:
Create Date: 2026-10-28
"""

revision = "0001_g1_2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Establish the Alembic baseline; domain tables arrive in later slices."""

    pass


def downgrade() -> None:
    """Remove no domain objects; dropping the Alembic version is tool-managed."""

    pass
