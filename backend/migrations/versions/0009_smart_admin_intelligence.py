"""Add smart AI-powered admin intelligence features

Revision ID: 0009_smart_admin_intelligence
Revises: 0008_email_notifications
Create Date: 2026-10-16 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_smart_admin_intelligence"
down_revision: str | None = "0008_email_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Risk scores table - AI-generated risk scores for NGOs and donors
    op.create_table('risk_scores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('score_type', sa.String(length=20), nullable=False),
        sa.Column('score_value', sa.Integer(), nullable=False),
        sa.Column('factors', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.String(length=20), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_risk_scores_org_id'), 'risk_scores', ['org_id'], unique=False)
    op.create_index(op.f('ix_risk_scores_computed_at'), 'risk_scores', ['computed_at'], unique=False)

    # Anomaly flags table - Real-time anomaly detection
    op.create_table('anomaly_flags',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('flag_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('acknowledged_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['acknowledged_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_anomaly_flags_org_id'), 'anomaly_flags', ['org_id'], unique=False)
    op.create_index(op.f('ix_anomaly_flags_created_at'), 'anomaly_flags', ['created_at'], unique=False)

    # Smart alerts table - Proactive admin alerts
    op.create_table('smart_alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('subject_org_id', sa.String(length=36), nullable=True),
        sa.Column('subject_project_id', sa.String(length=36), nullable=True),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('recommended_action', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_by_user_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['subject_org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dismissed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_smart_alerts_subject_org_id'), 'smart_alerts', ['subject_org_id'], unique=False)
    op.create_index(op.f('ix_smart_alerts_subject_project_id'), 'smart_alerts', ['subject_project_id'], unique=False)
    op.create_index(op.f('ix_smart_alerts_created_at'), 'smart_alerts', ['created_at'], unique=False)

    # Churn predictions table - Predictive churn risk
    op.create_table('churn_predictions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('org_type', sa.String(length=20), nullable=False),
        sa.Column('churn_risk_score', sa.Integer(), nullable=False),
        sa.Column('factors', sa.JSON(), nullable=False),
        sa.Column('intervention_suggested', sa.String(length=500), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_churn_predictions_org_id'), 'churn_predictions', ['org_id'], unique=False)
    op.create_index(op.f('ix_churn_predictions_computed_at'), 'churn_predictions', ['computed_at'], unique=False)

    # Campaign predictions table - Campaign success probability
    op.create_table('campaign_predictions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('success_probability', sa.Integer(), nullable=False),
        sa.Column('reasoning', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.String(length=20), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaign_predictions_project_id'), 'campaign_predictions', ['project_id'], unique=False)
    op.create_index(op.f('ix_campaign_predictions_computed_at'), 'campaign_predictions', ['computed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_campaign_predictions_computed_at'), table_name='campaign_predictions')
    op.drop_index(op.f('ix_campaign_predictions_project_id'), table_name='campaign_predictions')
    op.drop_table('campaign_predictions')

    op.drop_index(op.f('ix_churn_predictions_computed_at'), table_name='churn_predictions')
    op.drop_index(op.f('ix_churn_predictions_org_id'), table_name='churn_predictions')
    op.drop_table('churn_predictions')

    op.drop_index(op.f('ix_smart_alerts_created_at'), table_name='smart_alerts')
    op.drop_index(op.f('ix_smart_alerts_subject_project_id'), table_name='smart_alerts')
    op.drop_index(op.f('ix_smart_alerts_subject_org_id'), table_name='smart_alerts')
    op.drop_table('smart_alerts')

    op.drop_index(op.f('ix_anomaly_flags_created_at'), table_name='anomaly_flags')
    op.drop_index(op.f('ix_anomaly_flags_org_id'), table_name='anomaly_flags')
    op.drop_table('anomaly_flags')

    op.drop_index(op.f('ix_risk_scores_computed_at'), table_name='risk_scores')
    op.drop_index(op.f('ix_risk_scores_org_id'), table_name='risk_scores')
    op.drop_table('risk_scores')
