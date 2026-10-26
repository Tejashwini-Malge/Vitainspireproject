"""Receivable schedule and UTR reconciliation (ADM-009, DON-010).

Commitment + FinanceLedger already exist, but FinanceLedger only ever records a single
"COMMITMENT" entry at approval time -- an intent to fund, not a record of money actually
arriving. `receivables` is the CSR's declared payment schedule (tranches against a
confirmed Commitment, mirroring how delivery_milestones is the NGO's declared delivery
schedule); reconciling one against a bank transfer's UTR writes a second, distinct
FinanceLedger entry ("RECEIVED") and is a separate, admin/finance-only action from
declaring the schedule.

This is the first of two planned increments toward the sheet's full funding lifecycle
(the other being fine-grained allocation of reconciled money against specific delivery
milestones, and contract-document generation) -- scoped separately to keep this change
reviewable on its own.

Revision ID: 0022_receivables
Revises: 0021_audit_hash_chain_export
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0022_receivables"
down_revision: str | None = "0021_audit_hash_chain_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receivables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), nullable=False),
        sa.Column("commitment_id", sa.String(36), sa.ForeignKey("commitments.id"), nullable=False),
        sa.Column("ngo_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("sequence_num", sa.Integer, nullable=False),
        sa.Column("amount_minor", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("utr", sa.String(64), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("proposal_id", "sequence_num", name="uq_receivable_proposal_sequence"),
        sa.UniqueConstraint("utr", name="uq_receivable_utr"),
    )
    op.create_index("ix_receivables_proposal_id", "receivables", ["proposal_id"])
    op.create_index("ix_receivables_commitment_id", "receivables", ["commitment_id"])
    op.create_index("ix_receivables_ngo_id", "receivables", ["ngo_id"])
    op.create_index("ix_receivables_opportunity_id", "receivables", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_receivables_opportunity_id", table_name="receivables")
    op.drop_index("ix_receivables_ngo_id", table_name="receivables")
    op.drop_index("ix_receivables_commitment_id", table_name="receivables")
    op.drop_index("ix_receivables_proposal_id", table_name="receivables")
    op.drop_table("receivables")
