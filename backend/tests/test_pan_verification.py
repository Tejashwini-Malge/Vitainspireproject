from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AuditEvent
from tests.helpers import auth, login, make_platform_admin, user_token

PDF = b"%PDF-1.7\n% pan card scan\n" + b"0" * 200
PDF_OTHER = b"%PDF-1.7\n% a different scan\n" + b"1" * 200
VALID_PAN = "ABCDE1234F"


def _donor(client, email="donor@example.com"):
    return user_token(client, email)


def _upload(client, token, *, pan=VALID_PAN, content=PDF, filename="pan.pdf", mime="application/pdf"):
    return client.post(
        "/me/pan-verification",
        data={"pan_number": pan},
        files={"file": (filename, content, mime)},
        headers=auth(token),
    )


def _admin(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def test_upload_returns_metadata_but_never_storage_location(client, storage_dir):
    token = _donor(client)
    r = _upload(client, token)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["review_status"] == "PENDING_REVIEW"
    assert body["pan_number"] == VALID_PAN
    assert body["latest_decision"] is None
    assert "storage_key" not in body
    stored = list(storage_dir.rglob("*"))
    assert any(p.is_file() and p.read_bytes() == PDF for p in stored)


def test_upload_rejects_malformed_pan(client):
    token = _donor(client)
    r = _upload(client, token, pan="not-a-pan")
    assert r.status_code == 422
    assert "ABCDE1234F" in r.json()["detail"]


def test_pan_is_normalised_to_uppercase(client):
    token = _donor(client)
    r = _upload(client, token, pan="abcde1234f")
    assert r.status_code == 201
    assert r.json()["pan_number"] == VALID_PAN


def test_upload_rejects_disguised_file(client):
    token = _donor(client)
    r = _upload(client, token, content=b"<script>alert(1)</script>")
    assert r.status_code == 422
    assert "not a PDF" in r.json()["detail"]


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    token = _donor(client)
    r = _upload(client, token)
    assert r.status_code == 422 and "larger than" in r.json()["detail"]


def test_same_file_twice_for_same_user_is_refused(client):
    token = _donor(client)
    assert _upload(client, token).status_code == 201
    r = _upload(client, token, filename="again.pdf")
    assert r.status_code == 409


def test_status_reflects_latest_submission(client):
    token = _donor(client)
    r = client.get("/me/pan-verification/status", headers=auth(token))
    assert r.status_code == 200
    assert r.json() == {"verified": False, "status": None, "pan_number": None}

    _upload(client, token)
    r = client.get("/me/pan-verification/status", headers=auth(token))
    body = r.json()
    assert body["verified"] is False
    assert body["status"] == "PENDING_REVIEW"
    assert body["pan_number"] == VALID_PAN


def test_user_cannot_see_another_users_submissions(client):
    a = _donor(client, "a@example.com")
    _upload(client, a)
    b = _donor(client, "b@example.com")
    assert client.get("/me/pan-verification", headers=auth(b)).json() == []


def test_queue_and_decisions_are_admin_only(client):
    donor = _donor(client)
    _upload(client, donor)
    assert client.get("/admin/pan-verifications/queue", headers=auth(donor)).status_code == 403


def test_admin_approves_submission_and_status_flips_verified(client):
    donor = _donor(client)
    sub_id = _upload(client, donor).json()["id"]
    admin = _admin(client)

    queue = client.get("/admin/pan-verifications/queue", headers=auth(admin)).json()
    assert any(item["id"] == sub_id for item in queue)

    r = client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "APPROVED", "reason": "Matches the uploaded scan"},
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text
    assert r.json()["decision"] == "APPROVED"

    status_out = client.get("/me/pan-verification/status", headers=auth(donor)).json()
    assert status_out == {"verified": True, "status": "APPROVED", "pan_number": VALID_PAN}


def test_decision_requires_a_reason(client):
    donor = _donor(client)
    sub_id = _upload(client, donor).json()["id"]
    admin = _admin(client)
    r = client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "REJECTED", "reason": "  "},
        headers=auth(admin),
    )
    assert r.status_code == 422


def test_decided_submission_cannot_be_decided_again(client):
    donor = _donor(client)
    sub_id = _upload(client, donor).json()["id"]
    admin = _admin(client)
    assert client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "REJECTED", "reason": "PAN does not match scan"},
        headers=auth(admin),
    ).status_code == 201
    r = client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "APPROVED", "reason": "second look"},
        headers=auth(admin),
    )
    assert r.status_code == 409


def test_admin_cannot_review_their_own_submission(client):
    admin = _admin(client)
    sub_id = _upload(client, admin).json()["id"]
    r = client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "APPROVED", "reason": "self review"},
        headers=auth(admin),
    )
    assert r.status_code == 403
    assert client.get("/admin/pan-verifications/queue", headers=auth(admin)).json() == []


def test_admin_download_returns_exact_bytes_and_is_audited(client):
    donor = _donor(client)
    sub_id = _upload(client, donor).json()["id"]
    admin = _admin(client)
    r = client.get(f"/admin/pan-verifications/{sub_id}/download", headers=auth(admin))
    assert r.status_code == 200
    assert r.content == PDF
    assert r.headers["content-disposition"].startswith("attachment;")
    with SessionLocal() as db:
        ev = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "pan_verification.downloaded_by_reviewer", AuditEvent.resource_id == sub_id
            )
        )
        assert ev is not None and ev.actor_user_id is not None


def test_rejecting_lets_donor_resubmit_with_a_new_file(client):
    donor = _donor(client)
    sub_id = _upload(client, donor).json()["id"]
    admin = _admin(client)
    client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "REJECTED", "reason": "blurry scan"},
        headers=auth(admin),
    )
    r = _upload(client, donor, content=PDF_OTHER, filename="pan-retake.pdf")
    assert r.status_code == 201
    subs = client.get("/me/pan-verification", headers=auth(donor)).json()
    assert len(subs) == 2
