"""Project -> Campaign link, and the website-derived campaign draft.

Budget, beneficiaries, impact and milestones live on Campaign. A project references
the campaign that funds it instead of restating those fields.
"""

import pytest

from app.services.website_extractor import WebsiteData
from tests.helpers import auth, user_token

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
    "budget_total": 5000000,
    "duration_months": 9,
}


def _org(client, token, name="Shanti Trust", org_type="NGO"):
    r = client.post("/orgs", json={"name": name, "org_type": org_type}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _campaign(client, token):
    r = client.post("/ngo/campaigns", json=GOOD_CAMPAIGN, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_project_can_reference_its_funding_campaign(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    campaign_id = _campaign(client, token)

    r = client.post(
        f"/orgs/{org}/projects",
        json={"title": "Borewell rehabilitation", "summary": "Restore 12 borewells.",
              "campaign_id": campaign_id},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["campaign_id"] == campaign_id

    listed = client.get(f"/orgs/{org}/projects", headers=auth(token)).json()
    assert listed[0]["campaign_id"] == campaign_id


def test_project_without_a_campaign_is_still_valid(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    r = client.post(
        f"/orgs/{org}/projects",
        json={"title": "Scoping study", "summary": "Survey before we raise money."},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["campaign_id"] is None


def test_project_cannot_reference_another_orgs_campaign(client):
    """Tenancy: the campaign id of another organisation must not be linkable."""
    other = user_token(client, "other@ngo.org")
    _org(client, other, name="Other Trust")
    stolen_campaign = _campaign(client, other)

    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)

    r = client.post(
        f"/orgs/{org}/projects",
        json={"title": "Piggyback", "summary": "Trying to attach someone else's campaign.",
              "campaign_id": stolen_campaign},
        headers=auth(token),
    )
    assert r.status_code == 404, r.text


def test_unknown_campaign_id_is_rejected(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    r = client.post(
        f"/orgs/{org}/projects",
        json={"title": "Ghost", "summary": "Points at nothing.",
              "campaign_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth(token),
    )
    assert r.status_code == 404, r.text


def test_campaign_link_can_be_cleared_on_update(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    campaign_id = _campaign(client, token)
    pid = client.post(
        f"/orgs/{org}/projects",
        json={"title": "Borewells", "summary": "Restore wells.", "campaign_id": campaign_id},
        headers=auth(token),
    ).json()["id"]

    r = client.put(
        f"/orgs/{org}/projects/{pid}",
        json={"title": "Borewells", "summary": "Restore wells.", "campaign_id": None},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["campaign_id"] is None


# --------------------------------------------------------------- website suggestions

@pytest.fixture()
def fake_site(monkeypatch):
    """Replace the network fetch so the suggestion path is testable offline."""
    def _install(data):
        async def _fake(url):
            return data
        monkeypatch.setattr("app.routers.campaigns.fetch_website", _fake)
    return _install


def test_suggestion_returns_a_draft_with_its_source_and_saves_nothing(client, fake_site):
    fake_site(WebsiteData(
        title="Shanti Water Trust",
        description="We restore failed borewells across rural Karnataka so that families "
                    "no longer walk four kilometres for drinking water every morning.",
        mission="Clean water for every rural school",
    ))
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)

    r = client.post(
        "/ngo/campaigns/suggest-from-website",
        json={"website_url": "https://shanti.example.org"},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["source_url"] == "https://shanti.example.org"
    assert body["title"]["value"] == "Shanti Water Trust"
    assert body["title"]["source_url"] == "https://shanti.example.org"
    assert body["mission"]["value"] == "Clean water for every rural school"
    assert body["disclaimer"]

    # Nothing was persisted: the NGO still has no campaigns.
    assert client.get("/ngo/campaigns", headers=auth(token)).json() == []


def test_suggestion_reports_which_values_are_too_short_to_submit(client, fake_site):
    """CampaignIn requires description >= 50 chars. Say so before the NGO hits a 422."""
    fake_site(WebsiteData(title="Shanti Water Trust", description="We dig wells.", mission="Water"))
    token = user_token(client, "owner@ngo.org")
    _org(client, token)

    body = client.post(
        "/ngo/campaigns/suggest-from-website",
        json={"website_url": "https://shanti.example.org"},
        headers=auth(token),
    ).json()

    assert body["description"]["meets_minimum"] is False
    assert body["description"]["minimum_length"] == 50
    assert body["title"]["meets_minimum"] is True  # 18 chars, minimum is 10


def test_suggestion_never_invents_beneficiaries_or_impact(client, fake_site):
    """A website does not state these, so they must be asked for, not fabricated."""
    fake_site(WebsiteData(title="Shanti Water Trust", description="x" * 60, mission="Water for all"))
    token = user_token(client, "owner@ngo.org")
    _org(client, token)

    body = client.post(
        "/ngo/campaigns/suggest-from-website",
        json={"website_url": "https://shanti.example.org"},
        headers=auth(token),
    ).json()

    for required in ("beneficiary_description", "impact_statement", "budget_total", "duration_months"):
        assert required in body["needs_your_input"]
    assert "beneficiary_description" not in body


def test_missing_fields_are_listed_rather_than_guessed(client, fake_site):
    fake_site(WebsiteData(title=None, description=None, mission=None))
    token = user_token(client, "owner@ngo.org")
    _org(client, token)

    body = client.post(
        "/ngo/campaigns/suggest-from-website",
        json={"website_url": "https://shanti.example.org"},
        headers=auth(token),
    ).json()

    assert body["title"] is None and body["description"] is None and body["mission"] is None
    for name in ("title", "description", "mission"):
        assert name in body["needs_your_input"]


def test_suggestion_requires_an_ngo_membership(client, fake_site):
    fake_site(WebsiteData(title="Anything"))
    token = user_token(client, "csr@foundation.org")
    _org(client, token, name="Acme Foundation", org_type="CSR")

    r = client.post(
        "/ngo/campaigns/suggest-from-website",
        json={"website_url": "https://acme.example.org"},
        headers=auth(token),
    )
    assert r.status_code == 403, r.text
