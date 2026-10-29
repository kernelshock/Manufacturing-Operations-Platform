"""G2.1 article and UoM foundation.

Revision ID: 0006_g2_1
Revises: 0005_g1_8
Create Date: 2026-10-29
"""

from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0006_g2_1"
down_revision = "0005_g1_8"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = UUID("20000000-0000-0000-0000-000000000001")
MASTERDATA_READ_ID = UUID("10000000-0000-0000-0000-000000000014")
MASTERDATA_EDIT_ID = UUID("10000000-0000-0000-0000-000000000015")


def upgrade() -> None:
    op.create_table(
        "md_uom",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("dimension", sa.String(length=30), nullable=False),
        sa.Column("canonical", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "dimension IN ('COUNT', 'LENGTH', 'MASS', 'VOLUME', 'OTHER')",
            name="ck_md_uom_dimension",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_md_uom_code"),
    )

    op.create_table(
        "md_uom_alias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("raw_value", sa.String(length=80), nullable=False),
        sa.Column("uom_id", sa.Uuid(), nullable=True),
        sa.Column("mapping_status", sa.String(length=20), nullable=False),
        sa.Column("conversion_factor", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "mapping_status IN ('MAPPED', 'UNMAPPED', 'REVIEW_REQUIRED')",
            name="ck_md_uom_alias_mapping_status",
        ),
        sa.CheckConstraint(
            "conversion_factor IS NULL OR conversion_factor > 0",
            name="ck_md_uom_alias_conversion_positive",
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uom_id"], ["md_uom.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_system", "raw_value", name="uq_md_uom_alias_source_raw"),
    )

    op.create_table(
        "md_article",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_system", sa.String(length=40), nullable=False),
        sa.Column("external_code", sa.String(length=80), nullable=False),
        sa.Column("canonical_description", sa.Text(), nullable=False),
        sa.Column("article_kind", sa.String(length=30), nullable=False),
        sa.Column("default_uom_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "article_kind IN ('UNKNOWN', 'PURCHASED', 'MANUFACTURED', 'FINISHED_PRODUCT', 'CONSUMABLE', 'SERVICE')",
            name="ck_md_article_kind",
        ),
        sa.ForeignKeyConstraint(["default_uom_id"], ["md_uom.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_system", "external_code", name="uq_md_article_source_code"),
    )

    op.create_table(
        "md_article_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("revision_label", sa.String(length=80), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_batch_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')",
            name="ck_md_article_revision_status",
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["iam_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["article_id"], ["md_article.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "source_fingerprint", name="uq_md_article_revision_fingerprint"),
    )
    op.create_index("ix_md_article_revision_article_id", "md_article_revision", ["article_id"])

    permission_table = sa.table(
        "iam_permission",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        permission_table,
        [
            {
                "id": MASTERDATA_READ_ID,
                "code": "masterdata.read",
                "description": "Read canonical manufacturing master data",
            },
            {
                "id": MASTERDATA_EDIT_ID,
                "code": "masterdata.edit",
                "description": "Create or modify canonical manufacturing master data",
            },
        ],
    )

    role_permission_table = sa.table(
        "iam_role_permission",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        role_permission_table,
        [
            {"role_id": ADMIN_ROLE_ID, "permission_id": MASTERDATA_READ_ID},
            {"role_id": ADMIN_ROLE_ID, "permission_id": MASTERDATA_EDIT_ID},
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM iam_role_permission WHERE role_id = :role_id AND permission_id IN (:read_id, :edit_id)"
        ).bindparams(role_id=ADMIN_ROLE_ID, read_id=MASTERDATA_READ_ID, edit_id=MASTERDATA_EDIT_ID)
    )
    op.execute(
        sa.text("DELETE FROM iam_permission WHERE id IN (:read_id, :edit_id)").bindparams(
            read_id=MASTERDATA_READ_ID, edit_id=MASTERDATA_EDIT_ID
        )
    )
    op.drop_index("ix_md_article_revision_article_id", table_name="md_article_revision")
    op.drop_table("md_article_revision")
    op.drop_table("md_article")
    op.drop_table("md_uom_alias")
    op.drop_table("md_uom")
