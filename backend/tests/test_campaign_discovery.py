"""Public campaign browsing: NGO identity on each card, and sector/geography filtering.

A campaign is only discoverable once its NGO is verified and has published a profile --
the same visibility rule every other public listing uses (app.domain.visibility).
"""

from app.db import SessionLocal
from app.models import Campaign
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


def _admin(client):
    # Each test may call this more than once (once per NGO it verifies), and the users table is
    # truncated between tests -- so register on first use per test, then just log in afterward.
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


def test_live_campaign_lists_with_ngo_identity(client):
    token, org = _verified_published_ngo(client, sectors=["Water", "Sanitation"], geographies=["Karnataka"])
    campaign_id = _live_campaign(client, token, org)

    r = client.get("/campaigns")
    assert r.status_code == 200, r.text
    ids = {c["id"]: c for c in r.json()}
    assert campaign_id in ids
    card = ids[campaign_id]
    assert card["ngo_name"] == "Shanti Trust"
    assert card["ngo_sectors"] == ["Water", "Sanitation"]
    assert card["ngo_geographies"] == ["Karnataka"]


def test_campaign_detail_carries_ngo_identity(client):
    token, org = _verified_published_ngo(client, sectors=["Education"])
    campaign_id = _live_campaign(client, token, org)

    r = client.get(f"/campaigns/{campaign_id}")
    assert r.status_code == 200, r.text
    assert r.json()["ngo_sectors"] == ["Education"]


def test_sector_filter_excludes_non_matching_campaigns(client):
    water_token, water_org = _verified_published_ngo(client, name="Water Org", sectors=["Water"])
    water_campaign = _live_campaign(client, water_token, water_org)
    edu_token, edu_org = _verified_published_ngo(client, name="Education Org", sectors=["Education"])
    edu_campaign = _live_campaign(client, edu_token, edu_org)

    r = client.get("/campaigns", params={"sectors": ["Water"]})
    ids = {c["id"] for c in r.json()}
    assert water_campaign in ids
    assert edu_campaign not in ids


def test_geography_filter_excludes_non_matching_campaigns(client):
    kt_token, kt_org = _verified_published_ngo(client, name="Karnataka Org", geographies=["Karnataka"])
    kt_campaign = _live_campaign(client, kt_token, kt_org)
    od_token, od_org = _verified_published_ngo(client, name="Odisha Org", geographies=["Odisha"])
    od_campaign = _live_campaign(client, od_token, od_org)

    r = client.get("/campaigns", params={"geographies": ["Odisha"]})
    ids = {c["id"] for c in r.json()}
    assert od_campaign in ids
    assert kt_campaign not in ids


def test_campaign_from_unverified_ngo_is_not_publicly_listed(client):
    # Mirrors how other tests create a LIVE campaign without the org being verified or
    # published -- that combination must not surface in the public listing.
    token = user_token(client, "owner@unverified.org")
    org = client.post("/orgs", json={"name": "Unverified NGO", "org_type": "NGO"}, headers=auth(token)).json()["id"]
    client.put(f"/orgs/{org}/profile", json={"mission": "Mission."}, headers=auth(token))
    with SessionLocal() as db:
        campaign = Campaign(
            ngo_id=org, title="Clean Water", description="Wells.", mission="Safe water.",
            beneficiary_description="300 households", impact_statement="Fewer illnesses.",
            budget_total=500_000, duration_months=6, status="LIVE",
        )
        db.add(campaign)
        db.commit()
        campaign_id = campaign.id

    r = client.get("/campaigns")
    assert campaign_id not in {c["id"] for c in r.json()}

    r = client.get(f"/campaigns/{campaign_id}")
    assert r.status_code == 404
