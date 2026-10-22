"""opportunities, matching, proposals, finance

Revision ID: 0004_opportunities_matching_proposals_finance
Revises: 0003_projects_and_donations
Create Date: 2026-10-14 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '0003_projects_and_donations'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Opportunities (RFP)
    op.create_table('opportunities',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('sectors', sa.JSON(), nullable=False, server_default='[]'),
    sa.Column('geographies', sa.JSON(), nullable=False, server_default='[]'),
    sa.Column('budget_min', sa.Integer(), nullable=True),
    sa.Column('budget_max', sa.Integer(), nullable=True),
    sa.Column('deadline', sa.Date(), nullable=False),
    sa.Column('requirements_text', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='DRAFT'),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_opportunities_org_id'), 'opportunities', ['org_id'], unique=False)

    # Eligibility rules (deterministic business logic)
    op.create_table('eligibility_rules',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('rule_type', sa.String(length=50), nullable=False),
    sa.Column('condition_json', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    # Eligibility check results
    op.create_table('eligibility_results',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('opportunity_id', sa.String(length=36), nullable=False),
    sa.Column('ngo_id', sa.String(length=36), nullable=False),
    sa.Column('passed', sa.Boolean(), nullable=False),
    sa.Column('rule_id', sa.String(length=36), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.ForeignKeyConstraint(['ngo_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eligibility_results_opportunity_id'), 'eligibility_results', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_eligibility_results_ngo_id'), 'eligibility_results', ['ngo_id'], unique=False)

    # AI-generated fit scores
    op.create_table('fit_scores',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('opportunity_id', sa.String(length=36), nullable=False),
    sa.Column('ngo_id', sa.String(length=36), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('confidence', sa.String(length=20), nullable=False),
    sa.Column('model_version', sa.String(length=50), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('correlation_id', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.ForeignKeyConstraint(['ngo_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fit_scores_opportunity_id'), 'fit_scores', ['opportunity_id'], unique=False)

    # Shortlist (versioned with revisions)
    op.create_table('shortlists',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('shortlist_id', sa.String(length=36), nullable=False),
    sa.Column('opportunity_id', sa.String(length=36), nullable=False),
    sa.Column('revision_num', sa.Integer(), nullable=False, server_default='1'),
    sa.Column('ngo_ids', sa.JSON(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
    sa.Column('selected_by_user_id', sa.String(length=36), nullable=False),
    sa.Column('selected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.ForeignKeyConstraint(['selected_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('opportunity_id', 'revision_num', name='uq_shortlist_opportunity_revision')
    )
    op.create_index(op.f('ix_shortlists_opportunity_id'), 'shortlists', ['opportunity_id'], unique=False)

    # Proposals (versioned)
    op.create_table('proposals',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('opportunity_id', sa.String(length=36), nullable=False),
    sa.Column('ngo_id', sa.String(length=36), nullable=False),
    sa.Column('version_num', sa.Integer(), nullable=False, server_default='1'),
    sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
    sa.Column('problem_statement', sa.Text(), nullable=False),
    sa.Column('solution', sa.Text(), nullable=False),
    sa.Column('budget_requested', sa.Integer(), nullable=False),
    sa.Column('timeline', sa.String(length=500), nullable=False),
    sa.Column('expected_outcomes', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='DRAFT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.ForeignKeyConstraint(['ngo_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proposal_id', 'version_num', name='uq_proposal_version')
    )
    op.create_index(op.f('ix_proposals_opportunity_id'), 'proposals', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_proposals_ngo_id'), 'proposals', ['ngo_id'], unique=False)
    op.create_index('ix_proposals_current', 'proposals', ['proposal_id', 'is_current'], unique=False)

    # Generic approval state machine
    op.create_table('approval_requests',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('subject_type', sa.String(length=50), nullable=False),
    sa.Column('subject_id', sa.String(length=36), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('requested_by_user_id', sa.String(length=36), nullable=False),
    sa.Column('approver_user_id', sa.String(length=36), nullable=True),
    sa.Column('approver_feedback', sa.Text(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('correlation_id', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_requests_subject_type'), 'approval_requests', ['subject_type', 'subject_id'], unique=False)

    # Commitment (intent to fund)
    op.create_table('commitments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('amount_minor', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_commitments_proposal_id'), 'commitments', ['proposal_id'], unique=True)

    # Finance ledger (append-only)
    op.create_table('finance_ledger',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('opportunity_id', sa.String(length=36), nullable=False),
    sa.Column('ngo_id', sa.String(length=36), nullable=False),
    sa.Column('amount_minor', sa.Integer(), nullable=False),
    sa.Column('transaction_type', sa.String(length=20), nullable=False),
    sa.Column('idempotency_key', sa.String(length=64), nullable=False),
    sa.Column('recorded_by_user_id', sa.String(length=36), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('correlation_id', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.ForeignKeyConstraint(['ngo_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key', name='uq_finance_ledger_idempotency_key')
    )
    op.create_index(op.f('ix_finance_ledger_opportunity_id'), 'finance_ledger', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_finance_ledger_ngo_id'), 'finance_ledger', ['ngo_id'], unique=False)

    # Append-only trigger for finance_ledger
    op.execute(
        "CREATE TRIGGER finance_ledger_append_only BEFORE UPDATE OR DELETE ON finance_ledger "
        "FOR EACH ROW EXECUTE FUNCTION forbid_mutation()"
    )

    # Matching job (for async agent runs)
    op.create_table('matching_jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('opportunity_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='QUEUED'),
    sa.Column('fit_scores_json', sa.JSON(), nullable=True),
    sa.Column('error_log', sa.Text(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('fallback_used', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_matching_jobs_opportunity_id'), 'matching_jobs', ['opportunity_id'], unique=False)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS finance_ledger_append_only ON finance_ledger")
    op.drop_index(op.f('ix_matching_jobs_opportunity_id'), table_name='matching_jobs')
    op.drop_table('matching_jobs')
    op.drop_index(op.f('ix_finance_ledger_ngo_id'), table_name='finance_ledger')
    op.drop_index(op.f('ix_finance_ledger_opportunity_id'), table_name='finance_ledger')
    op.drop_table('finance_ledger')
    op.drop_index(op.f('ix_commitments_proposal_id'), table_name='commitments')
    op.drop_table('commitments')
    op.drop_index(op.f('ix_approval_requests_subject_type'), table_name='approval_requests')
    op.drop_table('approval_requests')
    op.drop_index('ix_proposals_current', table_name='proposals')
    op.drop_index(op.f('ix_proposals_ngo_id'), table_name='proposals')
    op.drop_index(op.f('ix_proposals_opportunity_id'), table_name='proposals')
    op.drop_table('proposals')
    op.drop_index(op.f('ix_shortlists_opportunity_id'), table_name='shortlists')
    op.drop_table('shortlists')
    op.drop_index(op.f('ix_fit_scores_opportunity_id'), table_name='fit_scores')
    op.drop_table('fit_scores')
    op.drop_index(op.f('ix_eligibility_results_ngo_id'), table_name='eligibility_results')
    op.drop_index(op.f('ix_eligibility_results_opportunity_id'), table_name='eligibility_results')
    op.drop_table('eligibility_results')
    op.drop_table('eligibility_rules')
    op.drop_index(op.f('ix_opportunities_org_id'), table_name='opportunities')
    op.drop_table('opportunities')
