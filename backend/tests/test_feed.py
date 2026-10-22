"""GET /feed: merges live campaigns and published projects into one ranked list.

Ranking is deterministic (app.domain.feed.score_item) -- no LLM call in the path.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document, DocumentReviewDecision, DocumentType, ReviewStatus, User
from tests.helpers import auth, login, make_platform_admin, user_token

GOOD_CAMPAIGN = {
    "title": "Restore twelve village borewells",
    "description": (
        "Twelve borewells across four villages have failed, leaving families walking "
        "four kilometres for water. This campaign funds their full rehabilitation "
        "including pumps, platforms and water testing."
    ),
    "mission": "Clean water for rural schools",
    "beneficiary_count": 4000,
    "beneficiary_description": "Families and school children across four villages in Karnataka.",
    "impact_statement": "Four thousand people gain year-round access to safe drinking water.",
    "budget_total": 5_000_000,
    "duration_months": 9,
}
GOOD_PROJECT = {"title": "Clean Water Wells", "summary": "Dig wells in drought-hit villages", "description": "Detail."}


def _admin(client):
    r = client.post("/auth/register", json={"email": "ops@platform.org", "password": "correct-horse-battery", "full_name": "Ops"})
    if r.status_code == 201:
        make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def _verified_published_ngo(client, name="Shanti Trust", sectors=None, geographies=None):
    token = user_token(client, f"owner-{name.lower().replace(' ', '')}@ngo.org")
    org = client.post("/orgs", json={"name": name, "org_type": "NGO"}, headers=auth(token)).json()["id"]
    client.put(
        f"/orgs/{org}/profile",
        json={"mission": "Our mission.", "sectors": sectors or ["Water"], "geographies": geographies or ["Karnataka"]},
        headers=auth(token),
    )
    admin = _admin(client)
    r = client.post(f"/admin/organizations/{org}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    assert r.status_code == 200, r.text
    r = client.post(f"/orgs/{org}/profile/publish", headers=auth(token))
    assert r.status_code == 200, r.text
    return token, org


def _live_campaign(client, token, org_id) -> str:
    campaign_id = client.post("/ngo/campaigns", json=GOOD_CAMPAIGN, headers=auth(token)).json()["id"]
    client.post(f"/ngo/campaigns/{campaign_id}/submit-for-review", headers=auth(token))
    admin = _admin(client)
    r = client.post(f"/admin/campaigns/{campaign_id}/approve", headers=auth(admin))
    assert r.status_code == 200, r.text
    return campaign_id


def _approve_docs(client, org_id, owner_email):
    with SessionLocal() as db:
        user_id = db.scalar(select(User).where(User.email == owner_email)).id
        for doc_type in (DocumentType.PAN, DocumentType.FCRA, DocumentType.SECTION_12A, DocumentType.SECTION_80G, DocumentType.REGISTRATION):
            doc = Document(
                org_id=org_id,
                doc_type=doc_type,
                title=f"{doc_type.value} Certificate",
                original_filename=f"{doc_type.value}.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                sha256=f"sha-{doc_type.value}-{org_id}",
                storage_key=f"{doc_type.value}_key_{org_id}",
                uploaded_by_user_id=user_id,
            )
            db.add(doc)
            db.flush()
            db.add(
                DocumentReviewDecision(
                    document_id=doc.id,
                    reviewer_user_id=user_id,
                    decision=ReviewStatus.APPROVED,
                    reason="Document verified",
                    previous_status=ReviewStatus.PENDING_REVIEW,
                )
            )
        db.commit()


def _published_project(client, token, org_id, owner_email) -> str:
    _approve_docs(client, org_id, owner_email)
    project_id = client.post(f"/orgs/{org_id}/projects", json=GOOD_PROJECT, headers=auth(token)).json()["id"]
    r = client.post(f"/orgs/{org_id}/projects/{project_id}/submit-for-review", headers=auth(token))
    assert r.status_code == 200, r.text
    admin = _admin(client)
    r = client.post(f"/admin/projects/{project_id}/decisions", json={"decision": "PUBLISHED"}, headers=auth(admin))
    assert r.status_code == 200, r.text
    return project_id


def test_feed_merges_campaigns_and_projects(client):
    token, org = _verified_published_ngo(client)
    campaign_id = _live_campaign(client, token, org)
    project_id = _published_project(client, token, org, "owner-shantitrust@ngo.org")

    r = client.get("/feed")
    assert r.status_code == 200, r.text
    body = r.json()
    kinds = {(item["id"], item["kind"]) for item in body}
    assert (campaign_id, "campaign") in kinds
    assert (project_id, "project") in kinds


def test_feed_boosts_matching_sector_above_non_matching(client):
    water_token, water_org = _verified_published_ngo(client, name="Water Org", sectors=["Water"])
    water_campaign = _live_campaign(client, water_token, water_org)
    edu_token, edu_org = _verified_published_ngo(client, name="Education Org", sectors=["Education"])
    edu_campaign = _live_campaign(client, edu_token, edu_org)

    r = client.get("/feed", params={"sectors": ["Water"]})
    body = r.json()
    ids_in_order = [item["id"] for item in body]
    assert ids_in_order.index(water_campaign) < ids_in_order.index(edu_campaign)

    by_id = {item["id"]: item for item in body}
    assert by_id[water_campaign]["score"] == 2
    assert by_id[edu_campaign]["score"] == 0


def test_feed_without_preferences_is_just_recency_ordered(client):
    token, org = _verified_published_ngo(client)
    campaign_id = _live_campaign(client, token, org)

    r = client.get("/feed")
    assert r.status_code == 200
    assert all(item["score"] == 0 for item in r.json())
    assert any(item["id"] == campaign_id for item in r.json())


def test_feed_geography_boost_uses_real_distance(client, monkeypatch):
    # Real coordinates: Govandi is a Mumbai suburb (~15km from the city centre); Bundelkhand is
    # ~1000km away. A donor near central Mumbai should boost the Mumbai NGO, not the other one.
    from app.services.geocoding import GeoPoint

    coords = {"Govandi, Mumbai": (19.0433, 72.9289), "Bundelkhand, Madhya Pradesh": (25.0, 79.5)}

    async def _geocode(query):
        query = query.strip()
        if query not in coords:
            return None
        lat, lon = coords[query]
        return GeoPoint(query=query, lat=lat, lon=lon, display_name=query)

    monkeypatch.setattr("app.routers.profiles.geocode", _geocode)

    mumbai_token, mumbai_org = _verified_published_ngo(client, name="Mumbai Org", geographies=["Govandi, Mumbai"])
    mumbai_campaign = _live_campaign(client, mumbai_token, mumbai_org)
    bk_token, bk_org = _verified_published_ngo(client, name="Bundelkhand Org", geographies=["Bundelkhand, Madhya Pradesh"])
    bk_campaign = _live_campaign(client, bk_token, bk_org)

    r = client.get("/feed", params={"lat": 19.0760, "lon": 72.8777})
    assert r.status_code == 200, r.text
    by_id = {item["id"]: item for item in r.json()}
    assert by_id[mumbai_campaign]["score"] == 1
    assert by_id[mumbai_campaign]["distance_km"] < 100
    assert by_id[bk_campaign]["score"] == 0
    assert by_id[bk_campaign]["distance_km"] > 100


def test_feed_requires_lat_and_lon_together(client):
    r = client.get("/feed", params={"lat": 19.0})
    assert r.status_code == 422


def test_geocode_endpoint_resolves_a_place(client, monkeypatch):
    from app.services.geocoding import GeoPoint

    async def _geocode(query):
        return GeoPoint(query=query, lat=19.076, lon=72.8777, display_name="Mumbai, Maharashtra, India")

    monkeypatch.setattr("app.routers.feed.geocode", _geocode)

    r = client.get("/geocode", params={"q": "Mumbai"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lat"] == 19.076 and body["lon"] == 72.8777 and body["display_name"] == "Mumbai, Maharashtra, India"


def test_geocode_endpoint_404s_for_unknown_place(client, monkeypatch):
    async def _geocode(query):
        return None

    monkeypatch.setattr("app.routers.feed.geocode", _geocode)
    r = client.get("/geocode", params={"q": "Nowhereville"})
    assert r.status_code == 404


def test_feed_items_carry_a_lat_lon_for_map_pins(client):
    # Every feed item geocoded at profile-save time should come back with a lat/lon a map
    # can plant a pin at, even when the donor hasn't given their own location.
    token, org = _verified_published_ngo(client, geographies=["Karnataka"])
    campaign_id = _live_campaign(client, token, org)

    r = client.get("/feed")
    assert r.status_code == 200, r.text
    by_id = {item["id"]: item for item in r.json()}
    assert by_id[campaign_id]["lat"] == 20.0
    assert by_id[campaign_id]["lon"] == 78.0
