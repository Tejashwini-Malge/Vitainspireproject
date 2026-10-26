"""Re-verification / review-due workflow for organisations (ADM-004).

Before this, a decided organisation could never be re-decided at all (409 forever) and
there was no "review due" state. review_due_at is deliberately orthogonal to
verification_status: flagging an APPROVED org for review does not revoke anything it
already has -- it only unblocks a later, explicit re-decision and surfaces the org in a
dedicated queue.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token


def _approved_org(client) -> tuple[str, str]:
    owner = user_token(client, "owner@ngo.org")
    org_id = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(owner)).json()["id"]
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    admin = login(client, "ops@platform.org")
    r = client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    assert r.status_code == 200, r.text
    return org_id, admin


def test_request_review_does_not_change_verification_status(client):
    org_id, admin = _approved_org(client)
    r = client.post(
        f"/admin/organizations/{org_id}/request-review",
        json={"reason": "Annual compliance renewal due."},
        headers=auth(admin),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verification_status"] == "APPROVED"
    assert body["review_due_at"] is not None
    assert body["review_reason"] == "Annual compliance renewal due."


def test_request_review_requires_a_reason(client):
    org_id, admin = _approved_org(client)
    r = client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": ""}, headers=auth(admin))
    assert r.status_code == 422, r.text


def test_request_review_on_a_pending_org_is_rejected(client):
    owner = user_token(client, "owner@ngo.org")
    org_id = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(owner)).json()["id"]
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    admin = login(client, "ops@platform.org")

    r = client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "x"}, headers=auth(admin))
    assert r.status_code == 409, r.text


def test_request_review_twice_is_rejected(client):
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "first"}, headers=auth(admin))
    r = client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "second"}, headers=auth(admin))
    assert r.status_code == 409, r.text


def test_request_review_is_admin_only(client):
    org_id, _ = _approved_org(client)
    owner = login(client, "owner@ngo.org")
    r = client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "x"}, headers=auth(owner))
    assert r.status_code == 403, r.text


def test_review_due_queue_lists_flagged_orgs_only(client):
    org_id, admin = _approved_org(client)
    assert client.get("/admin/organizations/review-due", headers=auth(admin)).json() == []

    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))
    queue = client.get("/admin/organizations/review-due", headers=auth(admin)).json()
    assert [o["id"] for o in queue] == [org_id]


def test_review_due_queue_is_admin_only(client):
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))
    owner = login(client, "owner@ngo.org")
    assert client.get("/admin/organizations/review-due", headers=auth(owner)).status_code == 403


def test_review_due_org_can_now_be_redecided(client):
    """The core fix: a previously-impossible re-decision now succeeds once flagged."""
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "complaint received"}, headers=auth(admin))

    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "REJECTED", "reason": "Compliance lapse confirmed."},
        headers=auth(admin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "REJECTED"
    assert r.json()["review_due_at"] is None  # resolved by the new decision
    assert r.json()["review_reason"] is None


def test_redecision_removes_org_from_review_due_queue(client):
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))
    client.post(f"/admin/organizations/{org_id}/verification", json={"decision": "APPROVED"}, headers=auth(admin))

    assert client.get("/admin/organizations/review-due", headers=auth(admin)).json() == []


def test_redecision_without_review_due_is_still_409(client):
    """Must not regress the existing protection for an org that was never flagged."""
    org_id, admin = _approved_org(client)
    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "REJECTED", "reason": "changed my mind"},
        headers=auth(admin),
    )
    assert r.status_code == 409, r.text


def test_dismiss_review_clears_the_flag_without_a_new_decision(client):
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))

    r = client.post(f"/admin/organizations/{org_id}/dismiss-review", headers=auth(admin))
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "APPROVED"
    assert r.json()["review_due_at"] is None

    assert client.get("/admin/organizations/review-due", headers=auth(admin)).json() == []
    # Still decided, still cannot be silently re-decided again.
    r2 = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": "REJECTED", "reason": "x"},
        headers=auth(admin),
    )
    assert r2.status_code == 409, r2.text


def test_dismiss_review_with_nothing_pending_is_409(client):
    org_id, admin = _approved_org(client)
    r = client.post(f"/admin/organizations/{org_id}/dismiss-review", headers=auth(admin))
    assert r.status_code == 409, r.text


def test_dismiss_review_is_admin_only(client):
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))
    owner = login(client, "owner@ngo.org")
    r = client.post(f"/admin/organizations/{org_id}/dismiss-review", headers=auth(owner))
    assert r.status_code == 403, r.text


def test_request_review_on_unknown_org_is_404(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    admin = login(client, "ops@platform.org")
    r = client.post(
        "/admin/organizations/00000000-0000-0000-0000-000000000000/request-review",
        json={"reason": "x"},
        headers=auth(admin),
    )
    assert r.status_code == 404, r.text


def test_request_review_writes_an_audit_row(client):
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))

    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "org.review_requested", AuditEvent.org_id == org_id)
        ).all()
        assert len(events) == 1
        assert events[0].details["reason"] == "renewal"


def test_org_under_review_keeps_its_existing_privileges(client):
    """The key design guarantee: being flagged for review must not itself suspend an
    APPROVED org's ability to act (e.g. still visible as APPROVED to its own members)."""
    org_id, admin = _approved_org(client)
    client.post(f"/admin/organizations/{org_id}/request-review", json={"reason": "renewal"}, headers=auth(admin))

    owner = login(client, "owner@ngo.org")
    seen_by_owner = client.get(f"/orgs/{org_id}", headers=auth(owner)).json()
    assert seen_by_owner["verification_status"] == "APPROVED"
