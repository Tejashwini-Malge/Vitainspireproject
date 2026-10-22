from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token


def _pending_org(client, owner_token):
    r = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(owner_token))
    return r.json()["id"]


def test_verification_queue_is_admin_only(client):
    owner = user_token(client, "owner@ngo.org")
    _pending_org(client, owner)
    assert client.get("/admin/verification-queue", headers=auth(owner)).status_code == 403


def test_admin_approves_org_and_status_is_visible_to_owner(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org_id = _pending_org(client, owner)
    admin = login(client, "ops@platform.org")

    queue = client.get("/admin/verification-queue", headers=auth(admin)).json()
    assert [o["id"] for o in queue] == [org_id]

    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "APPROVED"},
        headers=auth(admin),
    )
    assert r.status_code == 200
    assert r.json()["verification_status"] == "APPROVED"

    seen_by_owner = client.get(f"/orgs/{org_id}", headers=auth(owner)).json()
    assert seen_by_owner["verification_status"] == "APPROVED"


def test_rejection_requires_reason(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org_id = _pending_org(client, owner)
    admin = login(client, "ops@platform.org")
    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "REJECTED", "reason": "   "},
        headers=auth(admin),
    )
    assert r.status_code == 422


def test_decided_org_cannot_be_silently_redecided(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org_id = _pending_org(client, owner)
    admin = login(client, "ops@platform.org")
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "REJECTED", "reason": "changed my mind"},
        headers=auth(admin),
    )
    assert r.status_code == 409


def test_verification_writes_audit_with_actor_and_correlation_id(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org_id = _pending_org(client, owner)
    admin_token = login(client, "ops@platform.org")

    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "APPROVED"},
        headers={**auth(admin_token), "x-request-id": "trace-abc-123"},
    )
    assert r.headers["x-request-id"] == "trace-abc-123"

    with SessionLocal() as db:
        ev = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "org.verification_decided", AuditEvent.resource_id == org_id
            )
        )
        assert ev is not None
        assert ev.resource_id == org_id
        assert ev.actor_user_id is not None
        assert ev.correlation_id == "trace-abc-123"
        assert ev.details["from"] == "PENDING" and ev.details["to"] == "APPROVED"


def test_failed_business_action_leaves_no_audit_row(client):
    owner = user_token(client, "owner@ngo.org")
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org_id = _pending_org(client, owner)
    admin = login(client, "ops@platform.org")
    # Rejected at validation before any write: nothing should be audited.
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "REJECTED"}, headers=auth(admin))
    with SessionLocal() as db:
        assert db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "org.verification_decided", AuditEvent.resource_id == org_id
            )
        ) is None


def test_audit_table_is_append_only_by_convention_no_update_path_in_api(client):
    # Guard against a future endpoint that edits audit rows: the API must expose no route that writes audit_events.
    from app.main import app as prod_app

    writes = [r for r in prod_app.routes if getattr(r, "methods", None) and r.methods & {"PUT", "PATCH", "DELETE"}]
    paths = {r.path for r in writes}
    assert not any("audit" in p for p in paths)
