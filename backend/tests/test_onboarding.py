from tests.helpers import auth, user_token

GOOD_PROFILE = {
    "mission": "Clean drinking water for rural households in Odisha",
    "sectors": ["Water"],
    "geographies": ["Odisha"],
}
GOOD_PROJECT = {"title": "Clean Water Wells", "summary": "Dig wells in drought-hit villages", "description": "Detail."}


def _create_org(client, token, org_type="NGO", name="Shanti Trust"):
    r = client.post("/orgs", json={"name": name, "org_type": org_type}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_non_member_gets_404(client):
    owner_token = user_token(client, "owner@ngo.org")
    org = _create_org(client, owner_token)
    outsider = user_token(client, "outsider@example.org")
    r = client.get(f"/orgs/{org}/onboarding/status", headers=auth(outsider))
    assert r.status_code == 404


def test_fresh_ngo_has_no_steps_done(client):
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)
    r = client.get(f"/orgs/{org}/onboarding/status", headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["org_type"] == "NGO"
    assert body["completion_pct"] == 0
    assert all(not s["done"] for s in body["steps"])
    assert body["next_step"]["key"] == "profile_started"


def test_ngo_steps_advance_as_profile_and_project_are_added(client):
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)

    r = client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(token))
    assert r.status_code == 200, r.text

    r = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token))
    assert r.status_code == 201, r.text

    r = client.get(f"/orgs/{org}/onboarding/status", headers=auth(token))
    body = r.json()
    by_key = {s["key"]: s["done"] for s in body["steps"]}
    assert by_key["profile_started"] is True
    assert by_key["project_created"] is True
    assert by_key["profile_published"] is False
    assert by_key["project_published"] is False
    assert body["completion_pct"] > 0 and body["completion_pct"] < 100


def test_fresh_csr_has_no_steps_done(client):
    token = user_token(client, "owner@csr.org")
    org = _create_org(client, token, org_type="CSR", name="Impact Fund")
    r = client.get(f"/orgs/{org}/onboarding/status", headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["org_type"] == "CSR"
    assert body["completion_pct"] == 0
    assert body["next_step"]["key"] == "org_verified"
