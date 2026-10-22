"""Add extracted website data fields to ngo_profiles

Revision ID: 0003
Revises: 0002_profiles_documents_review
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002_profiles_documents_review'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ngo_profiles', sa.Column('vision', sa.Text(), nullable=True))
    op.add_column('ngo_profiles', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('ngo_profiles', sa.Column('organization_title', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('ngo_profiles', 'organization_title')
    op.drop_column('ngo_profiles', 'description')
    op.drop_column('ngo_profiles', 'vision')
