"""The unified inbox: every conversation a user is part of, in one list."""

from app.models import DocumentType
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
    DocumentType.PAN,
    DocumentType.REGISTRATION,
    DocumentType.SECTION_12A,
    DocumentType.SECTION_80G,
]


def _conversation(client):
    """An NGO and a CSR with one proposal between them. Returns the ids and tokens."""
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
    client.post("/csr/opportunities/shortlist",
                json={"opportunity_id": opp, "ngo_ids": [ngo]}, headers=auth(csr_token))

    r = client.post("/ngo/proposals", json={**PROPOSAL, "opportunity_id": opp}, headers=auth(ngo_token))
    assert r.status_code == 201, r.text
    return {"ngo_token": ngo_token, "csr_token": csr_token,
            "proposal": r.json()["id"], "opportunity": opp}


def test_inbox_shows_the_thread_to_both_sides_with_the_right_counterparty(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "Can you break down the per-well cost?"},
                headers=auth(c["csr_token"]))

    ngo_view = client.get("/inbox", headers=auth(c["ngo_token"])).json()
    assert len(ngo_view) == 1
    assert ngo_view[0]["my_side"] == "NGO"
    assert ngo_view[0]["counterparty_name"] == "Acme Foundation"
    assert ngo_view[0]["title"] == OPPORTUNITY["title"]

    csr_view = client.get("/inbox", headers=auth(c["csr_token"])).json()
    assert len(csr_view) == 1
    assert csr_view[0]["my_side"] == "CSR"
    assert csr_view[0]["counterparty_name"] == "Shanti Trust"


def test_unread_counts_only_the_other_sides_messages(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "Can you break down the per-well cost?"},
                headers=auth(c["csr_token"]))
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "INR 100,000 per well including labour."},
                headers=auth(c["ngo_token"]))

    ngo = client.get("/inbox", headers=auth(c["ngo_token"])).json()[0]
    csr = client.get("/inbox", headers=auth(c["csr_token"])).json()[0]

    assert ngo["total_messages"] == 2 and csr["total_messages"] == 2
    # Each side has exactly one message from the other, and neither counts its own.
    assert ngo["unread_count"] == 1
    assert csr["unread_count"] == 1


def test_marking_read_clears_only_inbound_messages(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "A question from the funder."},
                headers=auth(c["csr_token"]))
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "An answer from the NGO."},
                headers=auth(c["ngo_token"]))

    r = client.post(f"/inbox/threads/{c['proposal']}/read", headers=auth(c["ngo_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["marked_read"] == 1

    assert client.get("/inbox", headers=auth(c["ngo_token"])).json()[0]["unread_count"] == 0
    # The CSR side is untouched: the NGO reading does not mark the NGO's own message read.
    assert client.get("/inbox", headers=auth(c["csr_token"])).json()[0]["unread_count"] == 1


def test_last_message_preview_reflects_the_newest_message(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "First message."}, headers=auth(c["csr_token"]))
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "Second and latest message."}, headers=auth(c["ngo_token"]))

    thread = client.get("/inbox", headers=auth(c["csr_token"])).json()[0]
    assert thread["last_message_preview"] == "Second and latest message."
    assert thread["last_sender_side"] == "NGO"
    assert thread["last_message_at"] is not None


def test_long_messages_are_truncated_in_the_preview(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "x" * 500}, headers=auth(c["csr_token"]))

    preview = client.get("/inbox", headers=auth(c["ngo_token"])).json()[0]["last_message_preview"]
    assert preview.endswith("…")
    assert len(preview) <= 161


def test_unread_only_filter_hides_quiet_threads(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "A question."}, headers=auth(c["csr_token"]))

    assert len(client.get("/inbox?unread_only=true", headers=auth(c["ngo_token"])).json()) == 1
    client.post(f"/inbox/threads/{c['proposal']}/read", headers=auth(c["ngo_token"]))
    assert client.get("/inbox?unread_only=true", headers=auth(c["ngo_token"])).json() == []


def test_a_thread_with_no_messages_still_appears(client):
    """A submitted proposal is a conversation waiting to happen, not an absence."""
    c = _conversation(client)
    thread = client.get("/inbox", headers=auth(c["ngo_token"])).json()[0]
    assert thread["total_messages"] == 0
    assert thread["unread_count"] == 0
    assert thread["last_message_preview"] is None


def test_outsider_sees_an_empty_inbox(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "Private discussion."}, headers=auth(c["csr_token"]))

    outsider = user_token(client, "outsider@elsewhere.org")
    assert client.get("/inbox", headers=auth(outsider)).json() == []


def test_outsider_cannot_mark_someone_elses_thread_read(client):
    c = _conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "Private discussion."}, headers=auth(c["csr_token"]))

    outsider = user_token(client, "outsider@elsewhere.org")
    r = client.post(f"/inbox/threads/{c['proposal']}/read", headers=auth(outsider))
    assert r.status_code == 404, "existence of another org's thread must not be revealed"

    # And the real participant's unread count is untouched.
    assert client.get("/inbox", headers=auth(c["ngo_token"])).json()[0]["unread_count"] == 1


def test_inbox_requires_authentication(client):
    assert client.get("/inbox").status_code == 401


def test_inbox_cost_does_not_grow_with_thread_count(client):
    """The inbox must not issue a query per thread.

    The obvious implementation -- fetch threads, then look up each one's counterparty --
    is linear in thread count, so it degrades precisely for the users with the most
    conversations. This pins the shape of the query, not a wall-clock number.
    """
    from sqlalchemy import event

    from app.db import engine
    from tests.helpers import login, make_platform_admin

    ngo_token, org = user_token(client, "owner@ngo.org"), None
    org = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"},
                      headers=auth(ngo_token)).json()["id"]
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    admin = login(client, "ops@platform.org")

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def cost() -> int:
        statements.clear()
        r = client.get("/inbox", headers=auth(ngo_token))
        assert r.status_code == 200, r.text
        return len(statements)

    try:
        for i in range(2):
            client.post("/conversations",
                        json={"subject": f"Thread {i}", "message": "Hello.", "org_id": org},
                        headers=auth(admin))
        few = cost()

        for i in range(2, 12):
            client.post("/conversations",
                        json={"subject": f"Thread {i}", "message": "Hello.", "org_id": org},
                        headers=auth(admin))
        many = cost()
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert len(client.get("/inbox", headers=auth(ngo_token)).json()) == 12
    assert many == few, (
        f"12 threads cost {many} queries but 2 cost {few}: the inbox is issuing "
        "roughly one query per thread again"
    )


def test_inbox_shows_the_right_counterparty_name_for_org_to_org_threads(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(ngo_token)).json()["id"]
    csr_token = user_token(client, "lead@foundation.org")
    client.post("/orgs", json={"name": "Acme Foundation", "org_type": "CSR"}, headers=auth(csr_token))

    client.post(
        "/conversations",
        json={"subject": "Interested in your work", "message": "Hello!", "target_org_id": ngo},
        headers=auth(csr_token),
    )

    ngo_inbox = client.get("/inbox", headers=auth(ngo_token)).json()
    assert len(ngo_inbox) == 1
    assert ngo_inbox[0]["counterparty_name"] == "Acme Foundation"
    assert ngo_inbox[0]["kind"] == "ORG_ORG"

    csr_inbox = client.get("/inbox", headers=auth(csr_token)).json()
    assert len(csr_inbox) == 1
    assert csr_inbox[0]["counterparty_name"] == "Shanti Trust"


def test_inbox_shows_the_right_counterparty_name_for_donor_to_ngo_threads(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(ngo_token)).json()["id"]
    donor_token = user_token(client, "asha@example.org")

    client.post(
        "/conversations",
        json={"subject": "Question", "message": "Do you work in Bihar?", "target_org_id": ngo},
        headers=auth(donor_token),
    )

    ngo_inbox = client.get("/inbox", headers=auth(ngo_token)).json()
    assert len(ngo_inbox) == 1
    assert ngo_inbox[0]["counterparty_name"] == "Test User"  # user_token's default full_name
    assert ngo_inbox[0]["kind"] == "DONOR_NGO"

    donor_inbox = client.get("/inbox", headers=auth(donor_token)).json()
    assert len(donor_inbox) == 1
    assert donor_inbox[0]["counterparty_name"] == "Shanti Trust"
