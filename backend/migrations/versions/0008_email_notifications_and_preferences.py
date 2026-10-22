"""email notifications, queue, and user preferences for phase 3

Revision ID: 0008_email_notifications
Revises: 0007_campaigns_donations
Create Date: 2026-10-16 15:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_email_notifications"
down_revision: str | None = "0007_campaigns_donations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Email queue table - stores emails to be sent
    op.create_table('email_queue',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_user_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('html_body', sa.Text(), nullable=False),
        sa.Column('text_body', sa.Text(), nullable=True),
        sa.Column('template_name', sa.String(length=100), nullable=False),
        sa.Column('template_data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_queue_status'), 'email_queue', ['status'], unique=False)
    op.create_index(op.f('ix_email_queue_event_type'), 'email_queue', ['event_type'], unique=False)
    op.create_index(op.f('ix_email_queue_recipient_user_id'), 'email_queue', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_email_queue_created_at'), 'email_queue', ['created_at'], unique=False)

    # Notification preferences table
    op.create_table('notification_preferences',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('donation_received', sa.String(length=20), server_default='INSTANT', nullable=False),
        sa.Column('milestone_reached', sa.String(length=20), server_default='INSTANT', nullable=False),
        sa.Column('campaign_published', sa.String(length=20), server_default='INSTANT', nullable=False),
        sa.Column('ngo_verified', sa.String(length=20), server_default='INSTANT', nullable=False),
        sa.Column('donor_digest', sa.String(length=20), server_default='WEEKLY', nullable=False),
        sa.Column('marketing_emails', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('unsubscribe_token', sa.String(length=100), nullable=True),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_notification_preferences_user_id')
    )
    op.create_index(op.f('ix_notification_preferences_user_id'), 'notification_preferences', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_preferences_unsubscribe_token'), 'notification_preferences', ['unsubscribe_token'], unique=False)

    # Email templates table
    op.create_table('email_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('subject_template', sa.String(length=255), nullable=False),
        sa.Column('html_template', sa.Text(), nullable=False),
        sa.Column('text_template', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'version', name='uq_email_templates_name_version')
    )
    op.create_index(op.f('ix_email_templates_event_type'), 'email_templates', ['event_type'], unique=False)
    op.create_index(op.f('ix_email_templates_active'), 'email_templates', ['active'], unique=False)

    # Sent emails audit table (append-only)
    op.create_table('sent_emails',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email_queue_id', sa.String(length=36), nullable=True),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_user_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('opened', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('clicked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('bounced', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('delivery_provider', sa.String(length=50), nullable=True),
        sa.Column('external_message_id', sa.String(length=255), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bounced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sent_emails_recipient_user_id'), 'sent_emails', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_sent_emails_event_type'), 'sent_emails', ['event_type'], unique=False)
    op.create_index(op.f('ix_sent_emails_sent_at'), 'sent_emails', ['sent_at'], unique=False)

    # Add email_notification column to donations table (tracks if notification was sent)
    op.add_column('donations', sa.Column('email_notification_sent', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('donations', sa.Column('email_notification_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('donations', 'email_notification_sent_at')
    op.drop_column('donations', 'email_notification_sent')

    op.drop_index(op.f('ix_sent_emails_sent_at'), table_name='sent_emails')
    op.drop_index(op.f('ix_sent_emails_event_type'), table_name='sent_emails')
    op.drop_index(op.f('ix_sent_emails_recipient_user_id'), table_name='sent_emails')
    op.drop_table('sent_emails')

    op.drop_index(op.f('ix_email_templates_active'), table_name='email_templates')
    op.drop_index(op.f('ix_email_templates_event_type'), table_name='email_templates')
    op.drop_table('email_templates')

    op.drop_index(op.f('ix_notification_preferences_unsubscribe_token'), table_name='notification_preferences')
    op.drop_index(op.f('ix_notification_preferences_user_id'), table_name='notification_preferences')
    op.drop_table('notification_preferences')

    op.drop_index(op.f('ix_email_queue_created_at'), table_name='email_queue')
    op.drop_index(op.f('ix_email_queue_recipient_user_id'), table_name='email_queue')
    op.drop_index(op.f('ix_email_queue_event_type'), table_name='email_queue')
    op.drop_index(op.f('ix_email_queue_status'), table_name='email_queue')
    op.drop_table('email_queue')
