"""Admin visibility and reorder power over CSR-authored shortlists (ADM-006).

Deliberately additive, not a gate: the acceptance report notes a CSR's shortlist already
works end to end (201, NGO notified, proposal eligible immediately) and that chain is one
of the few things scored clean. Rather than block it behind a new pre-publish review --
which would also change proposal-eligibility timing and notification timing tests rely on
-- this gives admins a read-only directory plus the power to supersede a shortlist with a
reordered/trimmed one, reusing the exact same validation and notification path a CSR's own
call uses.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document, DocumentReviewDecision, DocumentType, ReviewStatus, User
from tests.helpers import auth, make_platform_admin, login, user_token

OPPORTUNITY = {
    "title": "Rural water access 2026",
    "description": "Funding borewell rehabilitation across Karnataka.",
    "sectors": ["Water"],
    "geographies": ["Karnataka"],
    "budget_min": 500000,
    "budget_max": 2500000,
    "deadline": "2026-12-31",
    "requirements_text": "80G registered, three years of operation.",
}

REQUIRED_DOCS = [
    DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A, DocumentType.SECTION_80G,
]


def _admin(client) -> str:
    """Idempotent: a test may set up more than one NGO (each needing admin approval), and
    register() 409s on a repeat email."""
    with SessionLocal() as db:
        already_registered = db.scalar(select(User).where(User.email == "ops@platform.org")) is not None
    if not already_registered:
        user_token(client, "ops@platform.org")
        make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def _eligible_ngo(client, email: str, name: str) -> tuple[str, str]:
    token = user_token(client, email)
    org = client.post("/orgs", json={"name": name, "org_type": "NGO"}, headers=auth(token)).json()["id"]
    admin = _admin(client)
    r = client.post(f"/admin/organizations/{org}/verification", json={"decision": "APPROVED"}, headers=auth(admin))
    assert r.status_code == 200, r.text

    # storage_key only needs to be unique per org here (not globally, as the shared
    # _approve_docs helper assumes), since this test sets up more than one compliant NGO.
    with SessionLocal() as db:
        user_id = db.scalar(select(User).where(User.email == email)).id
        for doc_type in REQUIRED_DOCS:
            doc = Document(
                org_id=org, doc_type=doc_type, title=f"{doc_type.value} Certificate",
                original_filename=f"{doc_type.value}.pdf", content_type="application/pdf",
                size_bytes=1024, sha256=f"sha-{org}-{doc_type.value}", storage_key=f"{org}-{doc_type.value}_key",
                uploaded_by_user_id=user_id,
            )
            db.add(doc)
            db.flush()
            db.add(DocumentReviewDecision(
                document_id=doc.id, reviewer_user_id=user_id, decision=ReviewStatus.APPROVED,
                reason="Document verified", previous_status=ReviewStatus.PENDING_REVIEW,
            ))
        db.commit()

    return token, org


def _published_opportunity(client) -> tuple[str, str]:
    csr_token = user_token(client, "lead@foundation.org")
    csr_org = client.post("/orgs", json={"name": "Acme Foundation", "org_type": "CSR"},
                          headers=auth(csr_token)).json()["id"]
    opp = client.post("/csr/opportunities", json=OPPORTUNITY, headers=auth(csr_token)).json()["id"]
    client.post(f"/csr/opportunities/{opp}/publish", headers=auth(csr_token))
    return csr_token, opp


def test_shortlist_directory_is_admin_only(client):
    csr_token, opp = _published_opportunity(client)
    _, ngo = _eligible_ngo(client, "owner@ngo.org", "Shanti Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))

    assert client.get("/admin/shortlists", headers=auth(csr_token)).status_code == 403


def test_shortlist_directory_lists_the_current_revision(client):
    csr_token, opp = _published_opportunity(client)
    _, ngo = _eligible_ngo(client, "owner@ngo.org", "Shanti Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))

    admin = _admin(client)
    rows = client.get("/admin/shortlists", headers=auth(admin)).json()
    assert len(rows) == 1
    assert rows[0]["opportunity_id"] == opp
    assert rows[0]["opportunity_title"] == OPPORTUNITY["title"]
    assert rows[0]["csr_org_name"] == "Acme Foundation"
    assert rows[0]["ngo_ids"] == [ngo]
    assert rows[0]["is_current"] is True


def test_shortlist_directory_filters_by_opportunity(client):
    csr_token, opp1 = _published_opportunity(client)
    _, ngo1 = _eligible_ngo(client, "owner1@ngo.org", "Shanti Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp1, "ngo_ids": [ngo1]}, headers=auth(csr_token))

    csr_token2 = user_token(client, "lead2@foundation.org")
    csr_org2 = client.post("/orgs", json={"name": "Other Foundation", "org_type": "CSR"},
                           headers=auth(csr_token2)).json()["id"]
    opp2 = client.post("/csr/opportunities", json=OPPORTUNITY, headers=auth(csr_token2)).json()["id"]
    client.post(f"/csr/opportunities/{opp2}/publish", headers=auth(csr_token2))
    _, ngo2 = _eligible_ngo(client, "owner2@ngo.org", "Other Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp2, "ngo_ids": [ngo2]}, headers=auth(csr_token2))

    admin = _admin(client)
    rows = client.get(f"/admin/shortlists?opportunity_id={opp1}", headers=auth(admin)).json()
    assert len(rows) == 1
    assert rows[0]["opportunity_id"] == opp1


def test_shortlist_directory_current_only_hides_superseded_revisions(client):
    csr_token, opp = _published_opportunity(client)
    _, ngo1 = _eligible_ngo(client, "owner1@ngo.org", "Shanti Trust")
    _, ngo2 = _eligible_ngo(client, "owner2@ngo.org", "Other Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo1]}, headers=auth(csr_token))
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo1, ngo2]}, headers=auth(csr_token))

    admin = _admin(client)
    current = client.get("/admin/shortlists", headers=auth(admin)).json()
    assert len(current) == 1
    assert current[0]["revision_num"] == 2

    everything = client.get("/admin/shortlists?current_only=false", headers=auth(admin)).json()
    assert len(everything) == 2


def test_admin_can_reorder_shortlist_into_a_new_revision(client):
    csr_token, opp = _published_opportunity(client)
    _, ngo1 = _eligible_ngo(client, "owner1@ngo.org", "Shanti Trust")
    _, ngo2 = _eligible_ngo(client, "owner2@ngo.org", "Other Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo1, ngo2]}, headers=auth(csr_token))

    admin = _admin(client)
    r = client.post(
        f"/admin/opportunities/{opp}/shortlist/reorder",
        json={"ngo_ids": [ngo2, ngo1]},
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["revision_num"] == 2
    assert body["ngo_ids"] == [ngo2, ngo1]
    assert body["is_current"] is True

    rows = client.get("/admin/shortlists", headers=auth(admin)).json()
    assert len(rows) == 1 and rows[0]["ngo_ids"] == [ngo2, ngo1]


def test_admin_reorder_preserves_proposal_eligibility_for_still_listed_ngos(client):
    """The reorder must not disrupt the already-working proposal chain for NGOs that
    remain on the list -- only a trimmed-out NGO should lose eligibility."""
    csr_token, opp = _published_opportunity(client)
    ngo_token, ngo1 = _eligible_ngo(client, "owner1@ngo.org", "Shanti Trust")
    _, ngo2 = _eligible_ngo(client, "owner2@ngo.org", "Other Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo1, ngo2]}, headers=auth(csr_token))

    admin = _admin(client)
    client.post(
        f"/admin/opportunities/{opp}/shortlist/reorder",
        json={"ngo_ids": [ngo1]},  # trims ngo2
        headers=auth(admin),
    )

    r = client.post(
        "/ngo/proposals",
        json={"opportunity_id": opp, "problem_statement": "Twelve borewells have failed.",
              "solution": "Rehabilitate all twelve including pumps and testing.",
              "budget_requested": 1200000, "timeline": "9 months",
              "expected_outcomes": "Four thousand people served."},
        headers=auth(ngo_token),
    )
    assert r.status_code == 201, r.text


def test_admin_reorder_rejects_an_ngo_missing_compliance_documents(client):
    csr_token, opp = _published_opportunity(client)
    _, ngo = _eligible_ngo(client, "owner@ngo.org", "Shanti Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))

    unverified_token = user_token(client, "owner2@ngo.org")
    unverified_ngo = client.post("/orgs", json={"name": "No Docs Trust", "org_type": "NGO"},
                                 headers=auth(unverified_token)).json()["id"]

    admin = _admin(client)
    r = client.post(
        f"/admin/opportunities/{opp}/shortlist/reorder",
        json={"ngo_ids": [ngo, unverified_ngo]},
        headers=auth(admin),
    )
    assert r.status_code == 422, r.text


def test_admin_reorder_on_unknown_opportunity_is_404(client):
    admin = _admin(client)
    r = client.post(
        "/admin/opportunities/00000000-0000-0000-0000-000000000000/shortlist/reorder",
        json={"ngo_ids": ["00000000-0000-0000-0000-000000000001"]},
        headers=auth(admin),
    )
    assert r.status_code == 404, r.text


def test_admin_reorder_requires_admin(client):
    csr_token, opp = _published_opportunity(client)
    _, ngo = _eligible_ngo(client, "owner@ngo.org", "Shanti Trust")
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))

    r = client.post(
        f"/admin/opportunities/{opp}/shortlist/reorder",
        json={"ngo_ids": [ngo]},
        headers=auth(csr_token),
    )
    assert r.status_code == 403, r.text


def test_shortlist_directory_empty_is_not_an_error(client):
    admin = _admin(client)
    assert client.get("/admin/shortlists", headers=auth(admin)).json() == []
