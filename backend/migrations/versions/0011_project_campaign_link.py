"""Link a project to the campaign that funds it.

Project and Campaign grew up as two parallel fundable objects. Campaign already
carries budget, budget breakdown, beneficiaries, impact statement, duration and
milestones; Project carries only title/summary/description. Rather than duplicate
those fields onto Project, a project now points at the campaign that funds it, so
the richer detail has exactly one home.

Nullable: a project may legitimately exist with no campaign yet.

Revision ID: 0011_project_campaign
Revises: 0010_payments_receipts
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0011_project_campaign"
down_revision: str | None = "0010_payments_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("campaign_id", sa.String(36), nullable=True))
    op.create_index("ix_projects_campaign_id", "projects", ["campaign_id"])
    op.create_foreign_key(
        "fk_projects_campaign_id", "projects", "campaigns", ["campaign_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_campaign_id", "projects", type_="foreignkey")
    op.drop_index("ix_projects_campaign_id", table_name="projects")
    op.drop_column("projects", "campaign_id")
