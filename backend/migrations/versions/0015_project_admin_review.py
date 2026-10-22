"""Project admin review

A project can no longer go PUBLISHED directly from NGO action: it must be submitted
for review (PENDING_REVIEW) and explicitly approved by an admin, mirroring the
Campaign review pattern. The status column moves off the native Postgres enum (which
only had DRAFT/PUBLISHED) onto a plain string column, so new states don't require a
further ALTER TYPE.

Revision ID: 0015_project_admin_review
Revises: 0014_ngo_registration_numbers
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0015_project_admin_review"
down_revision: str | None = "0014_ngo_registration_numbers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "status",
        type_=sa.String(length=20),
        existing_type=postgresql.ENUM("DRAFT", "PUBLISHED", name="project_status"),
        postgresql_using="status::text",
        server_default="DRAFT",
    )
    op.execute("DROP TYPE IF EXISTS project_status")
    op.add_column("projects", sa.Column("review_feedback", sa.Text(), nullable=True))


def downgrade() -> None:
    # Irreversible if any row holds a status the original two-value enum never had
    # (PENDING_REVIEW, CHANGES_REQUESTED); those rows would fail the cast below.
    op.drop_column("projects", "review_feedback")
    op.execute("CREATE TYPE project_status AS ENUM ('DRAFT', 'PUBLISHED')")
    op.alter_column(
        "projects",
        "status",
        type_=postgresql.ENUM("DRAFT", "PUBLISHED", name="project_status", create_type=False),
        existing_type=sa.String(length=20),
        postgresql_using="status::project_status",
        server_default="DRAFT",
    )
