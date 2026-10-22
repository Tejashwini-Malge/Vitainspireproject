"""Reviewer assist for a single compliance document.

The assist must cite a page for every finding, never decide anything, and be honest
when it cannot read the file -- a scan with no text layer is the common real case.
"""

from tests.helpers import auth, login, make_platform_admin, make_pdf, user_token


def _pdf(pages_text: list[str]) -> bytes:
    return make_pdf(pages_text)


def _blank_pdf(page_count: int) -> bytes:
    """Real pages with no text layer -- what a scan looks like to pypdf."""
    return make_pdf([""] * page_count)


def _org(client, token, name="Shanti Trust"):
    return client.post("/orgs", json={"name": name, "org_type": "NGO"},
                       headers=auth(token)).json()["id"]


def _upload(client, token, org, doc_type, content, title="Certificate"):
    r = client.post(
        f"/orgs/{org}/documents",
        files={"file": ("doc.pdf", content, "application/pdf")},
        data={"doc_type": doc_type, "title": title},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _admin(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def test_assist_cites_a_page_for_every_finding(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    content = _pdf([
        "INCOME TAX DEPARTMENT\nPermanent Account Number\nAABCS1429B",
        "This certificate is valid up to 31/03/2030",
    ])
    doc = _upload(client, token, org, "PAN", content)
    admin = _admin(client)

    r = client.get(f"/admin/documents/{doc}/assist", headers=auth(admin))
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["page_count"] == 2
    assert body["text_extractable"] is True
    assert body["generated_by"] == "rules"
    assert body["disclaimer"]

    pans = [f for f in body["findings"] if f["label"] == "PAN"]
    assert pans and pans[0]["value"] == "AABCS1429B"
    assert pans[0]["page"] == 1, "PAN was on page 1 and must be cited as page 1"

    # Every finding carries a page, and every page cited appears in sources.
    for f in body["findings"]:
        assert f["page"] >= 1
        assert f"document:{doc}:page:{f['page']}" in body["sources"]


def test_scanned_document_is_reported_not_silently_empty(client):
    """A scan has pages but no text. The reviewer must be told to read it themselves."""
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    doc = _upload(client, token, org, "REGISTRATION", _blank_pdf(3))
    admin = _admin(client)

    body = client.get(f"/admin/documents/{doc}/assist", headers=auth(admin)).json()

    assert body["page_count"] == 3
    assert body["text_extractable"] is False
    assert body["findings"] == []
    assert any("scan" in f.lower() for f in body["flags"])
    assert any("manual" in f.lower() for f in body["flags"])


def test_assist_flags_a_document_that_does_not_match_its_declared_type(client):
    """Filed as PAN but containing no PAN number is exactly what a reviewer needs told."""
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    doc = _upload(client, token, org, "PAN", _pdf(["This is a letter about something else entirely."]))
    admin = _admin(client)

    body = client.get(f"/admin/documents/{doc}/assist", headers=auth(admin)).json()
    assert any("no PAN-formatted number" in f for f in body["flags"])


def test_assist_is_read_only_and_does_not_change_review_status(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    doc = _upload(client, token, org, "PAN", _pdf(["AABCS1429B"]))
    admin = _admin(client)

    before = client.get(f"/orgs/{org}/documents", headers=auth(token)).json()[0]["review_status"]
    client.get(f"/admin/documents/{doc}/assist", headers=auth(admin))
    after = client.get(f"/orgs/{org}/documents", headers=auth(token)).json()[0]["review_status"]
    assert before == after == "PENDING_REVIEW"


def test_assist_requires_platform_admin(client):
    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    doc = _upload(client, token, org, "PAN", _pdf(["AABCS1429B"]))

    # The uploading NGO is not a reviewer.
    assert client.get(f"/admin/documents/{doc}/assist", headers=auth(token)).status_code == 403


def test_reviewer_cannot_assist_on_their_own_organisations_document(client):
    """Same conflict-of-interest rule as download and decide."""
    admin_token = user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    admin_token = login(client, "ops@platform.org")
    own_org = _org(client, admin_token, name="Reviewer's Own Trust")
    doc = _upload(client, admin_token, own_org, "PAN", _pdf(["AABCS1429B"]))

    r = client.get(f"/admin/documents/{doc}/assist", headers=auth(admin_token))
    assert r.status_code == 403, r.text


def test_assist_access_is_audited(client):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AuditEvent

    token = user_token(client, "owner@ngo.org")
    org = _org(client, token)
    doc = _upload(client, token, org, "PAN", _pdf(["AABCS1429B"]))
    admin = _admin(client)
    client.get(f"/admin/documents/{doc}/assist", headers=auth(admin))

    with SessionLocal() as db:
        ev = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "document.assist_viewed_by_reviewer",
                AuditEvent.resource_id == doc,
            )
        )
        assert ev is not None, "reading private material must leave an audit trail"
        assert ev.actor_user_id is not None
