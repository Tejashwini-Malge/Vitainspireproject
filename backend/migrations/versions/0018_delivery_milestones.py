"""Delivery milestones, and notifications that are not tied to a proposal.

Two changes, both needed by the shortlist-to-delivery flow:

1. `notifications.proposal_id` becomes nullable and gains `opportunity_id`. A SHORTLISTED
   notification is raised at the moment a CSR selects an NGO, before any proposal exists,
   so it can only reference the opportunity.

2. `delivery_milestones` records what an NGO committed to deliver after its proposal was
   approved, and lets the funding CSR watch and verify progress. It is keyed on the stable
   `proposals.proposal_id` family value rather than a version row id, so a later revision
   does not orphan the milestones.

Revision ID: 0018_delivery_milestones
Revises: 0017_ngo_geo_points
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0018_delivery_milestones"
down_revision: str | None = "0017_ngo_geo_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("notifications", "proposal_id", existing_type=sa.String(36), nullable=True)
    op.add_column("notifications", sa.Column("opportunity_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_notifications_opportunity_id", "notifications", "opportunities", ["opportunity_id"], ["id"]
    )
    op.create_index("ix_notifications_opportunity_id", "notifications", ["opportunity_id"])

    op.create_table(
        "delivery_milestones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), nullable=False),
        sa.Column("commitment_id", sa.String(36), sa.ForeignKey("commitments.id"), nullable=False),
        sa.Column("ngo_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("sequence_num", sa.Integer, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("amount_minor", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("evidence_url", sa.String(600), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("proposal_id", "sequence_num", name="uq_delivery_milestone_proposal_sequence"),
    )
    op.create_index("ix_delivery_milestones_proposal_id", "delivery_milestones", ["proposal_id"])
    op.create_index("ix_delivery_milestones_commitment_id", "delivery_milestones", ["commitment_id"])
    op.create_index("ix_delivery_milestones_ngo_id", "delivery_milestones", ["ngo_id"])
    op.create_index("ix_delivery_milestones_opportunity_id", "delivery_milestones", ["opportunity_id"])


def downgrade() -> None:
    op.drop_table("delivery_milestones")
    op.drop_index("ix_notifications_opportunity_id", table_name="notifications")
    op.drop_constraint("fk_notifications_opportunity_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "opportunity_id")
    # Rows written after this migration may legitimately have a null proposal_id; drop them
    # rather than fail the downgrade, since they carry no information the old schema can hold.
    op.execute("DELETE FROM notifications WHERE proposal_id IS NULL")
    op.alter_column("notifications", "proposal_id", existing_type=sa.String(36), nullable=False)
