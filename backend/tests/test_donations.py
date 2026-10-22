from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token

BILLING = {
    "line1": "221B Baker Street",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
    "country": "India",
}

GOOD_DONATION = {
    "donor_name": "Asha Rao",
    "donor_email": "asha@example.com",
    "billing_address": BILLING,
    "amount": "500.00",
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


def _verified_published_ngo(client):
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)
    client.put(
        f"/orgs/{org}/profile",
        json={"mission": "Water for all", "sectors": ["Water"], "geographies": ["Odisha"]},
        headers=auth(token),
    )
    _approve(client, org)
    client.post(f"/orgs/{org}/profile/publish", headers=auth(token))
    return token, org


def test_anonymous_donation_succeeds_and_is_recorded(client):
    token, org = _verified_published_ngo(client)
    r = client.post(f"/public/ngos/{org}/donations", json=GOOD_DONATION)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount_minor"] == 50000
    assert body["currency"] == "INR"
    assert body["billing_address"]["city"] == "Bengaluru"

    with SessionLocal() as db:
        ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "donation.received", AuditEvent.org_id == org))
        assert ev is not None and ev.actor_user_id is None

    org_view = client.get(f"/orgs/{org}/donations", headers=auth(token))
    assert org_view.status_code == 200 and len(org_view.json()) == 1


def test_donation_to_unverified_ngo_is_rejected(client):
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)
    r = client.post(f"/public/ngos/{org}/donations", json=GOOD_DONATION)
    assert r.status_code == 422
    assert "not yet verified" in r.json()["detail"]


def test_donation_to_csr_organization_is_rejected(client):
    token = user_token(client, "csr@foundation.org")
    org = _create_org(client, token, org_type="CSR", name="Acme Foundation")
    r = client.post(f"/public/ngos/{org}/donations", json=GOOD_DONATION)
    assert r.status_code == 422


def test_zero_or_negative_amount_rejected(client):
    _, org = _verified_published_ngo(client)
    for bad_amount in ("0", "-10.00"):
        r = client.post(f"/public/ngos/{org}/donations", json={**GOOD_DONATION, "amount": bad_amount})
        assert r.status_code in (422,)


def test_registered_donor_donation_is_linked_to_their_account_and_visible_in_their_history(client):
    _, org = _verified_published_ngo(client)
    donor_token = user_token(client, "donor@example.com")
    r = client.post(f"/public/ngos/{org}/donations", json=GOOD_DONATION, headers=auth(donor_token))
    assert r.status_code == 201, r.text

    mine = client.get("/me/donations", headers=auth(donor_token))
    assert mine.status_code == 200 and len(mine.json()) == 1

    other_donor = user_token(client, "other@example.com")
    assert client.get("/me/donations", headers=auth(other_donor)).json() == []


def test_donation_cannot_be_targeted_at_a_project_from_a_different_org(client):
    _, org_a = _verified_published_ngo(client)
    owner_b = user_token(client, "owner@other-ngo.org")
    org_b = _create_org(client, owner_b, name="Other Trust")
    project_b = client.post(
        f"/orgs/{org_b}/projects",
        json={"title": "Other Project", "summary": "Summary"},
        headers=auth(owner_b),
    ).json()

    r = client.post(f"/public/ngos/{org_a}/donations", json={**GOOD_DONATION, "project_id": project_b["id"]})
    assert r.status_code == 422


def test_donations_table_is_append_only(client):
    from sqlalchemy import text

    _, org = _verified_published_ngo(client)
    r = client.post(f"/public/ngos/{org}/donations", json=GOOD_DONATION)
    donation_id = r.json()["id"]
    with SessionLocal() as db:
        try:
            db.execute(text("UPDATE donations SET amount_minor = 1 WHERE id = :id"), {"id": donation_id})
            db.commit()
            assert False, "update should have been rejected by the append-only trigger"
        except Exception as exc:
            db.rollback()
            assert "append-only" in str(exc)
