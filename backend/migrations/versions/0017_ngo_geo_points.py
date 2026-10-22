"""NGO profile geography points (geocoded)

Each entry in NgoProfile.geographies is free text an NGO typed ("Govandi, Mumbai").
This adds geography_points: the same entries geocoded to lat/lon, so a donor's
location (or a typed place) can be ranked by real distance instead of string
matching. Geocoding runs when a profile is saved (app.services.geocoding), not on
every read -- a geography string that fails to geocode is simply omitted here, it
is never a reason to refuse the profile save.

Revision ID: 0017_ngo_geo_points
Revises: 0016_org_to_org_conversations
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0017_ngo_geo_points"
down_revision: str | None = "0016_org_to_org_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ngo_profiles",
        sa.Column("geography_points", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("ngo_profiles", "geography_points")
