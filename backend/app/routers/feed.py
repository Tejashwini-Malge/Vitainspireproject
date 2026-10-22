from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.feed import DEFAULT_RADIUS_KM, representative_point, score_item
from app.domain.visibility import PUBLIC_NGO_FILTER
from app.models import Campaign, NgoProfile, Organization, Project, ProjectStatus
from app.schemas import FeedItemOut, GeocodeOut
from app.services.geocoding import geocode

router = APIRouter(prefix="/feed", tags=["feed"])
geocode_router = APIRouter(tags=["feed"])


@geocode_router.get("/geocode", response_model=GeocodeOut)
async def geocode_place(q: str = Query(min_length=1, max_length=200)) -> GeocodeOut:
    """Resolve a typed place to lat/lon, so the frontend can send coordinates to GET /feed
    instead of re-geocoding on every feed request."""
    point = await geocode(q)
    if point is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find that place")
    return GeocodeOut(query=point.query, lat=point.lat, lon=point.lon, display_name=point.display_name)


@router.get("", response_model=list[FeedItemOut])
def discovery_feed(
    db: Session = Depends(get_db),
    sectors: list[str] | None = Query(default=None, description="Boost campaigns/projects from NGOs working in these sectors"),
    lat: float | None = Query(default=None, description="Donor's location latitude, to boost nearby NGOs and show distance"),
    lon: float | None = Query(default=None, description="Donor's location longitude"),
    radius_km: float = Query(default=DEFAULT_RADIUS_KM, gt=0, le=2000),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[FeedItemOut]:
    """Live campaigns and standalone published projects, merged and ranked.

    Ranking is a deterministic match score (see app.domain.feed) against the given sectors and,
    when a donor's lat/lon is supplied, real distance to each NGO's geocoded locations -- not a
    model call. Use GET /geocode to turn a typed place into lat/lon first.
    """
    if (lat is None) != (lon is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "lat and lon must be given together")

    preferred_sectors = sectors or []

    campaign_rows = db.execute(
        select(Campaign, Organization.name, NgoProfile.sectors, NgoProfile.geography_points)
        .join(Organization, Organization.id == Campaign.ngo_id)
        .join(NgoProfile, NgoProfile.org_id == Organization.id)
        .where(Campaign.status == "LIVE", *PUBLIC_NGO_FILTER)
    ).all()
    project_rows = db.execute(
        select(Project, Organization.name, NgoProfile.sectors, NgoProfile.geography_points)
        .join(Organization, Organization.id == Project.org_id)
        .join(NgoProfile, NgoProfile.org_id == Organization.id)
        .where(Project.status == ProjectStatus.PUBLISHED, *PUBLIC_NGO_FILTER)
    ).all()

    items: list[FeedItemOut] = []
    for c, ngo_name, ngo_sectors, geography_points in campaign_rows:
        ngo_sectors = list(ngo_sectors)
        geography_points = list(geography_points)
        score, distance_km = score_item(ngo_sectors, geography_points, preferred_sectors, lat, lon, radius_km)
        point = representative_point(geography_points, lat, lon)
        items.append(
            FeedItemOut(
                kind="campaign",
                id=c.id,
                org_id=c.ngo_id,
                org_name=ngo_name,
                org_sectors=ngo_sectors,
                org_geographies=[p["query"] for p in geography_points],
                title=c.title,
                summary=c.mission,
                hero_image_url=c.hero_image_url,
                budget_total=c.budget_total,
                amount_raised=c.amount_raised,
                published_at=c.published_at,
                score=score,
                distance_km=distance_km,
                lat=point[0] if point else None,
                lon=point[1] if point else None,
            )
        )
    for p, ngo_name, ngo_sectors, geography_points in project_rows:
        ngo_sectors = list(ngo_sectors)
        geography_points = list(geography_points)
        score, distance_km = score_item(ngo_sectors, geography_points, preferred_sectors, lat, lon, radius_km)
        point = representative_point(geography_points, lat, lon)
        items.append(
            FeedItemOut(
                kind="project",
                id=p.id,
                org_id=p.org_id,
                org_name=ngo_name,
                org_sectors=ngo_sectors,
                org_geographies=[g["query"] for g in geography_points],
                title=p.title,
                summary=p.summary,
                hero_image_url=None,
                budget_total=None,
                amount_raised=None,
                published_at=p.published_at,
                score=score,
                distance_km=distance_km,
                lat=point[0] if point else None,
                lon=point[1] if point else None,
            )
        )

    items.sort(key=lambda i: (-i.score, -(i.published_at.timestamp() if i.published_at else 0)))
    return items[offset : offset + limit]
