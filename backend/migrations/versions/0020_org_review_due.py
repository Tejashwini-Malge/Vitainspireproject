"""Re-verification / review-due workflow for organisations (ADM-004).

A decided organisation (APPROVED or REJECTED) previously could never be re-decided at
all -- the verification endpoint refused a second decision with a 409, and there was no
state representing "this organisation is due for another look" at all.

`review_due_at` is deliberately orthogonal to `verification_status`, not a replacement
state for it: flagging an organisation for re-verification does not revoke whatever
verification_status already grants it. An org stays APPROVED (keeps publishing projects,
appearing in fit scoring, etc.) until an admin actually issues a new decision; the flag
only adds it to a dedicated review queue and lets a new decision supersede the old one.

Revision ID: 0020_org_review_due
Revises: 0019_csr_profiles_and_fcra_flag
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0020_org_review_due"
down_revision: str | None = "0019_csr_profiles_and_fcra_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("review_requested_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("organizations", sa.Column("review_reason", sa.String(1000), nullable=True))
    op.create_index("ix_organizations_review_due_at", "organizations", ["review_due_at"])


def downgrade() -> None:
    op.drop_index("ix_organizations_review_due_at", table_name="organizations")
    op.drop_column("organizations", "review_reason")
    op.drop_column("organizations", "review_requested_by_user_id")
    op.drop_column("organizations", "review_due_at")
