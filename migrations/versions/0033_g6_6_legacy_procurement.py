"""G6.6 legacy Prolowin screenshot/manual staged procurement evidence.

Revision ID: 0033_g6_6
Revises: 0032_g6_5
"""
from uuid import NAMESPACE_URL, uuid5
from alembic import op
import sqlalchemy as sa

revision = "0033_g6_6"
down_revision = "0032_g6_5"
branch_labels = None
depends_on = None

ADMIN = "20000000-0000-0000-0000-000000000001"
READ = uuid5(NAMESPACE_URL, "faic-mop/g6/prolowin.procurement.read")
CAPTURE = uuid5(NAMESPACE_URL, "faic-mop/g6/prolowin.procurement.capture")
VERIFY = uuid5(NAMESPACE_URL, "faic-mop/g6/prolowin.procurement.verify")


def upgrade():
    op.create_table(
        "int_proc_capture",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("source_reference", sa.String(150), nullable=False),
        sa.Column("source_sha256", sa.String(64), unique=True),
        sa.Column("image_mime", sa.String(32)),
        sa.Column("image_bytes", sa.LargeBinary()),
        sa.Column("captured_by", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type IN ('MANUAL', 'SCREENSHOT', 'WEEKLY_SNAPSHOT')", name="ck_proc_cap_kind"),
        sa.CheckConstraint("image_bytes IS NULL OR octet_length(image_bytes) <= 4194304", name="ck_proc_cap_image_size"),
    )
    op.create_table(
        "int_proc_evidence_event",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("capture_id", sa.Uuid(), sa.ForeignKey("int_proc_capture.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_event_key", sa.String(180), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("po_number", sa.String(80), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("supplier_code", sa.String(80), nullable=False),
        sa.Column("article_code", sa.String(80), nullable=False),
        sa.Column("uom_code", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(24,8)),
        sa.Column("accepted_quantity", sa.Numeric(24,8)),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_promise_date", sa.DateTime(timezone=True)),
        sa.Column("revised_promise_date", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.Text()),
        sa.Column("continuity_safe", sa.Boolean()),
        sa.Column("source_reference", sa.String(128), nullable=False),
        sa.Column("mapped_supplier_id", sa.Uuid(), sa.ForeignKey("md_supplier.id", ondelete="RESTRICT")),
        sa.Column("mapped_article_id", sa.Uuid(), sa.ForeignKey("md_article.id", ondelete="RESTRICT")),
        sa.Column("mapped_uom_id", sa.Uuid(), sa.ForeignKey("md_uom.id", ondelete="RESTRICT")),
        sa.Column("review_status", sa.String(12), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("entered_by", sa.Uuid(), sa.ForeignKey("iam_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('ORDER', 'RECEIPT', 'RESCHEDULE', 'CLAIM', 'ESCALATION')", name="ck_proc_event_kind"),
        sa.CheckConstraint("review_status IN ('PENDING', 'VERIFIED', 'REJECTED')", name="ck_proc_event_status"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_proc_event_quantity"),
        sa.CheckConstraint("accepted_quantity IS NULL OR (quantity IS NOT NULL AND accepted_quantity >= 0 AND accepted_quantity <= quantity)", name="ck_proc_event_accepted"),
        sa.CheckConstraint(
            "(review_status = 'PENDING' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR "
            "(review_status <> 'PENDING' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_proc_event_review"
        ),
        sa.UniqueConstraint("source_event_key", name="uq_proc_event_source_key"),

    )
    op.create_index("ix_proc_event_order_line", "int_proc_evidence_event", ["po_number", "line_number", "review_status"])
    op.create_index("uq_proc_event_verified_business_key", "int_proc_evidence_event", ["po_number", "line_number", "kind", "source_reference"], unique=True, postgresql_where=sa.text("review_status = 'VERIFIED'"))
    op.execute("""
        CREATE FUNCTION mop_procurement_evidence_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'procurement evidence is append-only';
            END IF;
            IF OLD.review_status <> 'PENDING' OR NEW.review_status = 'PENDING'
               OR NEW.id <> OLD.id OR NEW.capture_id <> OLD.capture_id
               OR NEW.source_event_key <> OLD.source_event_key
               OR NEW.kind <> OLD.kind OR NEW.po_number <> OLD.po_number
               OR NEW.line_number <> OLD.line_number OR NEW.supplier_code <> OLD.supplier_code
               OR NEW.article_code <> OLD.article_code OR NEW.uom_code <> OLD.uom_code
               OR NEW.quantity IS DISTINCT FROM OLD.quantity
               OR NEW.accepted_quantity IS DISTINCT FROM OLD.accepted_quantity
               OR NEW.event_date <> OLD.event_date
               OR NEW.original_promise_date IS DISTINCT FROM OLD.original_promise_date
               OR NEW.revised_promise_date IS DISTINCT FROM OLD.revised_promise_date
               OR NEW.reason IS DISTINCT FROM OLD.reason
               OR NEW.continuity_safe IS DISTINCT FROM OLD.continuity_safe
               OR NEW.source_reference <> OLD.source_reference
               OR NEW.entered_by <> OLD.entered_by
               OR NEW.entered_at <> OLD.entered_at
            THEN
                RAISE EXCEPTION 'procurement evidence payload is immutable';
            END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_procurement_event_review_only
        BEFORE UPDATE OR DELETE ON int_proc_evidence_event
        FOR EACH ROW EXECUTE FUNCTION mop_procurement_evidence_guard()
    """)
    op.execute("""
        CREATE FUNCTION mop_procurement_capture_reject_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'procurement capture is immutable'; END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_procurement_capture_append_only
        BEFORE UPDATE OR DELETE ON int_proc_capture
        FOR EACH ROW EXECUTE FUNCTION mop_procurement_capture_reject_mutation()
    """)
    perms = sa.table("iam_permission", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("description", sa.String()))
    op.bulk_insert(perms, [
        {"id": READ, "code": "prolowin.procurement.read", "description": "Read staged historical purchasing evidence"},
        {"id": CAPTURE, "code": "prolowin.procurement.capture", "description": "Record manual and screenshot Prolowin evidence"},
        {"id": VERIFY, "code": "prolowin.procurement.verify", "description": "Independently review purchasing evidence"},
    ])
    grants = sa.table("iam_role_permission", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid()))
    op.bulk_insert(grants, [
        {"role_id": ADMIN, "permission_id": READ},
        {"role_id": ADMIN, "permission_id": CAPTURE},
        {"role_id": ADMIN, "permission_id": VERIFY},
    ])


def downgrade():
    for perm in [READ, CAPTURE, VERIFY]:
        op.execute(sa.text("DELETE FROM iam_role_permission WHERE permission_id = :id").bindparams(id=perm))
        op.execute(sa.text("DELETE FROM iam_permission WHERE id = :id").bindparams(id=perm))
    op.execute("DROP TRIGGER IF EXISTS trg_procurement_event_review_only ON int_proc_evidence_event")
    op.execute("DROP FUNCTION IF EXISTS mop_procurement_evidence_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_procurement_capture_append_only ON int_proc_capture")
    op.execute("DROP FUNCTION IF EXISTS mop_procurement_capture_reject_mutation()")
    op.drop_index("uq_proc_event_verified_business_key", table_name="int_proc_evidence_event")
    op.drop_index("ix_proc_event_order_line", table_name="int_proc_evidence_event")
    op.drop_table("int_proc_evidence_event")
    op.drop_table("int_proc_capture")
