"""G6.2 warehouses, locations, append-only stock ledger and Materials IAM.

Revision ID: 0030_g6_2
Revises: 0029_g5_5
"""
from uuid import UUID
from alembic import op
import sqlalchemy as sa

revision = "0030_g6_2"
down_revision = "0029_g5_5"
branch_labels = None
depends_on = None

ADMIN = UUID("20000000-0000-0000-0000-000000000001")
READ = UUID("10000000-0000-0000-0000-000000000020")
EDIT = UUID("10000000-0000-0000-0000-000000000021")


def upgrade():
    op.create_table(
        "mat_warehouse",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plant_id"], ["core_plant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plant_id", "code", name="uq_mat_warehouse_plant_code"),
    )
    op.create_index("ix_mat_warehouse_plant_id", "mat_warehouse", ["plant_id"])
    op.create_table(
        "mat_location",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["warehouse_id"], ["mat_warehouse.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warehouse_id", "code", name="uq_mat_location_wh_code"),
    )
    op.create_index("ix_mat_location_warehouse_id", "mat_location", ["warehouse_id"])
    op.create_table(
        "mat_movement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("uom_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("signed_quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("source_system", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("reversal_of_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_by", sa.Uuid(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_mat_movement_quantity_positive"),
        sa.CheckConstraint("(kind = 'OPENING_ZERO' AND signed_quantity = 0 AND quantity = 0) OR (kind <> 'OPENING_ZERO' AND signed_quantity <> 0 AND quantity > 0)", name="ck_mat_movement_signed_nonzero"),
        sa.CheckConstraint(
            "(kind = 'OPENING_ZERO' AND signed_quantity = 0) OR (kind IN ('OPENING', 'RECEIPT', 'ADJUSTMENT_IN') AND signed_quantity > 0) OR "
            "(kind IN ('ISSUE', 'ADJUSTMENT_OUT') AND signed_quantity < 0) OR "
            "(kind = 'REVERSAL' AND reversal_of_id IS NOT NULL)", name="ck_mat_movement_kind_sign"
        ),
        sa.ForeignKeyConstraint(["article_id"], ["md_article.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["mat_location.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uom_id"], ["md_uom.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["mat_movement.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by"], ["iam_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_system", "idempotency_key", name="uq_mat_movement_source_idem"),
        sa.UniqueConstraint("reversal_of_id", name="uq_mat_movement_reversal_once"),
    )
    op.create_index("ix_mat_movement_balance", "mat_movement", ["article_id", "location_id"])
    op.execute("""
        CREATE FUNCTION mop_material_movement_reject_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'mat_movement is append-only';
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_mat_movement_append_only
        BEFORE UPDATE OR DELETE ON mat_movement FOR EACH ROW
        EXECUTE FUNCTION mop_material_movement_reject_mutation()
    """)
    perms = sa.table("iam_permission", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("description", sa.String()))
    op.bulk_insert(perms, [
        {"id": READ, "code": "materials.read", "description": "Read operational material locations, movements and balances"},
        {"id": EDIT, "code": "materials.edit", "description": "Post governed material stock evidence"},
    ])
    grants = sa.table("iam_role_permission", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid()))
    op.bulk_insert(grants, [{"role_id": ADMIN, "permission_id": READ}, {"role_id": ADMIN, "permission_id": EDIT}])


def downgrade():
    op.execute(sa.text("DELETE FROM iam_role_permission WHERE permission_id IN (:read, :edit)").bindparams(read=READ, edit=EDIT))
    op.execute(sa.text("DELETE FROM iam_permission WHERE id IN (:read, :edit)").bindparams(read=READ, edit=EDIT))
    op.execute("DROP TRIGGER IF EXISTS trg_mat_movement_append_only ON mat_movement")
    op.execute("DROP FUNCTION IF EXISTS mop_material_movement_reject_mutation()")
    op.drop_index("ix_mat_movement_balance", table_name="mat_movement")
    op.drop_table("mat_movement")
    op.drop_index("ix_mat_location_warehouse_id", table_name="mat_location")
    op.drop_table("mat_location")
    op.drop_index("ix_mat_warehouse_plant_id", table_name="mat_warehouse")
    op.drop_table("mat_warehouse")
