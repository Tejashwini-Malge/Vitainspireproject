from tests.helpers import auth, login, make_platform_admin, user_token


def _create_org(client, token, org_type="NGO", name="Shanti Trust"):
    r = client.post("/orgs", json={"name": name, "org_type": org_type}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _admin_token(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def test_ai_assist_falls_back_to_deterministic_draft_without_api_key(client):
    owner = user_token(client, "owner@ngo.org")
    org = _create_org(client, owner)
    admin = _admin_token(client)

    r = client.get(f"/admin/organizations/{org}/ai-assist", headers=auth(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated_by"] == "rules"
    assert "has not submitted a profile yet" in body["summary"]
    assert "No compliance documents uploaded" in body["flags"]
    assert body["sources"] == [f"organization:{org}"]
    assert "proposal" in body["disclaimer"].lower()


def test_ai_assist_reflects_submitted_profile(client):
    owner = user_token(client, "owner@ngo.org")
    org = _create_org(client, owner)
    client.put(
        f"/orgs/{org}/profile",
        json={"mission": "Water for all", "sectors": ["Water"], "geographies": ["Odisha"]},
        headers=auth(owner),
    )
    admin = _admin_token(client)
    r = client.get(f"/admin/organizations/{org}/ai-assist", headers=auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert "Water for all" in body["summary"]
    assert any("profile" in s for s in body["sources"])


def test_ai_assist_requires_platform_admin(client):
    owner = user_token(client, "owner@ngo.org")
    org = _create_org(client, owner)
    r = client.get(f"/admin/organizations/{org}/ai-assist", headers=auth(owner))
    assert r.status_code == 403


def test_reviewer_cannot_ai_assist_their_own_organization(client):
    admin = _admin_token(client)
    org = _create_org(client, admin, name="Ops Own Org")
    r = client.get(f"/admin/organizations/{org}/ai-assist", headers=auth(admin))
    assert r.status_code == 403
