from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token

GOOD_PROFILE = {
    "mission": "Clean drinking water for rural households in Odisha",
    "about": "Founded by local volunteers in 2015.",
    "sectors": ["Water", "Sanitation"],
    "geographies": ["Odisha", "Jharkhand"],
    "founded_year": 2015,
    "website": "https://example-ngo.org",
}


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


def _owner_with_ngo(client):
    token = user_token(client, "owner@ngo.org")
    return token, _create_org(client, token)


def test_profile_is_empty_until_saved(client):
    token, org = _owner_with_ngo(client)
    r = client.get(f"/orgs/{org}/profile", headers=auth(token))
    assert r.status_code == 200 and r.json() is None


def test_owner_saves_profile_and_audit_records_changed_fields(client):
    token, org = _owner_with_ngo(client)
    r = client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "DRAFT" and body["published_at"] is None
    assert body["sectors"] == ["Water", "Sanitation"]
    with SessionLocal() as db:
        ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "profile.created", AuditEvent.org_id == org))
        assert ev is not None and "mission" in ev.details["changed_fields"]


def test_website_must_be_https(client):
    token, org = _owner_with_ngo(client)
    r = client.put(f"/orgs/{org}/profile", json={**GOOD_PROFILE, "website": "http://example.org"}, headers=auth(token))
    assert r.status_code == 422


def test_lists_are_trimmed_and_blank_entries_dropped(client):
    token, org = _owner_with_ngo(client)
    r = client.put(
        f"/orgs/{org}/profile",
        json={**GOOD_PROFILE, "sectors": ["  Water ", "", "   "], "geographies": ["Odisha"]},
        headers=auth(token),
    )
    assert r.json()["sectors"] == ["Water"]


def test_member_can_read_but_not_edit_profile(client):
    owner, org = _owner_with_ngo(client)
    client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(owner))
    member = user_token(client, "member@ngo.org")
    client.post(f"/orgs/{org}/members", json={"email": "member@ngo.org", "role": "MEMBER"}, headers=auth(owner))
    assert client.get(f"/orgs/{org}/profile", headers=auth(member)).status_code == 200
    r = client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(member))
    assert r.status_code == 403


def test_non_member_cannot_see_or_edit_profile(client):
    owner, org = _owner_with_ngo(client)
    outsider = user_token(client, "outsider@x.org")
    assert client.get(f"/orgs/{org}/profile", headers=auth(outsider)).status_code == 404
    assert client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(outsider)).status_code == 404


def test_csr_organization_cannot_have_ngo_profile(client):
    token = user_token(client, "csr@foundation.org")
    org = _create_org(client, token, org_type="CSR", name="Acme Foundation")
    r = client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(token))
    assert r.status_code == 422


def test_publish_reports_all_blockers_while_unverified(client):
    token, org = _owner_with_ngo(client)
    client.put(f"/orgs/{org}/profile", json={**GOOD_PROFILE, "geographies": []}, headers=auth(token))
    r = client.post(f"/orgs/{org}/profile/publish", headers=auth(token))
    assert r.status_code == 409
    blockers = r.json()["detail"]["blockers"]
    assert any("verified" in b for b in blockers)
    assert any("geography" in b for b in blockers)


def test_publish_after_verification_and_public_visibility_lifecycle(client):
    token, org = _owner_with_ngo(client)
    client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(token))

    # Unknown, unpublished and unverified all look identical to the public.
    assert client.get(f"/public/ngos/{org}").status_code == 404

    _approve(client, org)
    assert client.get(f"/public/ngos/{org}").status_code == 404, "verified but still draft must stay private"

    r = client.post(f"/orgs/{org}/profile/publish", headers=auth(token))
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED"

    public = client.get(f"/public/ngos/{org}")
    assert public.status_code == 200
    body = public.json()
    assert body["name"] == "Shanti Trust"
    assert body["verified_at"] is not None
    assert body["profile"]["mission"] == GOOD_PROFILE["mission"]
    assert "disclaimer" in body and "private" in body["disclaimer"]

    client.post(f"/orgs/{org}/profile/unpublish", headers=auth(token))
    assert client.get(f"/public/ngos/{org}").status_code == 404


def test_public_endpoint_hides_csr_and_unknown_ids_identically(client):
    token = user_token(client, "csr@foundation.org")
    csr = _create_org(client, token, org_type="CSR", name="Acme")
    a = client.get(f"/public/ngos/{csr}")
    b = client.get("/public/ngos/00000000-0000-0000-0000-000000000000")
    assert a.status_code == b.status_code == 404
    assert a.json() == b.json()


def test_partial_profile_save_does_not_wipe_fields_the_client_omitted(client):
    """A client that omits a field must leave it untouched.

    The profile edit form did not render vision, description or organization_title, so
    every save sent a payload without them and silently nulled whatever the website
    extractor had populated. Omission must mean "unchanged", not "clear".
    """
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)

    full = {
        **GOOD_PROFILE,
        "vision": "Every household has safe water by 2030",
        "description": "A registered public charitable trust operating since 2015.",
        "organization_title": "Shanti Charitable Trust",
    }
    r = client.put(f"/orgs/{org}/profile", json=full, headers=auth(token))
    assert r.status_code == 200, r.text

    # A save that knows nothing about the three extended fields.
    partial = {
        "mission": "Clean drinking water for rural households in Odisha and Bihar",
        "sectors": ["Water"],
        "geographies": ["Odisha"],
    }
    r = client.put(f"/orgs/{org}/profile", json=partial, headers=auth(token))
    assert r.status_code == 200, r.text

    body = client.get(f"/orgs/{org}/profile", headers=auth(token)).json()
    assert body["mission"] == partial["mission"]          # the sent field changed
    assert body["vision"] == full["vision"]               # the omitted fields survived
    assert body["description"] == full["description"]
    assert body["organization_title"] == full["organization_title"]


def test_explicit_null_still_clears_a_profile_field(client):
    """Omission means "unchanged", but an explicit null is a deliberate clear."""
    token = user_token(client, "owner2@ngo.org")
    org = _create_org(client, token, name="Second Trust")

    client.put(
        f"/orgs/{org}/profile",
        json={**GOOD_PROFILE, "vision": "A vision worth clearing"},
        headers=auth(token),
    )
    r = client.put(
        f"/orgs/{org}/profile",
        json={**GOOD_PROFILE, "vision": None},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/orgs/{org}/profile", headers=auth(token)).json()["vision"] is None
