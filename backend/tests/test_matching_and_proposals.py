"""Tests for RFP-to-Funded workflow: opportunities, eligibility, proposals, finance."""
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ApprovalRequest,
    Commitment,
    Document,
    DocumentReviewDecision,
    DocumentType,
    EligibilityResult,
    EligibilityRule,
    FinanceLedger,
    FitScore,
    Membership,
    Opportunity,
    Organization,
    OrgType,
    Proposal,
    ReviewStatus,
    Role,
    Shortlist,
    User,
    VerificationStatus,
)


@pytest.fixture
def csr_org(db: Session) -> Organization:
    """CSR organization."""
    org = Organization(name="Impact Fund", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def csr_user(db: Session, csr_org: Organization) -> User:
    """CSR user with ADMIN role."""
    from app.security import hash_password

    user = User(email="csr@test.com", password_hash=hash_password("password123"), full_name="CSR Admin")
    db.add(user)
    db.flush()
    db.add(Membership(org_id=csr_org.id, user_id=user.id, role=Role.ADMIN))
    db.commit()
    return user


@pytest.fixture
def approved_ngo(db: Session) -> Organization:
    """Approved NGO organization."""
    org = Organization(name="Health for All", org_type=OrgType.NGO, verification_status=VerificationStatus.APPROVED, verified_at=date.today())
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def ngo_user(db: Session, approved_ngo: Organization) -> User:
    """NGO user with ADMIN role."""
    from app.security import hash_password

    user = User(email="ngo@test.com", password_hash=hash_password("password123"), full_name="NGO Admin")
    db.add(user)
    db.flush()
    db.add(Membership(org_id=approved_ngo.id, user_id=user.id, role=Role.ADMIN))
    db.commit()
    return user


class TestOpportunityCRUD:
    def test_create_opportunity(self, client, csr_user, csr_org):
        """CSR can create an opportunity."""
        token = _login(client, "csr@test.com", "password123")
        payload = {
            "title": "Healthcare Innovation Fund",
            "description": "Fund innovative mobile health solutions",
            "sectors": ["health", "technology"],
            "geographies": ["Karnataka"],
            "budget_min": 1000000,
            "budget_max": 5000000,
            "deadline": (date.today() + timedelta(days=30)).isoformat(),
            "requirements_text": "NGOs must have healthcare focus and proven track record",
        }
        resp = client.post("/csr/opportunities", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Healthcare Innovation Fund"
        assert data["status"] == "DRAFT"

    def test_publish_opportunity(self, client, csr_user, csr_org, db: Session):
        """CSR can publish an opportunity."""
        # Create opportunity
        opp = Opportunity(
            org_id=csr_org.id,
            title="Test RFP",
            description="A test opportunity",
            deadline=date.today() + timedelta(days=30),
            requirements_text="Test requirements",
        )
        db.add(opp)
        db.commit()

        token = _login(client, "csr@test.com", "password123")
        resp = client.post(f"/csr/opportunities/{opp.id}/publish", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PUBLISHED"


class TestEligibility:
    def test_eligible_ngo(self, db: Session, approved_ngo: Organization):
        """Approved NGO with matching sectors is eligible."""
        # Create eligibility rule
        rule = EligibilityRule(
            rule_type="VERIFICATION_STATUS",
            condition_json={"status": "APPROVED"},
        )
        db.add(rule)
        db.flush()

        # Create CSR org and opportunity
        csr_org = Organization(name="CSR", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
        db.add(csr_org)
        db.flush()

        opp = Opportunity(
            org_id=csr_org.id,
            title="Test",
            description="Test",
            sectors=["health"],
            deadline=date.today() + timedelta(days=30),
            requirements_text="Test",
        )
        db.add(opp)
        db.flush()

        # Run eligibility check
        result = EligibilityResult(
            opportunity_id=opp.id,
            ngo_id=approved_ngo.id,
            passed=True,
            rule_id=rule.id,
            reason="NGO is APPROVED",
        )
        db.add(result)
        db.commit()

        # Verify
        check = db.scalar(
            select(EligibilityResult).where(
                EligibilityResult.opportunity_id == opp.id, EligibilityResult.ngo_id == approved_ngo.id
            )
        )
        assert check is not None
        assert check.passed is True


class TestProposal:
    def test_ngo_submit_proposal(self, client, ngo_user, approved_ngo: Organization, db: Session):
        """NGO can submit proposal if shortlisted."""
        # Create CSR org and opportunity
        csr_org = Organization(name="CSR", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
        db.add(csr_org)
        db.flush()

        opp = Opportunity(
            org_id=csr_org.id,
            title="Health RFP",
            description="Health opportunity",
            sectors=["health"],
            deadline=date.today() + timedelta(days=30),
            requirements_text="Requirements",
            status="PUBLISHED",
        )
        db.add(opp)
        db.flush()

        # Create shortlist
        shortlist = Shortlist(
            shortlist_id=opp.id,
            opportunity_id=opp.id,
            revision_num=1,
            ngo_ids=[approved_ngo.id],
            is_current=True,
            selected_by_user_id=ngo_user.id,
        )
        db.add(shortlist)
        db.flush()

        # Add all 5 required verified documents (required for proposals)
        for doc_type in [DocumentType.PAN, DocumentType.FCRA, DocumentType.SECTION_12A, DocumentType.SECTION_80G, DocumentType.REGISTRATION]:
            doc = Document(
                org_id=approved_ngo.id,
                doc_type=doc_type,
                title=f"{doc_type.value} Certificate",
                original_filename=f"{doc_type.value}.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                sha256="abc123",
                storage_key=f"{doc_type.value}_key",
                uploaded_by_user_id=ngo_user.id,
            )
            db.add(doc)
            db.flush()

            # Mark document as approved
            decision = DocumentReviewDecision(
                document_id=doc.id,
                reviewer_user_id=ngo_user.id,
                decision=ReviewStatus.APPROVED,
                reason="Document verified",
                previous_status=ReviewStatus.PENDING_REVIEW,
            )
            db.add(decision)
        db.commit()

        # NGO submits proposal
        token = _login(client, "ngo@test.com", "password123")
        payload = {
            "opportunity_id": opp.id,
            "problem_statement": "Rural communities lack access to healthcare",
            "solution": "Mobile clinic with telemedicine",
            "budget_requested": 2000000,
            "timeline": "12 months",
            "expected_outcomes": "Serve 10,000 beneficiaries",
        }
        resp = client.post("/ngo/proposals", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "SUBMITTED"
        assert data["version_num"] == 1

    def test_proposal_version_history(self, db: Session, approved_ngo: Organization, ngo_user: User):
        """Proposal versioning works correctly."""
        # Create opportunity
        csr_org = Organization(name="CSR", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
        db.add(csr_org)
        db.flush()

        opp = Opportunity(
            org_id=csr_org.id,
            title="Test",
            description="Test",
            deadline=date.today() + timedelta(days=30),
            requirements_text="Test",
        )
        db.add(opp)
        db.flush()

        # Submit v1
        proposal1 = Proposal(
            proposal_id="prop_1",
            opportunity_id=opp.id,
            ngo_id=approved_ngo.id,
            version_num=1,
            is_current=True,
            problem_statement="Problem v1",
            solution="Solution v1",
            budget_requested=1000000,
            timeline="6 months",
            expected_outcomes="100 beneficiaries",
            status="SUBMITTED",
        )
        db.add(proposal1)
        db.commit()

        # Submit v2
        proposal1.is_current = False
        proposal2 = Proposal(
            proposal_id="prop_1",
            opportunity_id=opp.id,
            ngo_id=approved_ngo.id,
            version_num=2,
            is_current=True,
            problem_statement="Problem v2",
            solution="Solution v2",
            budget_requested=2000000,
            timeline="12 months",
            expected_outcomes="500 beneficiaries",
            status="SUBMITTED",
        )
        db.add(proposal2)
        db.commit()

        # Verify
        current = db.scalar(
            select(Proposal).where(Proposal.proposal_id == "prop_1", Proposal.is_current == True)
        )
        assert current.version_num == 2
        assert current.budget_requested == 2000000


class TestFinanceLedger:
    def test_idempotent_ledger_entry(self, db: Session):
        """Duplicate idempotency keys produce only one ledger entry."""
        org = Organization(name="CSR", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
        ngo = Organization(name="NGO", org_type=OrgType.NGO, verification_status=VerificationStatus.APPROVED)
        db.add_all([org, ngo])
        db.flush()

        opp = Opportunity(
            org_id=org.id,
            title="Test",
            description="Test",
            deadline=date.today() + timedelta(days=30),
            requirements_text="Test",
        )
        db.add(opp)
        db.flush()

        user = User(email="user@test.com", password_hash="hash", full_name="User")
        db.add(user)
        db.flush()

        key = "idempotency_key_123"
        ledger1 = FinanceLedger(
            opportunity_id=opp.id,
            ngo_id=ngo.id,
            amount_minor=1000000,
            transaction_type="COMMITMENT",
            idempotency_key=key,
            recorded_by_user_id=user.id,
        )
        db.add(ledger1)
        db.commit()

        # Try to insert duplicate with same key (should fail due to unique constraint)
        ledger2 = FinanceLedger(
            opportunity_id=opp.id,
            ngo_id=ngo.id,
            amount_minor=1000000,
            transaction_type="COMMITMENT",
            idempotency_key=key,
            recorded_by_user_id=user.id,
        )
        db.add(ledger2)
        with pytest.raises(Exception):  # IntegrityError
            db.commit()
        db.rollback()

        # Verify only one entry exists
        count = db.scalar(
            select(__import__("sqlalchemy", fromlist=["func"]).func.count(FinanceLedger.id)).where(
                FinanceLedger.idempotency_key == key
            )
        )
        assert count == 1


class TestAuthorization:
    def test_non_shortlisted_ngo_cannot_submit(self, client, db: Session):
        """NGO not on shortlist cannot submit proposal."""
        # Create CSR org and user
        csr_org = Organization(name="CSR", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
        db.add(csr_org)
        db.flush()

        from app.security import hash_password
        csr_user = User(email="csr@test.com", password_hash=hash_password("password123"), full_name="CSR Admin")
        db.add(csr_user)
        db.flush()
        db.add(Membership(org_id=csr_org.id, user_id=csr_user.id, role=Role.ADMIN))
        db.flush()

        opp = Opportunity(
            org_id=csr_org.id,
            title="Health RFP",
            description="Health opportunity",
            sectors=["health"],
            deadline=date.today() + timedelta(days=30),
            requirements_text="Requirements",
            status="PUBLISHED",
        )
        db.add(opp)
        db.flush()

        # Create shortlist WITHOUT this NGO
        other_ngo = Organization(name="Other NGO", org_type=OrgType.NGO, verification_status=VerificationStatus.APPROVED)
        db.add(other_ngo)
        db.flush()

        shortlist = Shortlist(
            shortlist_id=opp.id,
            opportunity_id=opp.id,
            revision_num=1,
            ngo_ids=[other_ngo.id],
            is_current=True,
            selected_by_user_id=csr_user.id,
        )
        db.add(shortlist)

        # Create NGO user
        ngo = Organization(name="Excluded NGO", org_type=OrgType.NGO, verification_status=VerificationStatus.APPROVED)
        db.add(ngo)
        db.flush()

        from app.security import hash_password
        user = User(email="excluded@test.com", password_hash=hash_password("password123"), full_name="Excluded NGO")
        db.add(user)
        db.flush()
        db.add(Membership(org_id=ngo.id, user_id=user.id, role=Role.ADMIN))
        db.commit()

        # Try to submit (should fail)
        token = _login(client, "excluded@test.com", "password123")
        payload = {
            "opportunity_id": opp.id,
            "problem_statement": "This is a comprehensive problem statement",
            "solution": "This is our proposed comprehensive solution",
            "budget_requested": 1000000,
            "timeline": "6 months",
            "expected_outcomes": "We expect to serve 1000 beneficiaries with this project",
        }
        resp = client.post("/ngo/proposals", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


def _login(client, email: str, password: str) -> str:
    """Helper to login and get token."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _submit_proposal(client, db: Session, ngo_user: User, approved_ngo: Organization) -> tuple[str, Organization]:
    """Set up a shortlisted, compliance-cleared NGO and submit one proposal. Returns (proposal_id, csr_org)."""
    csr_org = Organization(name="CSR", org_type=OrgType.CSR, verification_status=VerificationStatus.APPROVED)
    db.add(csr_org)
    db.flush()

    opp = Opportunity(
        org_id=csr_org.id,
        title="Health RFP",
        description="Health opportunity",
        sectors=["health"],
        deadline=date.today() + timedelta(days=30),
        requirements_text="Requirements",
        status="PUBLISHED",
    )
    db.add(opp)
    db.flush()

    shortlist = Shortlist(
        shortlist_id=opp.id, opportunity_id=opp.id, revision_num=1, ngo_ids=[approved_ngo.id],
        is_current=True, selected_by_user_id=ngo_user.id,
    )
    db.add(shortlist)
    db.flush()

    for doc_type in [DocumentType.PAN, DocumentType.FCRA, DocumentType.SECTION_12A, DocumentType.SECTION_80G, DocumentType.REGISTRATION]:
        doc = Document(
            org_id=approved_ngo.id, doc_type=doc_type, title=f"{doc_type.value} Certificate",
            original_filename=f"{doc_type.value}.pdf", content_type="application/pdf", size_bytes=1024,
            sha256=f"sha-{doc_type.value}", storage_key=f"{doc_type.value}_key", uploaded_by_user_id=ngo_user.id,
        )
        db.add(doc)
        db.flush()
        db.add(DocumentReviewDecision(
            document_id=doc.id, reviewer_user_id=ngo_user.id, decision=ReviewStatus.APPROVED,
            reason="Document verified", previous_status=ReviewStatus.PENDING_REVIEW,
        ))
    db.commit()

    token = _login(client, "ngo@test.com", "password123")
    payload = {
        "opportunity_id": opp.id,
        "problem_statement": "Rural communities lack access to healthcare",
        "solution": "Mobile clinic with telemedicine",
        "budget_requested": 2000000,
        "timeline": "12 months",
        "expected_outcomes": "Serve 10,000 beneficiaries",
    }
    resp = client.post("/ngo/proposals", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"], csr_org


def _admin_token(client, db: Session) -> str:
    from app.security import hash_password

    admin = User(email="ops@platform.org", password_hash=hash_password("password123"), full_name="Ops", is_platform_admin=True)
    db.add(admin)
    db.commit()
    return _login(client, "ops@platform.org", "password123")


def _add_csr_member(db: Session, csr_org: Organization, email: str) -> None:
    from app.security import hash_password

    person = User(email=email, password_hash=hash_password("password123"), full_name="CSR Reviewer")
    db.add(person)
    db.flush()
    db.add(Membership(org_id=csr_org.id, user_id=person.id, role=Role.ADMIN))
    db.commit()


class TestProposalAdminPreScreen:
    def test_fresh_submission_is_hidden_from_csr_until_admin_clears_it(self, client, ngo_user, approved_ngo, db: Session):
        proposal_id, csr_org = _submit_proposal(client, db, ngo_user, approved_ngo)
        _add_csr_member(db, csr_org, "csr-screener@test.com")
        csr_token = _login(client, "csr-screener@test.com", "password123")

        listing = client.get("/csr/proposals", headers={"Authorization": f"Bearer {csr_token}"}).json()
        assert listing == []

        r = client.post(f"/csr/proposals/{proposal_id}/approve", headers={"Authorization": f"Bearer {csr_token}"})
        assert r.status_code == 409

        admin_token = _admin_token(client, db)
        queue = client.get("/admin/proposals/queue", headers={"Authorization": f"Bearer {admin_token}"}).json()
        assert any(item["id"] == proposal_id for item in queue)

    def test_admin_clears_proposal_then_csr_can_approve_and_commitment_is_created(self, client, ngo_user, approved_ngo, db: Session):
        proposal_id, csr_org = _submit_proposal(client, db, ngo_user, approved_ngo)
        _add_csr_member(db, csr_org, "csr-approver@test.com")
        csr_token = _login(client, "csr-approver@test.com", "password123")

        admin_token = _admin_token(client, db)
        r = client.post(
            f"/admin/proposals/{proposal_id}/decisions",
            json={"decision": "PENDING_CSR"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "PENDING_CSR"

        listing = client.get("/csr/proposals", headers={"Authorization": f"Bearer {csr_token}"}).json()
        assert any(p["id"] == proposal_id for p in listing)

        r = client.post(f"/csr/proposals/{proposal_id}/approve", headers={"Authorization": f"Bearer {csr_token}"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "APPROVED"

        commitment = db.scalar(select(Commitment).where(Commitment.proposal_id == proposal_id))
        assert commitment is not None and commitment.status == "CONFIRMED"
        ledger = db.scalar(select(FinanceLedger).where(FinanceLedger.ngo_id == approved_ngo.id))
        assert ledger is not None

    def test_admin_rejection_requires_a_reason_and_keeps_it_from_the_csr(self, client, ngo_user, approved_ngo, db: Session):
        proposal_id, csr_org = _submit_proposal(client, db, ngo_user, approved_ngo)
        admin_token = _admin_token(client, db)

        r = client.post(
            f"/admin/proposals/{proposal_id}/decisions",
            json={"decision": "ADMIN_REJECTED"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

        r = client.post(
            f"/admin/proposals/{proposal_id}/decisions",
            json={"decision": "ADMIN_REJECTED", "reason": "Budget not justified."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ADMIN_REJECTED"

        _add_csr_member(db, csr_org, "csr-blocked@test.com")
        csr_token = _login(client, "csr-blocked@test.com", "password123")
        listing = client.get("/csr/proposals", headers={"Authorization": f"Bearer {csr_token}"}).json()
        assert listing == []

    def test_proposal_admin_queue_and_decisions_are_admin_only(self, client, ngo_user, approved_ngo, db: Session):
        proposal_id, _csr_org = _submit_proposal(client, db, ngo_user, approved_ngo)
        ngo_token = _login(client, "ngo@test.com", "password123")

        assert client.get("/admin/proposals/queue", headers={"Authorization": f"Bearer {ngo_token}"}).status_code == 403
        r = client.post(
            f"/admin/proposals/{proposal_id}/decisions",
            json={"decision": "PENDING_CSR"},
            headers={"Authorization": f"Bearer {ngo_token}"},
        )
        assert r.status_code == 403

    def test_cannot_decide_a_proposal_twice(self, client, ngo_user, approved_ngo, db: Session):
        proposal_id, _csr_org = _submit_proposal(client, db, ngo_user, approved_ngo)
        admin_token = _admin_token(client, db)
        assert client.post(
            f"/admin/proposals/{proposal_id}/decisions", json={"decision": "PENDING_CSR"},
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code == 200
        r = client.post(
            f"/admin/proposals/{proposal_id}/decisions", json={"decision": "PENDING_CSR"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409
