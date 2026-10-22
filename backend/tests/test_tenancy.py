from tests.helpers import auth, user_token, register, login
from app.db import SessionLocal
from app.models import Membership, Role, User
from sqlalchemy import select


def _create_org(client, token, name="Shanti Trust", org_type="NGO"):
    r = client.post("/orgs", json={"name": name, "org_type": org_type}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _user_id(email):
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def _set_role(email, org_id, role):
    with SessionLocal() as db:
        m = db.scalar(select(Membership).where(Membership.user_id == _user_id(email), Membership.org_id == org_id))
        m.role = role
        db.commit()


def test_creator_becomes_owner_and_org_is_pending(client):
    token = user_token(client, "owner@ngo.org")
    org = _create_org(client, token)
    assert org["verification_status"] == "PENDING"
    members = client.get(f"/orgs/{org['id']}/members", headers=auth(token)).json()
    assert [(m["email"], m["role"]) for m in members] == [("owner@ngo.org", "OWNER")]


def test_cross_tenant_read_is_denied_as_not_found(client):
    a = user_token(client, "a@ngo.org")
    b = user_token(client, "b@csr.com")
    org_a = _create_org(client, a, "Org A")
    r = client.get(f"/orgs/{org_a['id']}", headers=auth(b))
    assert r.status_code == 404  # 404, not 403: does not reveal that the org exists
    assert client.get(f"/orgs/{org_a['id']}/members", headers=auth(b)).status_code == 404


def test_org_listing_contains_only_own_memberships(client):
    a = user_token(client, "a@ngo.org")
    b = user_token(client, "b@csr.com")
    _create_org(client, a, "Org A")
    _create_org(client, b, "Org B")
    names_for_a = [o["name"] for o in client.get("/orgs", headers=auth(a)).json()]
    names_for_b = [o["name"] for o in client.get("/orgs", headers=auth(b)).json()]
    assert names_for_a == ["Org A"]
    assert names_for_b == ["Org B"]


def test_member_cannot_add_members(client):
    owner = user_token(client, "owner@ngo.org")
    member = user_token(client, "member@ngo.org")
    org = _create_org(client, owner)
    client.post(f"/orgs/{org['id']}/members", json={"email": "member@ngo.org", "role": "MEMBER"}, headers=auth(owner))
    other = user_token(client, "other@ngo.org")
    r = client.post(f"/orgs/{org['id']}/members", json={"email": "other@ngo.org", "role": "MEMBER"}, headers=auth(member))
    assert r.status_code == 403


def test_admin_cannot_grant_owner_role(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "admin@ngo.org")
    org = _create_org(client, owner)
    client.post(f"/orgs/{org['id']}/members", json={"email": "admin@ngo.org", "role": "ADMIN"}, headers=auth(owner))
    admin = login(client, "admin@ngo.org")
    user_token(client, "target@ngo.org")
    r = client.post(f"/orgs/{org['id']}/members", json={"email": "target@ngo.org", "role": "OWNER"}, headers=auth(admin))
    assert r.status_code == 403


def test_admin_can_add_member_and_duplicate_is_rejected(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "admin@ngo.org")
    user_token(client, "staff@ngo.org")
    org = _create_org(client, owner)
    client.post(f"/orgs/{org['id']}/members", json={"email": "admin@ngo.org", "role": "ADMIN"}, headers=auth(owner))
    admin = login(client, "admin@ngo.org")
    r = client.post(f"/orgs/{org['id']}/members", json={"email": "staff@ngo.org", "role": "MEMBER"}, headers=auth(admin))
    assert r.status_code == 201
    again = client.post(f"/orgs/{org['id']}/members", json={"email": "staff@ngo.org", "role": "MEMBER"}, headers=auth(admin))
    assert again.status_code == 409


def test_adding_unregistered_email_is_explicit_not_silent(client):
    owner = user_token(client, "owner@ngo.org")
    org = _create_org(client, owner)
    r = client.post(f"/orgs/{org['id']}/members", json={"email": "nobody@x.org", "role": "MEMBER"}, headers=auth(owner))
    assert r.status_code == 404
    assert "No registered user" in r.json()["detail"]


def test_non_member_cannot_add_members_to_someone_elses_org(client):
    owner = user_token(client, "owner@ngo.org")
    intruder = user_token(client, "intruder@x.org")
    user_token(client, "victim@x.org")
    org = _create_org(client, owner)
    r = client.post(f"/orgs/{org['id']}/members", json={"email": "victim@x.org", "role": "OWNER"}, headers=auth(intruder))
    assert r.status_code == 404
