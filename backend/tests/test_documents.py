from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal, engine
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token

PDF = b"%PDF-1.7\n% registration certificate\n" + b"0" * 200
PDF_OTHER = b"%PDF-1.7\n% a different scan\n" + b"1" * 200


def _ngo_owner(client, email="owner@ngo.org"):
    token = user_token(client, email)
    r = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(token))
    return token, r.json()["id"]


def _upload(client, token, org, *, content=PDF, filename="reg.pdf", mime="application/pdf", doc_type="REGISTRATION",
            valid_until=None):
    data = {"doc_type": doc_type, "title": "Registration certificate"}
    if valid_until:
        data["valid_until"] = valid_until
    return client.post(
        f"/orgs/{org}/documents",
        data=data,
        files={"file": (filename, content, mime)},
        headers=auth(token),
    )


def _admin(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def test_upload_returns_metadata_but_never_storage_location(client, storage_dir):
    token, org = _ngo_owner(client)
    r = _upload(client, token, org, valid_until="2030-03-31")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["review_status"] == "PENDING_REVIEW"
    assert body["valid_until_stated"] == "2030-03-31"
    assert body["latest_decision"] is None
    assert "storage_key" not in body and "storage_dir" not in str(body)
    assert len(body["sha256"]) == 64
    # The file exists in private storage, not under a name chosen by the uploader.
    stored = list(storage_dir.rglob("*"))
    assert any(p.is_file() and p.read_bytes() == PDF for p in stored)


def test_upload_rejects_disguised_file(client):
    token, org = _ngo_owner(client)
    r = _upload(client, token, org, content=b"<script>alert(1)</script>", filename="reg.pdf")
    assert r.status_code == 422
    assert "not a PDF" in r.json()["detail"]


def test_upload_rejects_wrong_declared_type(client):
    token, org = _ngo_owner(client)
    r = _upload(client, token, org, content=PDF, mime="image/png")
    assert r.status_code == 422


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    token, org = _ngo_owner(client)
    r = _upload(client, token, org)
    assert r.status_code == 422 and "larger than" in r.json()["detail"]


def test_same_file_twice_in_one_org_is_refused(client):
    token, org = _ngo_owner(client)
    assert _upload(client, token, org).status_code == 201
    r = _upload(client, token, org, filename="again.pdf")
    assert r.status_code == 409


def test_upload_sanitises_hostile_filename(client):
    token, org = _ngo_owner(client)
    r = _upload(client, token, org, filename="../../../etc/passwd.pdf", content=PDF_OTHER)
    assert r.status_code == 201
    assert r.json()["original_filename"] == "passwd.pdf"


def test_non_ngo_organization_cannot_collect_compliance_documents(client):
    token = user_token(client, "csr@foundation.org")
    org = client.post("/orgs", json={"name": "Acme", "org_type": "CSR"}, headers=auth(token)).json()["id"]
    r = _upload(client, token, org)
    assert r.status_code == 422


def test_member_cannot_upload_but_can_view(client):
    owner, org = _ngo_owner(client)
    assert _upload(client, owner, org).status_code == 201
    member = user_token(client, "member@ngo.org")
    client.post(f"/orgs/{org}/members", json={"email": "member@ngo.org", "role": "MEMBER"}, headers=auth(owner))
    assert _upload(client, member, org, content=PDF_OTHER).status_code == 403
    assert client.get(f"/orgs/{org}/documents", headers=auth(member)).status_code == 200


def test_outsider_cannot_list_upload_or_download(client):
    owner, org = _ngo_owner(client)
    doc_id = _upload(client, owner, org).json()["id"]
    outsider = user_token(client, "outsider@x.org")
    assert client.get(f"/orgs/{org}/documents", headers=auth(outsider)).status_code == 404
    assert _upload(client, outsider, org, content=PDF_OTHER).status_code == 404
    assert client.get(f"/orgs/{org}/documents/{doc_id}/download", headers=auth(outsider)).status_code == 404


def test_document_id_from_another_org_is_not_reachable_through_own_org(client):
    owner_a, org_a = _ngo_owner(client, "a@ngo.org")
    doc_a = _upload(client, owner_a, org_a).json()["id"]
    owner_b = user_token(client, "b@ngo.org")
    org_b = client.post("/orgs", json={"name": "Other NGO", "org_type": "NGO"}, headers=auth(owner_b)).json()["id"]
    # Owner B uses their own org in the path with owner A's document id: must be 404, not the document.
    r = client.get(f"/orgs/{org_b}/documents/{doc_a}/download", headers=auth(owner_b))
    assert r.status_code == 404


def test_download_returns_exact_bytes_with_safe_headers_and_is_audited(client):
    token, org = _ngo_owner(client)
    doc_id = _upload(client, token, org).json()["id"]
    r = client.get(f"/orgs/{org}/documents/{doc_id}/download", headers=auth(token))
    assert r.status_code == 200
    assert r.content == PDF
    assert r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, no-store"
    with SessionLocal() as db:
        ev = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "document.downloaded", AuditEvent.resource_id == doc_id)
        )
        assert ev is not None and ev.actor_user_id is not None


def test_reviewer_queue_is_admin_only(client):
    owner, org = _ngo_owner(client)
    _upload(client, owner, org)
    assert client.get("/admin/documents/queue", headers=auth(owner)).status_code == 403


def test_approve_then_decision_is_final_and_history_is_kept(client):
    owner, org = _ngo_owner(client)
    doc_id = _upload(client, owner, org).json()["id"]
    admin = _admin(client)

    queue = client.get("/admin/documents/queue", headers=auth(admin)).json()
    assert [q["id"] for q in queue] == [doc_id]
    assert queue[0]["org_name"] == "Shanti Trust"

    blank = client.post(f"/admin/documents/{doc_id}/decisions", json={"decision": "APPROVED", "reason": "   "}, headers=auth(admin))
    assert blank.status_code == 422

    r = client.post(
        f"/admin/documents/{doc_id}/decisions",
        json={"decision": "APPROVED", "reason": "Registration number matches the state registry extract"},
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text
    assert r.json()["previous_status"] == "PENDING_REVIEW" and r.json()["decision"] == "APPROVED"

    again = client.post(f"/admin/documents/{doc_id}/decisions", json={"decision": "REJECTED", "reason": "changed"}, headers=auth(admin))
    assert again.status_code == 409

    docs = client.get(f"/orgs/{org}/documents", headers=auth(owner)).json()
    assert docs[0]["review_status"] == "APPROVED"
    assert docs[0]["latest_decision"]["reason"].startswith("Registration number")

    history = client.get(f"/orgs/{org}/documents/{doc_id}/decisions", headers=auth(owner)).json()
    assert len(history) == 1


def test_rejection_reason_is_visible_to_the_organization(client):
    owner, org = _ngo_owner(client)
    doc_id = _upload(client, owner, org).json()["id"]
    admin = _admin(client)
    client.post(
        f"/admin/documents/{doc_id}/decisions",
        json={"decision": "REJECTED", "reason": "The scan is cropped; the registration number is not legible"},
        headers=auth(admin),
    )
    docs = client.get(f"/orgs/{org}/documents", headers=auth(owner)).json()
    assert docs[0]["review_status"] == "REJECTED"
    assert "not legible" in docs[0]["latest_decision"]["reason"]


def test_reviewer_cannot_decide_documents_of_own_organization(client):
    admin_token = user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org = client.post("/orgs", json={"name": "Platform Test NGO", "org_type": "NGO"}, headers=auth(admin_token)).json()["id"]
    doc_id = _upload(client, admin_token, org).json()["id"]
    admin = login(client, "ops@platform.org")

    queue = client.get("/admin/documents/queue", headers=auth(admin)).json()
    assert doc_id not in [q["id"] for q in queue]
    r = client.post(f"/admin/documents/{doc_id}/decisions", json={"decision": "APPROVED", "reason": "self-review"}, headers=auth(admin))
    assert r.status_code == 403
    assert client.get(f"/admin/documents/{doc_id}/download", headers=auth(admin)).status_code == 403


def test_reviewer_cannot_verify_own_organization(client):
    admin_token = user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    org = client.post("/orgs", json={"name": "Self NGO", "org_type": "NGO"}, headers=auth(admin_token)).json()["id"]
    r = client.post(f"/admin/organizations/{org}/verification", json={"decision": "APPROVED"}, headers=auth(admin_token))
    assert r.status_code == 403


def test_reviewer_download_is_audited_with_reviewer_identity(client):
    owner, org = _ngo_owner(client)
    doc_id = _upload(client, owner, org).json()["id"]
    admin = _admin(client)
    r = client.get(f"/admin/documents/{doc_id}/download", headers=auth(admin))
    assert r.status_code == 200 and r.content == PDF
    with SessionLocal() as db:
        ev = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "document.downloaded_by_reviewer", AuditEvent.resource_id == doc_id
            )
        )
        assert ev is not None and ev.actor_user_id is not None


def test_public_profile_shows_approved_document_types_only(client):
    from tests.test_profiles import GOOD_PROFILE

    owner, org = _ngo_owner(client)
    client.put(f"/orgs/{org}/profile", json=GOOD_PROFILE, headers=auth(owner))
    approved_id = _upload(client, owner, org, doc_type="SECTION_12A", content=PDF).json()["id"]
    _upload(client, owner, org, doc_type="PAN", content=PDF_OTHER)  # stays pending and private
    admin = _admin(client)
    client.post(f"/admin/documents/{approved_id}/decisions", json={"decision": "APPROVED", "reason": "Order checked"}, headers=auth(admin))
    # Verify the organization and publish, so the public page is reachable.
    client.post(f"/admin/organizations/{org}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    client.post(f"/orgs/{org}/profile/publish", headers=auth(owner))

    body = client.get(f"/public/ngos/{org}").json()
    assert [d["doc_type"] for d in body["reviewed_documents"]] == ["SECTION_12A"]
    flat = str(body)
    assert "reg.pdf" not in flat and "sha256" not in flat and "storage" not in flat and "PAN" not in flat


def test_review_history_is_append_only_at_database_level(client):
    owner, org = _ngo_owner(client)
    doc_id = _upload(client, owner, org).json()["id"]
    admin = _admin(client)
    client.post(f"/admin/documents/{doc_id}/decisions", json={"decision": "APPROVED", "reason": "ok"}, headers=auth(admin))

    import pytest
    from sqlalchemy.exc import DBAPIError

    with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("UPDATE document_review_decisions SET reason = 'edited'"))
    with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("DELETE FROM document_review_decisions"))


def test_audit_log_is_append_only_at_database_level(client):
    import pytest
    from sqlalchemy.exc import DBAPIError

    user_token(client, "anyone@x.org")
    with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("UPDATE audit_events SET action = 'nothing.happened'"))
    with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("DELETE FROM audit_events"))
    with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("TRUNCATE audit_events"))
