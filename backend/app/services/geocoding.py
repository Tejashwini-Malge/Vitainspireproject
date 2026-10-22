"""Forward geocoding via OpenStreetMap Nominatim.

Free, no API key -- but its usage policy asks for a real User-Agent and no more than
~1 request/second. That's fine here: geocoding only runs when an NGO saves a changed
geography entry, or when a donor adds one location to the feed -- never on every
feed read. A failed or ambiguous lookup returns None rather than raising, so it is
never a reason to block a profile save.
"""

from dataclasses import dataclass

import httpx

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "Imparency/1.0 (https://imparency.example; donation transparency platform)"


@dataclass
class GeoPoint:
    query: str
    lat: float
    lon: float
    display_name: str


async def geocode(query: str) -> GeoPoint | None:
    query = query.strip()
    if not query:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            results = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not results:
        return None
    first = results[0]
    try:
        return GeoPoint(query=query, lat=float(first["lat"]), lon=float(first["lon"]), display_name=first.get("display_name", query))
    except (KeyError, TypeError, ValueError):
        return None
