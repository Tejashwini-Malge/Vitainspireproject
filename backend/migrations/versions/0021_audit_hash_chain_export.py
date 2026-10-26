"""Audit export and tamper-evidence hash chain (ADM-017, NEG-013).

audit_events was already append-only (trigger-protected, see 0002), but there was no way
to export the trail and no way to detect whether a row had been edited, deleted, or
reinserted out of order -- short of trusting the trigger never gets bypassed (e.g. by a
superuser connection). Adding a per-row hash chain means that trust is now checkable: a
verifier recomputes each row's hash from its stored content plus the previous row's hash
and compares it to what was stored.

`seq` is a DB-assigned identity, separate from `occurred_at`, because wall-clock ordering
is not reliable under concurrent writes; the chain follows insertion order instead.

Existing rows (there are none on a fresh install, but in case this runs against a
populated database) get `seq` assigned automatically by the identity column, and null
`row_hash`/`prev_hash` -- they predate the chain and are simply excluded from
verification rather than reported as corrupt.

Revision ID: 0021_audit_hash_chain_export
Revises: 0020_org_review_due
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0021_audit_hash_chain_export"
down_revision: str | None = "0020_org_review_due"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False))
    op.add_column("audit_events", sa.Column("row_hash", sa.String(64), nullable=True))
    op.add_column("audit_events", sa.Column("prev_hash", sa.String(64), nullable=True))
    op.create_index("ix_audit_events_seq", "audit_events", ["seq"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_seq", table_name="audit_events")
    op.drop_column("audit_events", "prev_hash")
    op.drop_column("audit_events", "row_hash")
    op.drop_column("audit_events", "seq")
