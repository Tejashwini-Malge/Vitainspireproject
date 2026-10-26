"""CSR profile (CIN, CSR budget, Schedule VII categories) and the FCRA-required flag on
opportunities, closing DON-001, ADM-005, and AI-004 from the 2026-10-25 acceptance report:
CSR organisations previously had no profile at all, and an opportunity's FCRA requirement
was free text that fit scoring never read.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentReviewDecision,
    DocumentType,
    NgoProfile,
    Organization,
    OrgType,
    ProfileStatus,
    ReviewStatus,
    User,
    VerificationStatus,
)
from app.security import hash_password
from tests.helpers import auth, user_token

GOOD_CSR_PROFILE = {
    "mission": "Fund digital-skills programs across underserved districts",
    "about": "A corporate foundation active since 2018.",
    "website": "https://example-csr.org",
    "cin": "U12345MH2018PLC123456",
    "csr_budget_minor": 50_000_000,
    "schedule_vii_categories": ["education", "skill development"],
}


def _csr_org(client, token, name="Acme Foundation") -> str:
    r = client.post("/orgs", json={"name": name, "org_type": "CSR"}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ngo_org(client, token, name="Shanti Trust") -> str:
    r = client.post("/orgs", json={"name": name, "org_type": "NGO"}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --------------------------------------------------------------------------- CSR profile

def test_csr_profile_is_empty_until_saved(client):
    token = user_token(client, "owner@csr.org")
    org = _csr_org(client, token)
    r = client.get(f"/orgs/{org}/csr-profile", headers=auth(token))
    assert r.status_code == 200 and r.json() is None


def test_csr_profile_can_be_saved_and_persists(client):
    token = user_token(client, "owner@csr.org")
    org = _csr_org(client, token)

    r = client.put(f"/orgs/{org}/csr-profile", json=GOOD_CSR_PROFILE, headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cin"] == "U12345MH2018PLC123456"
    assert body["csr_budget_minor"] == 50_000_000
    assert body["schedule_vii_categories"] == ["education", "skill development"]

    got = client.get(f"/orgs/{org}/csr-profile", headers=auth(token))
    assert got.status_code == 200
    assert got.json()["cin"] == "U12345MH2018PLC123456"


def test_csr_profile_is_rejected_for_an_ngo_organization(client):
    token = user_token(client, "owner@ngo.org")
    org = _ngo_org(client, token)
    r = client.put(f"/orgs/{org}/csr-profile", json=GOOD_CSR_PROFILE, headers=auth(token))
    assert r.status_code == 422, r.text


def test_csr_profile_cannot_be_read_or_written_cross_org(client):
    owner_token = user_token(client, "owner@csr.org")
    org = _csr_org(client, owner_token)

    other_token = user_token(client, "other@csr.org")
    _csr_org(client, other_token, name="Other Foundation")

    r = client.get(f"/orgs/{org}/csr-profile", headers=auth(other_token))
    assert r.status_code == 404, r.text

    r = client.put(f"/orgs/{org}/csr-profile", json=GOOD_CSR_PROFILE, headers=auth(other_token))
    assert r.status_code == 404, r.text


def test_csr_profile_requires_auth(client):
    r = client.put("/orgs/00000000-0000-0000-0000-000000000000/csr-profile", json=GOOD_CSR_PROFILE)
    assert r.status_code == 401, r.text


def test_csr_profile_rejects_negative_budget(client):
    token = user_token(client, "owner@csr.org")
    org = _csr_org(client, token)
    r = client.put(
        f"/orgs/{org}/csr-profile",
        json={**GOOD_CSR_PROFILE, "csr_budget_minor": -100},
        headers=auth(token),
    )
    assert r.status_code == 422, r.text


# --------------------------------------------------------------------------- FCRA gating

def _system_user(db: Session, email: str) -> str:
    user = User(email=email, password_hash=hash_password("not-used-123"), full_name="Test Fixture User")
    db.add(user)
    db.flush()
    return user.id


def _published_ngo(db: Session, name: str, sectors: list[str], geographies: list[str]) -> Organization:
    org = Organization(name=name, org_type=OrgType.NGO, verification_status=VerificationStatus.APPROVED)
    db.add(org)
    db.flush()
    profile = NgoProfile(
        org_id=org.id, mission="Doing good work.", sectors=sectors, geographies=geographies,
        status=ProfileStatus.PUBLISHED,
    )
    db.add(profile)
    db.flush()
    return org


def _approve_documents(db: Session, org_id: str, doc_types: list[DocumentType]) -> None:
    actor_id = _system_user(db, f"doc-actor-{org_id}@fixture.test")
    for doc_type in doc_types:
        doc = Document(
            org_id=org_id, doc_type=doc_type, title=f"{doc_type.value} Certificate",
            original_filename=f"{doc_type.value}.pdf", content_type="application/pdf",
            size_bytes=1024, sha256=f"sha-{org_id}-{doc_type.value}", storage_key=f"{org_id}-{doc_type.value}_key",
            uploaded_by_user_id=actor_id,
        )
        db.add(doc)
        db.flush()
        db.add(DocumentReviewDecision(
            document_id=doc.id, reviewer_user_id=actor_id, decision=ReviewStatus.APPROVED,
            reason="Document verified", previous_status=ReviewStatus.PENDING_REVIEW,
        ))
    db.commit()


_BASE_REQUIRED_DOCS = [
    DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A, DocumentType.SECTION_80G,
]


def test_fcra_required_opportunity_excludes_ngo_without_approved_fcra_document(client, db: Session):
    csr_token = user_token(client, "owner@csr.org")
    csr_org_id = _csr_org(client, csr_token)

    ngo = _published_ngo(db, "Health Trust", sectors=["health"], geographies=["Telangana"])
    _approve_documents(db, ngo.id, _BASE_REQUIRED_DOCS)  # no FCRA document

    opp = client.post(
        "/csr/opportunities",
        json={"title": "International Grant Program", "description": "Funded via foreign contributions.",
              "sectors": ["health"], "geographies": ["Telangana"], "deadline": (date.today() + timedelta(days=30)).isoformat(),
              "requirements_text": "FCRA registration required.", "fcra_required": True},
        headers=auth(csr_token),
    )
    assert opp.status_code == 201, opp.text
    opp_id = opp.json()["id"]

    scores = client.post(f"/csr/opportunities/{opp_id}/fit-scores/compute", headers=auth(csr_token))
    assert scores.status_code == 200, scores.text
    assert ngo.id not in {s["ngo_id"] for s in scores.json()}

    from app.models import EligibilityResult
    result = db.scalar(
        select(EligibilityResult).where(EligibilityResult.opportunity_id == opp_id, EligibilityResult.ngo_id == ngo.id)
    )
    assert result is not None
    assert result.passed is False
    assert "FCRA" in result.reason


def test_fcra_required_opportunity_includes_ngo_with_approved_fcra_document(client, db: Session):
    csr_token = user_token(client, "owner@csr.org")
    csr_org_id = _csr_org(client, csr_token)

    ngo = _published_ngo(db, "Global Health Trust", sectors=["health"], geographies=["Telangana"])
    _approve_documents(db, ngo.id, [*_BASE_REQUIRED_DOCS, DocumentType.FCRA])

    opp = client.post(
        "/csr/opportunities",
        json={"title": "International Grant Program", "description": "Funded via foreign contributions.",
              "sectors": ["health"], "geographies": ["Telangana"], "deadline": (date.today() + timedelta(days=30)).isoformat(),
              "requirements_text": "FCRA registration required.", "fcra_required": True},
        headers=auth(csr_token),
    )
    assert opp.status_code == 201, opp.text
    opp_id = opp.json()["id"]

    scores = client.post(f"/csr/opportunities/{opp_id}/fit-scores/compute", headers=auth(csr_token))
    assert scores.status_code == 200, scores.text
    by_ngo = {s["ngo_id"]: s for s in scores.json()}
    assert ngo.id in by_ngo
    assert "FCRA" in by_ngo[ngo.id]["explanation"]


def test_fcra_not_required_opportunity_is_unaffected_by_missing_fcra_document(client, db: Session):
    """The existing behaviour (FCRA is optional unless flagged) must not regress."""
    csr_token = user_token(client, "owner@csr.org")
    _csr_org(client, csr_token)

    ngo = _published_ngo(db, "Local Health Trust", sectors=["health"], geographies=["Telangana"])
    _approve_documents(db, ngo.id, _BASE_REQUIRED_DOCS)  # no FCRA document

    opp = client.post(
        "/csr/opportunities",
        json={"title": "Domestic Grant Program", "description": "Funded domestically.",
              "sectors": ["health"], "geographies": ["Telangana"], "deadline": (date.today() + timedelta(days=30)).isoformat(),
              "requirements_text": "No special requirements."},
        headers=auth(csr_token),
    )
    assert opp.status_code == 201, opp.text
    assert opp.json()["fcra_required"] is False
    opp_id = opp.json()["id"]

    scores = client.post(f"/csr/opportunities/{opp_id}/fit-scores/compute", headers=auth(csr_token))
    assert scores.status_code == 200, scores.text
    assert ngo.id in {s["ngo_id"] for s in scores.json()}


def test_opportunity_out_reports_fcra_required(client):
    csr_token = user_token(client, "owner@csr.org")
    _csr_org(client, csr_token)
    r = client.post(
        "/csr/opportunities",
        json={"title": "International Grant Program", "description": "Funded via foreign contributions.",
              "sectors": ["health"], "geographies": [], "deadline": (date.today() + timedelta(days=30)).isoformat(),
              "requirements_text": "FCRA registration required.", "fcra_required": True},
        headers=auth(csr_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["fcra_required"] is True
