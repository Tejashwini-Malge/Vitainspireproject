"""NGO profile registration and 80G numbers

Self-declared text fields so an NGO's registration number and 80G number can be
printed on a donor's tax certificate. Verifying the underlying documents remains a
separate, existing flow (compliance documents / admin review); this is just the text.

Revision ID: 0014_ngo_registration_numbers
Revises: 0013_pan_verification
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0014_ngo_registration_numbers"
down_revision: str | None = "0013_pan_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ngo_profiles", sa.Column("registration_number", sa.String(length=100), nullable=True))
    op.add_column("ngo_profiles", sa.Column("section_80g_number", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("ngo_profiles", "section_80g_number")
    op.drop_column("ngo_profiles", "registration_number")
