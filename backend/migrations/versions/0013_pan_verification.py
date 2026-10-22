"""PAN verification for individual users

Adds a user-scoped PAN proof upload and its immutable review-decision history,
mirroring the existing org-scoped documents / document_review_decisions pair but
keyed by user_id instead of org_id (individual donors have no organization).

Revision ID: 0013_pan_verification
Revises: 0012_conversations
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0013_pan_verification"
down_revision: str | None = "0012_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_STATUS = postgresql.ENUM("PENDING_REVIEW", "APPROVED", "REJECTED", name="review_status", create_type=False)
_REVIEW_DECISION = postgresql.ENUM("PENDING_REVIEW", "APPROVED", "REJECTED", name="review_decision", create_type=False)


def upgrade() -> None:
    op.create_table(
        "pan_verifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("review_status", _REVIEW_STATUS, nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_pan_verifications_storage_key"),
    )
    op.create_index(op.f("ix_pan_verifications_user_id"), "pan_verifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_pan_verifications_sha256"), "pan_verifications", ["sha256"], unique=False)

    op.create_table(
        "pan_verification_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pan_verification_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=False),
        sa.Column("decision", _REVIEW_DECISION, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("previous_status", _REVIEW_STATUS, nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["pan_verification_id"], ["pan_verifications.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pan_verification_decisions_pan_verification_id"),
        "pan_verification_decisions",
        ["pan_verification_id"],
        unique=False,
    )

    # Append-only enforcement, reusing the forbid_mutation() trigger function created in 0002.
    op.execute(
        "CREATE TRIGGER pan_verification_decisions_append_only BEFORE UPDATE OR DELETE "
        "ON pan_verification_decisions FOR EACH ROW EXECUTE FUNCTION forbid_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pan_verification_decisions_append_only ON pan_verification_decisions")
    op.drop_index(
        op.f("ix_pan_verification_decisions_pan_verification_id"), table_name="pan_verification_decisions"
    )
    op.drop_table("pan_verification_decisions")
    op.drop_index(op.f("ix_pan_verifications_sha256"), table_name="pan_verifications")
    op.drop_index(op.f("ix_pan_verifications_user_id"), table_name="pan_verifications")
    op.drop_table("pan_verifications")
