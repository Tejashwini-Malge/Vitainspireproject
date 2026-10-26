"""CSR profiles and FCRA-required flag on opportunities

Two changes the 2026-10-25 acceptance report flagged as missing (DON-001, ADM-005, AI-004):

1. `csr_profiles` gives CSR organizations a place for the donor-facing identity and
   statutory fields the sheet expects (CIN, CSR budget, Schedule VII categories) -- CSR
   organizations previously had no profile at all.

2. `opportunities.fcra_required` is a structured flag an opportunity's requirements_text
   could only describe in free text before. app.ai.fit now reads it as a hard eligibility
   gate (an unregistered NGO cannot be shortlisted for an FCRA-required opportunity),
   mirroring how the existing required-document gate works.

Revision ID: 0019_csr_profiles_and_fcra_flag
Revises: 0018_delivery_milestones
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0019_csr_profiles_and_fcra_flag"
down_revision: str | None = "0018_delivery_milestones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "csr_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, unique=True),
        sa.Column("mission", sa.String(1000), nullable=False, server_default=""),
        sa.Column("about", sa.Text, nullable=True),
        sa.Column("website", sa.String(300), nullable=True),
        sa.Column("cin", sa.String(30), nullable=True),
        sa.Column("csr_budget_minor", sa.Integer, nullable=True),
        sa.Column("schedule_vii_categories", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column(
        "opportunities",
        sa.Column("fcra_required", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("opportunities", "fcra_required")
    op.drop_table("csr_profiles")
