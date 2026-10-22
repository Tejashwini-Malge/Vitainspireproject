"""notifications system for messages and proposal status changes

Revision ID: a1b2c3d4e5f8
Revises: a1b2c3d4e5f7
Create Date: 2026-10-15 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f8"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('notifications',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('recipient_user_id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('notification_type', sa.String(length=50), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('actor_user_id', sa.String(length=36), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_recipient_user_id'), 'notifications', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_notifications_proposal_id'), 'notifications', ['proposal_id'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_proposal_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_user_id'), table_name='notifications')
    op.drop_table('notifications')
