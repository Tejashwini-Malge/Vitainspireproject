"""proposal messaging and escalation system

Revision ID: 0005_proposal_messaging
Revises: 0004_opportunities_matching_proposals_finance
Create Date: 2026-10-15 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f7"
down_revision: str | None = ("0003", "a1b2c3d4e5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('proposal_messages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('sender_id', sa.String(length=36), nullable=False),
    sa.Column('sender_type', sa.String(length=10), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proposal_messages_proposal_id'), 'proposal_messages', ['proposal_id'], unique=False)
    op.create_index(op.f('ix_proposal_messages_sender_id'), 'proposal_messages', ['sender_id'], unique=False)
    op.create_index(op.f('ix_proposal_messages_created_at'), 'proposal_messages', ['created_at'], unique=False)

    op.create_table('proposal_timelines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False, unique=True),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('reply_deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('waiting_on', sa.String(length=10), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proposal_timelines_proposal_id'), 'proposal_timelines', ['proposal_id'], unique=True)

    op.create_table('proposal_escalations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('reason', sa.String(length=100), nullable=False),
    sa.Column('escalated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('admin_notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proposal_escalations_proposal_id'), 'proposal_escalations', ['proposal_id'], unique=False)
    op.create_index(op.f('ix_proposal_escalations_status'), 'proposal_escalations', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proposal_escalations_status'), table_name='proposal_escalations')
    op.drop_index(op.f('ix_proposal_escalations_proposal_id'), table_name='proposal_escalations')
    op.drop_table('proposal_escalations')
    op.drop_index(op.f('ix_proposal_timelines_proposal_id'), table_name='proposal_timelines')
    op.drop_table('proposal_timelines')
    op.drop_index(op.f('ix_proposal_messages_created_at'), table_name='proposal_messages')
    op.drop_index(op.f('ix_proposal_messages_sender_id'), table_name='proposal_messages')
    op.drop_index(op.f('ix_proposal_messages_proposal_id'), table_name='proposal_messages')
    op.drop_table('proposal_messages')
