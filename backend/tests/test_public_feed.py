from tests.helpers import auth, login, make_platform_admin, user_token


def _create_org(client, token, org_type="NGO", name="Shanti Trust"):
    r = client.post("/orgs", json={"name": name, "org_type": org_type}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _approve(client, org_id):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    admin = login(client, "ops@platform.org")
    r = client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    assert r.status_code == 200, r.text


def test_public_ngos_lists_only_verified_and_published(client):
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)
    assert client.get("/public/ngos").json() == []

    client.put(
        f"/orgs/{org}/profile",
        json={"mission": "Water for all", "sectors": ["Water"], "geographies": ["Odisha"]},
        headers=auth(token),
    )
    assert client.get("/public/ngos").json() == [], "unverified NGO must not appear even with a profile"

    _approve(client, org)
    assert client.get("/public/ngos").json() == [], "verified but unpublished must not appear"

    client.post(f"/orgs/{org}/profile/publish", headers=auth(token))
    listing = client.get("/public/ngos").json()
    assert len(listing) == 1 and listing[0]["name"] == "Shanti Trust"


def test_csr_never_appears_in_public_ngo_listing(client):
    token = user_token(client, "csr@foundation.org")
    _create_org(client, token, org_type="CSR", name="Acme Foundation")
    assert client.get("/public/ngos").json() == []
