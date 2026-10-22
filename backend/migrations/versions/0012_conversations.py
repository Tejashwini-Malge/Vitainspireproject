"""Direct conversations: admin <-> organisation, and donor <-> admin.

Until now the only messaging channel was proposal_messages, which is bound to a
proposal. An NGO had no way to reach platform staff, and a donor had no way to reach
anyone. These two tables add those channels without touching proposal threads, which
keep their own storage because they are keyed by a proposal rather than by participants.

Revision ID: 0012_conversations
Revises: 0011_project_campaign
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012_conversations"
down_revision: str | None = "0011_project_campaign"
branch_labels = None
depends_on = None

_KIND = sa.Enum("ADMIN_ORG", "DONOR_ADMIN", name="conversation_kind")
# create_type=False: the type is created once, explicitly, below. Left to itself the
# column definition would emit a second CREATE TYPE and fail.
_KIND_COL = postgresql.ENUM("ADMIN_ORG", "DONOR_ADMIN", name="conversation_kind", create_type=False)


def upgrade() -> None:
    _KIND.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("kind", _KIND_COL, nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("donor_user_id", sa.String(36), nullable=True),
        sa.Column("opened_by_user_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["donor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["opened_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Access is derived from these two columns, so exactly one must identify the
        # counterparty. Enforced here rather than only in the router: a malformed row
        # would be a conversation nobody could prove they were entitled to read.
        sa.CheckConstraint(
            "(kind = 'ADMIN_ORG' AND org_id IS NOT NULL AND donor_user_id IS NULL) OR "
            "(kind = 'DONOR_ADMIN' AND donor_user_id IS NOT NULL AND org_id IS NULL)",
            name="ck_conversation_counterparty_matches_kind",
        ),
    )
    op.create_index("ix_conversations_kind", "conversations", ["kind"])
    op.create_index("ix_conversations_org_id", "conversations", ["org_id"])
    op.create_index("ix_conversations_donor_user_id", "conversations", ["donor_user_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("sender_user_id", sa.String(36), nullable=False),
        sa.Column("sender_side", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_index("ix_conversation_messages_sender_user_id", "conversation_messages", ["sender_user_id"])
    op.create_index("ix_conversation_messages_created_at", "conversation_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_created_at", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_sender_user_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    for ix in (
        "ix_conversations_created_at",
        "ix_conversations_status",
        "ix_conversations_donor_user_id",
        "ix_conversations_org_id",
        "ix_conversations_kind",
    ):
        op.drop_index(ix, table_name="conversations")
    op.drop_table("conversations")
    _KIND.drop(op.get_bind(), checkfirst=True)
