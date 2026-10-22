"""campaigns and donations system with ai-assisted review

Revision ID: 0007_campaigns_and_donations
Revises: a1b2c3d4e5f8
Create Date: 2026-10-16 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_campaigns_donations"
down_revision: str | None = "a1b2c3d4e5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Campaigns table
    op.create_table('campaigns',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('ngo_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('mission', sa.String(length=500), nullable=False),
    sa.Column('beneficiary_count', sa.Integer(), nullable=True),
    sa.Column('beneficiary_description', sa.Text(), nullable=False),
    sa.Column('impact_statement', sa.Text(), nullable=False),
    sa.Column('budget_total', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
    sa.Column('budget_breakdown', sa.JSON(), nullable=True),
    sa.Column('duration_months', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='DRAFT', nullable=False),
    sa.Column('hero_image_url', sa.String(length=500), nullable=True),
    sa.Column('images', sa.JSON(), server_default='[]', nullable=False),
    sa.Column('view_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('donation_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('amount_raised', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_ai_reviewed', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('ai_review_summary', sa.Text(), nullable=True),
    sa.Column('ai_flags', sa.JSON(), server_default='[]', nullable=False),
    sa.Column('verification_status', sa.String(length=30), server_default='PENDING', nullable=False),
    sa.Column('verified_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('admin_notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_update_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ngo_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['verified_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaigns_ngo_id'), 'campaigns', ['ngo_id'], unique=False)
    op.create_index(op.f('ix_campaigns_status'), 'campaigns', ['status'], unique=False)
    op.create_index(op.f('ix_campaigns_verification_status'), 'campaigns', ['verification_status'], unique=False)

    # Campaign milestones
    op.create_table('campaign_milestones',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('sequence_num', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('target_amount', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='PENDING', nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('evidence_url', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id', 'sequence_num')
    )
    op.create_index(op.f('ix_campaign_milestones_campaign_id'), 'campaign_milestones', ['campaign_id'], unique=False)

    # Donation types
    op.create_table('donation_types',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('quantity_unit', sa.String(length=50), nullable=True),
    sa.Column('value_in_rupees', sa.Integer(), nullable=False),
    sa.Column('is_available', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_donation_types_campaign_id'), 'donation_types', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_donation_types_type'), 'donation_types', ['type'], unique=False)

    # Campaign donations (append-only)
    op.create_table('campaign_donations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('donation_type_id', sa.String(length=36), nullable=False),
    sa.Column('donor_name', sa.String(length=200), nullable=False),
    sa.Column('donor_email', sa.String(length=200), nullable=False),
    sa.Column('donor_user_id', sa.String(length=36), nullable=True),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('is_anonymous', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('status', sa.String(length=30), server_default='PENDING', nullable=False),
    sa.Column('payment_gateway_ref', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['donation_type_id'], ['donation_types.id'], ),
    sa.ForeignKeyConstraint(['donor_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaign_donations_campaign_id'), 'campaign_donations', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_campaign_donations_donor_user_id'), 'campaign_donations', ['donor_user_id'], unique=False)
    op.create_index(op.f('ix_campaign_donations_created_at'), 'campaign_donations', ['created_at'], unique=False)

    # Campaign reviews (AI + Admin)
    op.create_table('campaign_reviews',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('ai_review_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ai_model', sa.String(length=100), nullable=True),
    sa.Column('ai_analysis', sa.JSON(), nullable=True),
    sa.Column('ai_flags', sa.JSON(), server_default='[]', nullable=False),
    sa.Column('ai_recommendation', sa.String(length=30), nullable=True),
    sa.Column('trustworthiness_score', sa.Integer(), nullable=True),
    sa.Column('admin_user_id', sa.String(length=36), nullable=True),
    sa.Column('admin_review_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('admin_decision', sa.String(length=30), nullable=True),
    sa.Column('admin_notes', sa.Text(), nullable=True),
    sa.Column('admin_changes_requested', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id')
    )
    op.create_index(op.f('ix_campaign_reviews_campaign_id'), 'campaign_reviews', ['campaign_id'], unique=True)
    op.create_index(op.f('ix_campaign_reviews_admin_decision'), 'campaign_reviews', ['admin_decision'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_campaign_reviews_admin_decision'), table_name='campaign_reviews')
    op.drop_index(op.f('ix_campaign_reviews_campaign_id'), table_name='campaign_reviews')
    op.drop_table('campaign_reviews')
    op.drop_index(op.f('ix_campaign_donations_created_at'), table_name='campaign_donations')
    op.drop_index(op.f('ix_campaign_donations_donor_user_id'), table_name='campaign_donations')
    op.drop_index(op.f('ix_campaign_donations_campaign_id'), table_name='campaign_donations')
    op.drop_table('campaign_donations')
    op.drop_index(op.f('ix_donation_types_type'), table_name='donation_types')
    op.drop_index(op.f('ix_donation_types_campaign_id'), table_name='donation_types')
    op.drop_table('donation_types')
    op.drop_index(op.f('ix_campaign_milestones_campaign_id'), table_name='campaign_milestones')
    op.drop_table('campaign_milestones')
    op.drop_index(op.f('ix_campaigns_verification_status'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_status'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_ngo_id'), table_name='campaigns')
    op.drop_table('campaigns')
