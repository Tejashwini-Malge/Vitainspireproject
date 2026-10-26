"""Receivable schedule and UTR reconciliation (ADM-009, DON-010) -- the first of two
planned increments toward the sheet's funding lifecycle (contracts and fine-grained
allocation are follow-ons). The CSR declares a payment schedule against its confirmed
commitment; admin/finance reconciles each tranche against the UTR of an actual bank
transfer, which writes a second, distinct FinanceLedger entry ("RECEIVED") alongside the
"COMMITMENT" entry already written at proposal approval.
"""

from app.db import SessionLocal
from app.models import DocumentType, FinanceLedger
from sqlalchemy import select
from tests.helpers import auth, login, make_platform_admin, user_token
from tests.test_projects import _approve, _approve_docs

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

PROPOSAL = {
    "problem_statement": "Twelve borewells have failed.",
    "solution": "Rehabilitate all twelve including pumps and testing.",
    "budget_requested": 1200000,
    "timeline": "9 months",
    "expected_outcomes": "Four thousand people served.",
}

REQUIRED_DOCS = [
    DocumentType.PAN, DocumentType.REGISTRATION, DocumentType.SECTION_12A, DocumentType.SECTION_80G,
]


def _approved_proposal(client):
    """An NGO and CSR with one CSR-approved proposal (confirmed commitment) between them."""
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"},
                      headers=auth(ngo_token)).json()["id"]
    _approve(client, ngo)
    _approve_docs(client, ngo, "owner@ngo.org", REQUIRED_DOCS)

    csr_token = user_token(client, "lead@foundation.org")
    csr = client.post("/orgs", json={"name": "Acme Foundation", "org_type": "CSR"},
                      headers=auth(csr_token)).json()["id"]

    opp = client.post("/csr/opportunities", json=OPPORTUNITY, headers=auth(csr_token)).json()["id"]
    client.post(f"/csr/opportunities/{opp}/publish", headers=auth(csr_token))
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))

    proposal = client.post("/ngo/proposals", json={**PROPOSAL, "opportunity_id": opp}, headers=auth(ngo_token)).json()["id"]

    admin = _admin(client)
    pre_screen = client.post(
        f"/admin/proposals/{proposal}/decisions", json={"decision": "PENDING_CSR"}, headers=auth(admin)
    )
    assert pre_screen.status_code == 200, pre_screen.text

    r = client.post(f"/csr/proposals/{proposal}/approve", headers=auth(csr_token))
    assert r.status_code == 200, r.text

    return {"ngo_token": ngo_token, "csr_token": csr_token, "proposal": proposal, "opportunity": opp,
            "committed_amount_minor": PROPOSAL["budget_requested"]}


def _admin(client) -> str:
    """Idempotent: several tests set up more than one proposal (e.g. admin pre-screen plus
    a second commitment-less proposal), and register() 409s on a repeat email."""
    with SessionLocal() as db:
        from app.models import User
        already_registered = db.scalar(select(User).where(User.email == "ops@platform.org")) is not None
    if not already_registered:
        user_token(client, "ops@platform.org")
        make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


GOOD_SCHEDULE = {"receivables": [
    {"amount_minor": 600000, "due_date": "2026-11-15"},
    {"amount_minor": 600000, "due_date": "2027-02-15"},
]}


def test_csr_declares_a_receivable_schedule(client):
    c = _approved_proposal(client)
    r = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"]))
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 2
    assert [row["sequence_num"] for row in body] == [1, 2]
    assert all(row["status"] == "PENDING" for row in body)
    assert body[0]["amount_minor"] == 600000


def test_both_parties_can_view_the_schedule(client):
    c = _approved_proposal(client)
    client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"]))

    for token in (c["ngo_token"], c["csr_token"]):
        r = client.get(f"/proposals/{c['proposal']}/receivables", headers=auth(token))
        assert r.status_code == 200, r.text
        assert len(r.json()) == 2


def test_an_outsider_cannot_view_or_declare_the_schedule(client):
    c = _approved_proposal(client)
    outsider = user_token(client, "outsider@example.org")
    assert client.get(f"/proposals/{c['proposal']}/receivables", headers=auth(outsider)).status_code == 404
    # Tenant boundary (CLAUDE.md): a non-member of the CSR org gets 404, not 403 -- org
    # existence/membership is not revealed to someone outside it.
    r = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(outsider))
    assert r.status_code == 404, r.text


def test_ngo_cannot_declare_the_schedule(client):
    """Only the funding CSR declares its own payment schedule -- the NGO is not a member
    of the CSR org at all, so this is the same tenant-boundary 404, not a role 403."""
    c = _approved_proposal(client)
    r = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["ngo_token"]))
    assert r.status_code == 404, r.text


def test_schedule_total_cannot_exceed_the_commitment(client):
    c = _approved_proposal(client)
    over_budget = {"receivables": [{"amount_minor": c["committed_amount_minor"] + 1, "due_date": "2026-11-15"}]}
    r = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=over_budget, headers=auth(c["csr_token"]))
    assert r.status_code == 422, r.text


def test_schedule_can_be_replaced_before_any_reconciliation(client):
    c = _approved_proposal(client)
    client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"]))

    replacement = {"receivables": [{"amount_minor": 1200000, "due_date": "2027-01-01"}]}
    r = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=replacement, headers=auth(c["csr_token"]))
    assert r.status_code == 201, r.text
    assert len(r.json()) == 1


def test_schedule_without_an_approved_commitment_is_409(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(ngo_token)).json()["id"]
    _approve(client, ngo)
    _approve_docs(client, ngo, "owner@ngo.org", REQUIRED_DOCS)
    csr_token = user_token(client, "lead@foundation.org")
    client.post("/orgs", json={"name": "Acme Foundation", "org_type": "CSR"}, headers=auth(csr_token))
    opp = client.post("/csr/opportunities", json=OPPORTUNITY, headers=auth(csr_token)).json()["id"]
    client.post(f"/csr/opportunities/{opp}/publish", headers=auth(csr_token))
    client.post("/csr/opportunities/shortlist", json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))
    proposal = client.post("/ngo/proposals", json={**PROPOSAL, "opportunity_id": opp}, headers=auth(ngo_token)).json()["id"]

    r = client.post(f"/csr/proposals/{proposal}/receivables", json=GOOD_SCHEDULE, headers=auth(csr_token))
    assert r.status_code == 409, r.text


# --------------------------------------------------------------------- admin reconciliation

def test_admin_reconciles_a_tranche_and_it_leaves_the_schedule_pending_otherwise(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    admin = _admin(client)

    r = client.post(
        f"/admin/receivables/{schedule[0]['id']}/reconcile",
        json={"utr": "UTR1234567890", "notes": "Confirmed via bank statement"},
        headers=auth(admin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RECONCILED"
    assert r.json()["utr"] == "UTR1234567890"
    assert r.json()["reconciled_at"] is not None

    remaining = client.get(f"/proposals/{c['proposal']}/receivables", headers=auth(c["ngo_token"])).json()
    assert remaining[0]["status"] == "RECONCILED"
    assert remaining[1]["status"] == "PENDING"


def test_reconciliation_writes_a_received_finance_ledger_entry(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    admin = _admin(client)
    client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "UTR1"}, headers=auth(admin))

    with SessionLocal() as db:
        entries = db.scalars(
            select(FinanceLedger).where(
                FinanceLedger.transaction_type == "RECEIVED",
                FinanceLedger.idempotency_key == f"receivable_{schedule[0]['id']}_reconciled",
            )
        ).all()
        assert len(entries) == 1
        assert entries[0].amount_minor == 600000

        # The original COMMITMENT entry from proposal approval must still be there, untouched.
        commitment_entries = db.scalars(select(FinanceLedger).where(FinanceLedger.transaction_type == "COMMITMENT")).all()
        assert len(commitment_entries) == 1


def test_reconciling_twice_is_rejected(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    admin = _admin(client)
    client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "UTR1"}, headers=auth(admin))

    r = client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "UTR2"}, headers=auth(admin))
    assert r.status_code == 409, r.text


def test_the_same_utr_cannot_reconcile_two_different_tranches(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    admin = _admin(client)
    client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "DUPLICATE_UTR"}, headers=auth(admin))

    r = client.post(f"/admin/receivables/{schedule[1]['id']}/reconcile", json={"utr": "DUPLICATE_UTR"}, headers=auth(admin))
    assert r.status_code == 409, r.text


def test_schedule_cannot_be_replaced_once_a_tranche_is_reconciled(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    admin = _admin(client)
    client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "UTR1"}, headers=auth(admin))

    r = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"]))
    assert r.status_code == 409, r.text


def test_reconcile_requires_admin(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    r = client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "UTR1"}, headers=auth(c["csr_token"]))
    assert r.status_code == 403, r.text


def test_reconcile_unknown_receivable_is_404(client):
    admin = _admin(client)
    r = client.post(
        "/admin/receivables/00000000-0000-0000-0000-000000000000/reconcile",
        json={"utr": "UTR1"},
        headers=auth(admin),
    )
    assert r.status_code == 404, r.text


def test_receivables_directory_filters_by_status(client):
    c = _approved_proposal(client)
    schedule = client.post(f"/csr/proposals/{c['proposal']}/receivables", json=GOOD_SCHEDULE, headers=auth(c["csr_token"])).json()
    admin = _admin(client)
    client.post(f"/admin/receivables/{schedule[0]['id']}/reconcile", json={"utr": "UTR1"}, headers=auth(admin))

    reconciled = client.get("/admin/receivables?status_filter=RECONCILED", headers=auth(admin)).json()
    assert len(reconciled) == 1 and reconciled[0]["id"] == schedule[0]["id"]

    pending = client.get("/admin/receivables?status_filter=PENDING", headers=auth(admin)).json()
    assert len(pending) == 1 and pending[0]["id"] == schedule[1]["id"]


def test_receivables_directory_is_admin_only(client):
    c = _approved_proposal(client)
    assert client.get("/admin/receivables", headers=auth(c["csr_token"])).status_code == 403
