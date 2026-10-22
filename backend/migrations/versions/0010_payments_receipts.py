"""Create payments, recurring_donations and tax_receipts; add missing indexes.

These three tables are defined in app/models.py and used by app/routers/payments.py,
but were only ever created by revisions under backend/app/migrations/versions/ --
a directory alembic never reads (alembic.ini sets script_location = migrations).
Every payment and tax-receipt request therefore failed against a missing relation.
This revision brings the live chain in line with the models.

Revision ID: 0010_payments_receipts
Revises: 0009_smart_admin_intelligence
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0010_payments_receipts"
down_revision: str | None = "0009_smart_admin_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("donor_user_id", sa.String(36), nullable=True),
        sa.Column("donor_name", sa.String(200), nullable=False),
        sa.Column("donor_email", sa.String(320), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="INITIATED"),
        sa.Column("payment_method", sa.String(30), nullable=False, server_default="RAZORPAY"),
        sa.Column("gateway_order_id", sa.String(100), nullable=True),
        sa.Column("gateway_payment_id", sa.String(100), nullable=True),
        sa.Column("gateway_signature", sa.String(256), nullable=True),
        sa.Column("receipt_url", sa.String(500), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recurring_plan_id", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["donor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_campaign_id", "payments", ["campaign_id"])
    op.create_index("ix_payments_donor_email", "payments", ["donor_email"])
    op.create_index("ix_payments_donor_user_id", "payments", ["donor_user_id"])
    op.create_index("ix_payments_gateway_order_id", "payments", ["gateway_order_id"])
    op.create_index("ix_payments_gateway_payment_id", "payments", ["gateway_payment_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_created_at", "payments", ["created_at"])

    op.create_table(
        "recurring_donations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("donor_user_id", sa.String(36), nullable=True),
        sa.Column("donor_name", sa.String(200), nullable=False),
        sa.Column("donor_email", sa.String(320), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("gateway_subscription_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("next_billing_date", sa.Date(), nullable=False),
        sa.Column("total_payments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount_paid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["donor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_donations_campaign_id", "recurring_donations", ["campaign_id"])
    op.create_index("ix_recurring_donations_donor_email", "recurring_donations", ["donor_email"])
    op.create_index("ix_recurring_donations_donor_user_id", "recurring_donations", ["donor_user_id"])
    op.create_index(
        "ix_recurring_donations_gateway_subscription_id",
        "recurring_donations",
        ["gateway_subscription_id"],
        unique=True,
    )
    op.create_index("ix_recurring_donations_status", "recurring_donations", ["status"])

    op.create_table(
        "tax_receipts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("payment_id", sa.String(36), nullable=False),
        sa.Column("receipt_number", sa.String(50), nullable=False),
        sa.Column("donor_name", sa.String(200), nullable=False),
        sa.Column("donor_email", sa.String(320), nullable=False),
        sa.Column("donor_pan", sa.String(20), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("ngo_name", sa.String(200), nullable=False),
        sa.Column("ngo_80g_number", sa.String(50), nullable=True),
        sa.Column("ngo_registration_number", sa.String(50), nullable=True),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("pdf_url", sa.String(500), nullable=True),
        sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_tax_receipt_payment_id"),
    )
    op.create_index("ix_tax_receipts_receipt_number", "tax_receipts", ["receipt_number"], unique=True)

    # Indexes declared on the models but absent from the database.
    op.create_index("ix_email_queue_recipient_email", "email_queue", ["recipient_email"])
    op.create_index("ix_fit_scores_ngo_id", "fit_scores", ["ngo_id"])
    op.create_index("ix_shortlists_shortlist_id", "shortlists", ["shortlist_id"])


def downgrade() -> None:
    op.drop_index("ix_shortlists_shortlist_id", table_name="shortlists")
    op.drop_index("ix_fit_scores_ngo_id", table_name="fit_scores")
    op.drop_index("ix_email_queue_recipient_email", table_name="email_queue")

    op.drop_index("ix_tax_receipts_receipt_number", table_name="tax_receipts")
    op.drop_table("tax_receipts")

    for ix in (
        "ix_recurring_donations_status",
        "ix_recurring_donations_gateway_subscription_id",
        "ix_recurring_donations_donor_user_id",
        "ix_recurring_donations_donor_email",
        "ix_recurring_donations_campaign_id",
    ):
        op.drop_index(ix, table_name="recurring_donations")
    op.drop_table("recurring_donations")

    for ix in (
        "ix_payments_created_at",
        "ix_payments_status",
        "ix_payments_gateway_payment_id",
        "ix_payments_gateway_order_id",
        "ix_payments_donor_user_id",
        "ix_payments_donor_email",
        "ix_payments_campaign_id",
    ):
        op.drop_index(ix, table_name="payments")
    op.drop_table("payments")
