"""Org-to-org and donor-to-NGO conversations

General-purpose direct messaging, independent of any proposal: an NGO and a CSR can
now open a conversation with each other, and an individual donor can open one with an
NGO. Adds ConversationKind.ORG_ORG / DONOR_NGO and a counterparty_org_id column for
the second organisation in an ORG_ORG thread.

The kind column moves off the native Postgres enum (which only had the original two
values) onto a plain string column, so future kinds don't need another ALTER TYPE. The
existing check constraint tying the populated columns to kind is dropped and replaced
with one that covers all four kinds.

Revision ID: 0016_org_to_org_conversations
Revises: 0015_project_admin_review
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0016_org_to_org_conversations"
down_revision: str | None = "0015_project_admin_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CHECK = (
    "(kind = 'ADMIN_ORG' AND org_id IS NOT NULL AND donor_user_id IS NULL) OR "
    "(kind = 'DONOR_ADMIN' AND donor_user_id IS NOT NULL AND org_id IS NULL)"
)
_NEW_CHECK = (
    "(kind = 'ADMIN_ORG' AND org_id IS NOT NULL AND donor_user_id IS NULL AND counterparty_org_id IS NULL) OR "
    "(kind = 'DONOR_ADMIN' AND donor_user_id IS NOT NULL AND org_id IS NULL AND counterparty_org_id IS NULL) OR "
    "(kind = 'ORG_ORG' AND org_id IS NOT NULL AND counterparty_org_id IS NOT NULL AND donor_user_id IS NULL) OR "
    "(kind = 'DONOR_NGO' AND org_id IS NOT NULL AND donor_user_id IS NOT NULL AND counterparty_org_id IS NULL)"
)


def upgrade() -> None:
    op.add_column("conversations", sa.Column("counterparty_org_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_conversations_counterparty_org_id", "conversations", "organizations", ["counterparty_org_id"], ["id"]
    )
    op.create_index(
        op.f("ix_conversations_counterparty_org_id"), "conversations", ["counterparty_org_id"], unique=False
    )

    # The old constraint references the native enum type by comparison; it must go
    # before the column type can change.
    op.drop_constraint("ck_conversation_counterparty_matches_kind", "conversations", type_="check")

    op.alter_column(
        "conversations",
        "kind",
        type_=sa.String(length=20),
        existing_type=postgresql.ENUM("ADMIN_ORG", "DONOR_ADMIN", name="conversation_kind"),
        postgresql_using="kind::text",
    )
    op.execute("DROP TYPE IF EXISTS conversation_kind")

    op.create_check_constraint("ck_conversation_counterparty_matches_kind", "conversations", _NEW_CHECK)


def downgrade() -> None:
    # Irreversible if any row holds a kind the original enum never had (ORG_ORG,
    # DONOR_NGO) or a non-null counterparty_org_id; those rows would fail the cast below.
    op.drop_constraint("ck_conversation_counterparty_matches_kind", "conversations", type_="check")

    op.execute("CREATE TYPE conversation_kind AS ENUM ('ADMIN_ORG', 'DONOR_ADMIN')")
    op.alter_column(
        "conversations",
        "kind",
        type_=postgresql.ENUM("ADMIN_ORG", "DONOR_ADMIN", name="conversation_kind", create_type=False),
        existing_type=sa.String(length=20),
        postgresql_using="kind::conversation_kind",
    )

    op.create_check_constraint("ck_conversation_counterparty_matches_kind", "conversations", _OLD_CHECK)

    op.drop_index(op.f("ix_conversations_counterparty_org_id"), table_name="conversations")
    op.drop_constraint("fk_conversations_counterparty_org_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "counterparty_org_id")
