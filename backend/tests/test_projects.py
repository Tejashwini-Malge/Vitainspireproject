from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token

GOOD_PROJECT = {"title": "Clean Water Wells", "summary": "Dig wells in drought-hit villages", "description": "Detail."}


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


def test_owner_creates_lists_and_updates_project(client):
    token, org = _owner_with_ngo(client)
    r = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "DRAFT" and body["title"] == GOOD_PROJECT["title"]

    r = client.get(f"/orgs/{org}/projects", headers=auth(token))
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.put(
        f"/orgs/{org}/projects/{body['id']}",
        json={**GOOD_PROJECT, "title": "Clean Water Wells, Phase 2"},
        headers=auth(token),
    )
    assert r.status_code == 200 and r.json()["title"] == "Clean Water Wells, Phase 2"

    with SessionLocal() as db:
        ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "project.created", AuditEvent.org_id == org))
        assert ev is not None


def test_csr_organization_cannot_create_projects(client):
    token = user_token(client, "csr@foundation.org")
    org = _create_org(client, token, org_type="CSR", name="Acme Foundation")
    r = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token))
    assert r.status_code == 422


def test_member_can_read_but_not_create_projects(client):
    owner, org = _owner_with_ngo(client)
    member = user_token(client, "member@ngo.org")
    client.post(f"/orgs/{org}/members", json={"email": "member@ngo.org", "role": "MEMBER"}, headers=auth(owner))
    assert client.get(f"/orgs/{org}/projects", headers=auth(member)).status_code == 200
    assert client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(member)).status_code == 403


def test_non_member_cannot_see_projects(client):
    owner, org = _owner_with_ngo(client)
    outsider = user_token(client, "outsider@x.org")
    assert client.get(f"/orgs/{org}/projects", headers=auth(outsider)).status_code == 404


def _admin_token(client):
    # _approve() already registered and promoted this account; logging in again is enough.
    return login(client, "ops@platform.org")


def test_publish_blocked_until_verified_then_appears_in_feed(client):
    from app.models import Document, DocumentReviewDecision, DocumentType, ReviewStatus
    from app.db import SessionLocal
    from sqlalchemy import select

    token, org = _owner_with_ngo(client)
    created = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token)).json()
    pid = created["id"]

    # First attempt - should fail because org needs verification AND documents
    _approve(client, org)  # Approve organization first

    r = client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))
    assert r.status_code == 403  # Now fails because documents are missing
    # The refusal names what is still outstanding rather than failing opaquely.
    detail = r.json()["detail"]
    assert "approved by a reviewer" in detail
    assert "Section 80G" in detail

    # Add all 5 required verified documents
    with SessionLocal() as db:
        # Get the user ID from the token
        from app.models import User
        user = db.scalar(select(User).where(User.email == "owner@ngo.org"))
        user_id = user.id

        for doc_type in [DocumentType.PAN, DocumentType.FCRA, DocumentType.SECTION_12A, DocumentType.SECTION_80G, DocumentType.REGISTRATION]:
            doc = Document(
                org_id=org,
                doc_type=doc_type,
                title=f"{doc_type.value} Certificate",
                original_filename=f"{doc_type.value}.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                sha256="abc123",
                storage_key=f"{doc_type.value}_key",
                uploaded_by_user_id=user_id,
            )
            db.add(doc)
            db.flush()

            decision = DocumentReviewDecision(
                document_id=doc.id,
                reviewer_user_id=user_id,
                decision=ReviewStatus.APPROVED,
                reason="Document verified",
                previous_status=ReviewStatus.PENDING_REVIEW,
            )
            db.add(decision)
        db.commit()

    # Submission now succeeds, but the project is only PENDING_REVIEW until admin acts.
    r = client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "PENDING_REVIEW"

    admin = _admin_token(client)
    r = client.post(f"/admin/projects/{pid}/decisions", json={"decision": "PUBLISHED"}, headers=auth(admin))
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED"

    # NGO profile must also be published for the org to appear publicly.
    client.put(
        f"/orgs/{org}/profile",
        json={"mission": "Water for all", "sectors": ["Water"], "geographies": ["Odisha"]},
        headers=auth(token),
    )
    client.post(f"/orgs/{org}/profile/publish", headers=auth(token))

    feed = client.get("/public/feed")
    assert feed.status_code == 200
    assert any(p["id"] == pid for p in feed.json())

    client.post(f"/orgs/{org}/projects/{pid}/unpublish", headers=auth(token))
    feed = client.get("/public/feed")
    assert not any(p["id"] == pid for p in feed.json())


def test_admin_can_request_changes_instead_of_publishing(client):
    from app.models import DocumentType

    token, org = _owner_with_ngo(client)
    pid = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token)).json()["id"]
    _approve(client, org)
    _approve_docs(
        client, org, "owner@ngo.org",
        [DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A, DocumentType.SECTION_80G],
    )
    client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))

    admin = _admin_token(client)
    r = client.post(
        f"/admin/projects/{pid}/decisions",
        json={"decision": "CHANGES_REQUESTED", "reason": "Add more detail on impact."},
        headers=auth(admin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CHANGES_REQUESTED"
    assert r.json()["review_feedback"] == "Add more detail on impact."

    # The NGO can edit again while in CHANGES_REQUESTED and resubmit.
    client.put(f"/orgs/{org}/projects/{pid}", json=GOOD_PROJECT, headers=auth(token))
    r = client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))
    assert r.status_code == 200 and r.json()["status"] == "PENDING_REVIEW"
    assert r.json()["review_feedback"] is None


def test_project_review_queue_and_decisions_are_admin_only(client):
    from app.models import DocumentType

    token, org = _owner_with_ngo(client)
    pid = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token)).json()["id"]
    _approve(client, org)
    _approve_docs(
        client, org, "owner@ngo.org",
        [DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A, DocumentType.SECTION_80G],
    )
    client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))

    assert client.get("/admin/projects/queue", headers=auth(token)).status_code == 403
    assert client.post(f"/admin/projects/{pid}/decisions", json={"decision": "PUBLISHED"}, headers=auth(token)).status_code == 403

    admin = _admin_token(client)
    queue = client.get("/admin/projects/queue", headers=auth(admin)).json()
    assert any(item["id"] == pid for item in queue)


def test_cannot_decide_a_project_twice(client):
    from app.models import DocumentType

    token, org = _owner_with_ngo(client)
    pid = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token)).json()["id"]
    _approve(client, org)
    _approve_docs(
        client, org, "owner@ngo.org",
        [DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A, DocumentType.SECTION_80G],
    )
    client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))
    admin = _admin_token(client)
    assert client.post(f"/admin/projects/{pid}/decisions", json={"decision": "PUBLISHED"}, headers=auth(admin)).status_code == 200
    r = client.post(f"/admin/projects/{pid}/decisions", json={"decision": "PUBLISHED"}, headers=auth(admin))
    assert r.status_code == 409


def test_public_feed_excludes_projects_of_unverified_ngo(client):
    token, org = _owner_with_ngo(client)
    client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token))
    feed = client.get("/public/feed")
    assert feed.status_code == 200 and feed.json() == []


def _approve_docs(client, org, owner_email, doc_types):
    """Insert approved compliance documents of the given types for an organisation."""
    from app.db import SessionLocal
    from app.models import Document, DocumentReviewDecision, ReviewStatus, User
    from sqlalchemy import select

    with SessionLocal() as db:
        user_id = db.scalar(select(User).where(User.email == owner_email)).id
        for doc_type in doc_types:
            doc = Document(
                org_id=org,
                doc_type=doc_type,
                title=f"{doc_type.value} Certificate",
                original_filename=f"{doc_type.value}.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                sha256=f"sha-{doc_type.value}",
                storage_key=f"{doc_type.value}_key",
                uploaded_by_user_id=user_id,
            )
            db.add(doc)
            db.flush()
            db.add(
                DocumentReviewDecision(
                    document_id=doc.id,
                    reviewer_user_id=user_id,
                    decision=ReviewStatus.APPROVED,
                    reason="Document verified",
                    previous_status=ReviewStatus.PENDING_REVIEW,
                )
            )
        db.commit()


def test_publish_does_not_require_fcra(client):
    """FCRA applies only to organisations receiving foreign contributions.

    A domestic NGO can never obtain one, so requiring it would permanently block
    publishing. The other four documents are required; FCRA must not be.
    """
    from app.models import DocumentType

    token, org = _owner_with_ngo(client)
    pid = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token)).json()["id"]
    _approve(client, org)

    _approve_docs(
        client,
        org,
        "owner@ngo.org",
        [
            DocumentType.PAN,
            DocumentType.REGISTRATION,
            DocumentType.SECTION_12A,
            DocumentType.SECTION_80G,
        ],
    )

    r = client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PENDING_REVIEW"


def test_publish_still_blocked_when_a_required_document_is_missing(client):
    """Dropping FCRA must not weaken the rest of the gate."""
    from app.models import DocumentType

    token, org = _owner_with_ngo(client)
    pid = client.post(f"/orgs/{org}/projects", json=GOOD_PROJECT, headers=auth(token)).json()["id"]
    _approve(client, org)

    # Everything except Section 80G.
    _approve_docs(
        client,
        org,
        "owner@ngo.org",
        [DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A],
    )

    r = client.post(f"/orgs/{org}/projects/{pid}/submit-for-review", headers=auth(token))
    assert r.status_code == 403, r.text
    assert "Section 80G" in r.json()["detail"]
