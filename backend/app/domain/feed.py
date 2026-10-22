"""Discovery feed ranking. Deterministic: a plain match score, no LLM involved.

Sector overlap counts for more than geography proximity -- "what cause" is a stronger
signal of relevance than "where", and this keeps the score simple enough to explain
to a donor in one sentence ("because you've supported Water before" / "because this
is within 100km of you").
"""

from app.domain.geo import haversine_km

SECTOR_MATCH_SCORE = 2
GEOGRAPHY_MATCH_SCORE = 1
DEFAULT_RADIUS_KM = 100.0


def nearest_distance_km(org_geography_points: list[dict], preferred_lat: float, preferred_lon: float) -> float | None:
    """The closest of an NGO's geocoded locations to the given point, or None if it has none."""
    distances = [haversine_km(preferred_lat, preferred_lon, p["lat"], p["lon"]) for p in org_geography_points if "lat" in p and "lon" in p]
    return min(distances) if distances else None


def representative_point(
    org_geography_points: list[dict], preferred_lat: float | None = None, preferred_lon: float | None = None
) -> tuple[float, float] | None:
    """One (lat, lon) to plant a map pin at: the geocoded point nearest the donor if a donor
    location is known, otherwise just the first one an NGO has. None if the NGO has none at all
    (not every geography string geocodes successfully -- see app.services.geocoding)."""
    points = [p for p in org_geography_points if "lat" in p and "lon" in p]
    if not points:
        return None
    if preferred_lat is not None and preferred_lon is not None:
        closest = min(points, key=lambda p: haversine_km(preferred_lat, preferred_lon, p["lat"], p["lon"]))
        return closest["lat"], closest["lon"]
    return points[0]["lat"], points[0]["lon"]


def score_item(
    org_sectors: list[str],
    org_geography_points: list[dict],
    preferred_sectors: list[str],
    preferred_lat: float | None,
    preferred_lon: float | None,
    radius_km: float = DEFAULT_RADIUS_KM,
) -> tuple[int, float | None]:
    """Returns (score, distance_km). distance_km is the nearest match regardless of radius,
    so a donor can see "120km away" even when that falls outside the boost radius."""
    score = 0
    if preferred_sectors and set(org_sectors) & set(preferred_sectors):
        score += SECTOR_MATCH_SCORE

    distance_km = None
    if preferred_lat is not None and preferred_lon is not None:
        distance_km = nearest_distance_km(org_geography_points, preferred_lat, preferred_lon)
        if distance_km is not None and distance_km <= radius_km:
            score += GEOGRAPHY_MATCH_SCORE

    return score, distance_km
