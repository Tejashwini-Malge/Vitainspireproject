"""Direct messaging: admin <-> organisation, and donor <-> admin.

The access rules matter more than the plumbing here: a conversation is private
material, and getting the boundary wrong leaks it.
"""

from tests.helpers import auth, login, make_platform_admin, register, user_token


def _donor(client, email, name):
    """A signed-up user with no organisation, and a known display name."""
    register(client, email, name)
    return login(client, email)


def _staff(client, email="ops@platform.org"):
    user_token(client, email)
    make_platform_admin(email)
    return login(client, email)


def _ngo(client, email="owner@ngo.org", name="Shanti Trust"):
    token = user_token(client, email)
    org = client.post("/orgs", json={"name": name, "org_type": "NGO"},
                      headers=auth(token)).json()["id"]
    return token, org


# ------------------------------------------------------------------ admin <-> org

def test_staff_can_open_a_thread_with_an_organisation_and_the_org_sees_it(client):
    ngo_token, org = _ngo(client)
    admin = _staff(client)

    r = client.post(
        "/conversations",
        json={"subject": "About your 80G certificate", "message": "Page 2 is unreadable; please re-upload.",
              "org_id": org},
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "ADMIN_ORG"
    assert body["my_side"] == "ADMIN"
    convo = body["id"]

    # The organisation sees the thread and the opening message.
    listed = client.get("/conversations", headers=auth(ngo_token)).json()
    assert [c["id"] for c in listed] == [convo]
    assert listed[0]["my_side"] == "ORG"

    messages = client.get(f"/conversations/{convo}/messages", headers=auth(ngo_token)).json()
    assert len(messages) == 1
    assert messages[0]["sender_side"] == "ADMIN"
    assert messages[0]["content"] == "Page 2 is unreadable; please re-upload."


def test_organisation_can_open_a_thread_with_platform_staff(client):
    ngo_token, org = _ngo(client)
    admin = _staff(client)

    r = client.post(
        "/conversations",
        json={"subject": "Verification seems stuck", "message": "We uploaded everything two weeks ago."},
        headers=auth(ngo_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "ADMIN_ORG"
    assert r.json()["my_side"] == "ORG"
    assert r.json()["org_id"] == org

    # Staff can see and answer it.
    convo = r.json()["id"]
    assert client.get("/conversations", headers=auth(admin)).json()[0]["id"] == convo
    reply = client.post(f"/conversations/{convo}/messages",
                        json={"content": "Looking now, apologies for the delay."},
                        headers=auth(admin))
    assert reply.status_code == 201, reply.text
    assert reply.json()["sender_side"] == "ADMIN"


def test_a_non_staff_user_cannot_open_a_thread_against_someone_elses_org(client):
    _other_token, other_org = _ngo(client, "other@ngo.org", "Other Trust")
    outsider = user_token(client, "outsider@elsewhere.org")

    r = client.post(
        "/conversations",
        json={"subject": "Let me in", "message": "Hello.", "org_id": other_org},
        headers=auth(outsider),
    )
    assert r.status_code == 403, r.text


def test_staff_cannot_open_a_thread_with_their_own_organisation(client):
    """Same conflict-of-interest rule as verification and document review."""
    admin = _staff(client)
    own = client.post("/orgs", json={"name": "Reviewer's Own Trust", "org_type": "NGO"},
                      headers=auth(admin)).json()["id"]

    r = client.post(
        "/conversations",
        json={"subject": "Talking to myself", "message": "Hello me.", "org_id": own},
        headers=auth(admin),
    )
    assert r.status_code == 403, r.text


def test_an_unrelated_organisation_cannot_read_the_thread(client):
    ngo_token, org = _ngo(client)
    admin = _staff(client)
    convo = client.post(
        "/conversations",
        json={"subject": "Private matter", "message": "Confidential.", "org_id": org},
        headers=auth(admin),
    ).json()["id"]

    stranger, _ = _ngo(client, "stranger@ngo.org", "Stranger Trust")
    assert client.get(f"/conversations/{convo}/messages", headers=auth(stranger)).status_code == 404
    assert client.post(f"/conversations/{convo}/messages", json={"content": "Hi"},
                       headers=auth(stranger)).status_code == 404
    assert client.get("/conversations", headers=auth(stranger)).json() == []


# ---------------------------------------------------------------- donor <-> admin

def test_a_donor_with_no_organisation_opens_a_donor_thread(client):
    donor = _donor(client, "asha@example.org", "Asha R")
    admin = _staff(client)

    r = client.post(
        "/conversations",
        json={"subject": "Receipt for my donation", "message": "I never received the 80G receipt."},
        headers=auth(donor),
    )
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "DONOR_ADMIN"
    assert r.json()["my_side"] == "DONOR"
    convo = r.json()["id"]

    staff_view = client.get("/conversations", headers=auth(admin)).json()
    assert staff_view[0]["id"] == convo
    assert staff_view[0]["my_side"] == "ADMIN"


def test_another_donor_cannot_read_a_donor_thread(client):
    donor = _donor(client, "asha@example.org", "Asha R")
    convo = client.post(
        "/conversations",
        json={"subject": "My donation", "message": "Private question."},
        headers=auth(donor),
    ).json()["id"]

    other_donor = _donor(client, "ravi@example.org", "Ravi K")
    assert client.get(f"/conversations/{convo}/messages", headers=auth(other_donor)).status_code == 404
    assert client.get("/conversations", headers=auth(other_donor)).json() == []


def test_staff_see_the_donor_by_name_and_the_donor_sees_the_platform(client):
    donor = _donor(client, "asha@example.org", "Asha R")
    admin = _staff(client)
    client.post("/conversations",
                json={"subject": "Receipt", "message": "Where is it?"},
                headers=auth(donor))

    donor_inbox = client.get("/inbox", headers=auth(donor)).json()
    assert donor_inbox[0]["counterparty_name"] == "Platform staff"

    staff_inbox = client.get("/inbox", headers=auth(admin)).json()
    assert staff_inbox[0]["counterparty_name"] == "Asha R"


# ------------------------------------------------------------------ shared behaviour

def test_marking_read_affects_only_inbound_messages(client):
    ngo_token, org = _ngo(client)
    admin = _staff(client)
    convo = client.post("/conversations",
                        json={"subject": "Question", "message": "From staff.", "org_id": org},
                        headers=auth(admin)).json()["id"]
    client.post(f"/conversations/{convo}/messages", json={"content": "From the NGO."},
                headers=auth(ngo_token))

    r = client.post(f"/conversations/{convo}/read", headers=auth(ngo_token))
    assert r.json()["marked_read"] == 1

    ngo_thread = client.get("/inbox", headers=auth(ngo_token)).json()[0]
    admin_thread = client.get("/inbox", headers=auth(admin)).json()[0]
    assert ngo_thread["unread_count"] == 0
    assert admin_thread["unread_count"] == 1, "the NGO reading must not mark its own message read"


def test_closed_conversations_reject_new_messages(client):
    ngo_token, org = _ngo(client)
    admin = _staff(client)
    convo = client.post("/conversations",
                        json={"subject": "Resolved thing", "message": "Opening.", "org_id": org},
                        headers=auth(admin)).json()["id"]

    assert client.post(f"/conversations/{convo}/close", headers=auth(admin)).status_code == 200
    r = client.post(f"/conversations/{convo}/messages", json={"content": "One more thing"},
                    headers=auth(ngo_token))
    assert r.status_code == 409, r.text


def test_only_staff_can_close_a_conversation(client):
    ngo_token, org = _ngo(client)
    admin = _staff(client)
    convo = client.post("/conversations",
                        json={"subject": "Thing", "message": "Opening.", "org_id": org},
                        headers=auth(admin)).json()["id"]

    assert client.post(f"/conversations/{convo}/close", headers=auth(ngo_token)).status_code == 403


def test_opening_a_conversation_is_audited(client):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AuditEvent

    ngo_token, org = _ngo(client)
    admin = _staff(client)
    convo = client.post("/conversations",
                        json={"subject": "Audited", "message": "Opening.", "org_id": org},
                        headers=auth(admin)).json()["id"]

    with SessionLocal() as db:
        ev = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "conversation.opened",
                AuditEvent.resource_id == convo,
            )
        )
        assert ev is not None
        assert ev.org_id == org


def test_conversations_require_authentication(client):
    assert client.get("/conversations").status_code == 401
    assert client.post("/conversations", json={"subject": "x" * 5, "message": "y"}).status_code == 401


# ------------------------------------------------------------------ unified inbox

def test_inbox_shows_direct_threads_alongside_proposal_threads(client):
    """The whole point of the inbox: one list, regardless of which store a thread is in."""
    from tests.test_inbox import _conversation as _proposal_conversation

    c = _proposal_conversation(client)
    client.post(f"/proposals/{c['proposal']}/messages",
                json={"content": "About your proposal."}, headers=auth(c["csr_token"]))

    # The same NGO user also has a direct thread with platform staff.
    admin = _staff(client, "ops2@platform.org")
    ngo_org = client.get("/orgs", headers=auth(c["ngo_token"])).json()[0]["id"]
    client.post("/conversations",
                json={"subject": "Document query", "message": "About your 80G.", "org_id": ngo_org},
                headers=auth(admin))

    inbox = client.get("/inbox", headers=auth(c["ngo_token"])).json()
    kinds = {t["kind"] for t in inbox}
    assert kinds == {"PROPOSAL", "ADMIN_ORG"}, f"expected both channels, got {kinds}"

    proposal_thread = next(t for t in inbox if t["kind"] == "PROPOSAL")
    direct_thread = next(t for t in inbox if t["kind"] == "ADMIN_ORG")
    assert proposal_thread["proposal_id"] == c["proposal"]
    assert proposal_thread["conversation_id"] is None
    assert direct_thread["conversation_id"] is not None
    assert direct_thread["proposal_id"] is None
    assert direct_thread["counterparty_name"] == "Platform staff"


def test_sql_filter_and_per_row_rule_agree(client):
    """The inbox selects conversations in SQL; the router checks one row at a time.

    Both come from AccessScope. If they ever disagree, a user either loses sight of
    their own conversations or gains sight of someone else's -- so assert agreement
    directly, across every participant in a mixed set of threads.
    """
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.domain.conversations import scope_for
    from app.models import Conversation, User

    # A mixed set: two organisations, two donors, staff, and an unrelated user.
    ngo_a, org_a = _ngo(client, "a@ngo.org", "Trust A")
    ngo_b, org_b = _ngo(client, "b@ngo.org", "Trust B")
    donor_a = _donor(client, "asha@example.org", "Asha R")
    donor_b = _donor(client, "ravi@example.org", "Ravi K")
    admin = _staff(client)
    outsider = user_token(client, "nobody@elsewhere.org")

    client.post("/conversations", json={"subject": "To Trust A", "message": "Hi.", "org_id": org_a},
                headers=auth(admin))
    client.post("/conversations", json={"subject": "To Trust B", "message": "Hi.", "org_id": org_b},
                headers=auth(admin))
    client.post("/conversations", json={"subject": "From Trust A", "message": "Hi."},
                headers=auth(ngo_a))
    client.post("/conversations", json={"subject": "Asha asks", "message": "Hi."},
                headers=auth(donor_a))
    client.post("/conversations", json={"subject": "Ravi asks", "message": "Hi."},
                headers=auth(donor_b))

    emails = [
        "a@ngo.org", "b@ngo.org", "asha@example.org",
        "ravi@example.org", "ops@platform.org", "nobody@elsewhere.org",
    ]
    with SessionLocal() as db:
        every = db.scalars(select(Conversation)).all()
        assert len(every) == 5

        for email in emails:
            user = db.scalar(select(User).where(User.email == email))
            scope = scope_for(db, user)

            by_sql = {c.id for c in db.scalars(select(Conversation).where(scope.filter())).all()}
            by_rule = {c.id for c in every if scope.side_of(c) is not None}

            assert by_sql == by_rule, (
                f"for {email}: SQL filter selected {sorted(by_sql)} but the per-row rule "
                f"accepted {sorted(by_rule)}"
            )

        # And the rule is actually discriminating, not accepting everything.
        nobody = db.scalar(select(User).where(User.email == "nobody@elsewhere.org"))
        assert scope_for(db, nobody).org_ids == frozenset()
        assert {c.id for c in every if scope_for(db, nobody).side_of(c) is not None} == set()


def test_staff_membership_narrows_rather_than_widens_access(client):
    """Staff who belong to an organisation speak as that organisation, not as staff.

    The conflict-of-interest rule has to hold in the SQL path too, otherwise the inbox
    would label a conflicted thread as a staff thread.
    """
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.domain.conversations import ADMIN, ORG, scope_for
    from app.models import Conversation, User

    admin = _staff(client)
    own = client.post("/orgs", json={"name": "Staff's Own Trust", "org_type": "NGO"},
                      headers=auth(admin)).json()["id"]
    other_token, other_org = _ngo(client, "other@ngo.org", "Other Trust")

    # The staff member's own organisation opens a thread; staff also writes to another org.
    client.post("/conversations", json={"subject": "From my own org", "message": "Hi."},
                headers=auth(admin))
    client.post("/conversations", json={"subject": "To another org", "message": "Hi.", "org_id": other_org},
                headers=auth(admin))

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "ops@platform.org"))
        scope = scope_for(db, user)
        sides = {
            c.subject: scope.side_of(c)
            for c in db.scalars(select(Conversation).where(scope.filter())).all()
        }

    assert sides["From my own org"] == ORG, "a thread with their own org is not a staff thread"
    assert sides["To another org"] == ADMIN


# ------------------------------------------------------------------ org <-> org, and donor <-> NGO

def _csr(client, email="lead@foundation.org", name="Acme Foundation"):
    token = user_token(client, email)
    org = client.post("/orgs", json={"name": name, "org_type": "CSR"}, headers=auth(token)).json()["id"]
    return token, org


def test_csr_can_open_a_thread_directly_with_an_ngo_without_a_proposal(client):
    ngo_token, ngo_org = _ngo(client)
    csr_token, csr_org = _csr(client)

    r = client.post(
        "/conversations",
        json={"subject": "Interested in your work", "message": "Could we fund a borewell project?",
              "target_org_id": ngo_org},
        headers=auth(csr_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "ORG_ORG"
    assert body["my_side"] == "ORG"
    assert body["org_id"] == ngo_org
    assert body["counterparty_org_id"] == csr_org
    convo = body["id"]

    listed = client.get("/conversations", headers=auth(ngo_token)).json()
    assert [c["id"] for c in listed] == [convo]

    messages = client.get(f"/conversations/{convo}/messages", headers=auth(ngo_token)).json()
    assert len(messages) == 1 and messages[0]["content"] == "Could we fund a borewell project?"


def test_ngo_can_open_a_thread_directly_with_a_csr(client):
    ngo_token, ngo_org = _ngo(client)
    csr_token, csr_org = _csr(client)

    r = client.post(
        "/conversations",
        json={"subject": "About your opportunity", "message": "We would like to discuss eligibility.",
              "target_org_id": csr_org},
        headers=auth(ngo_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "ORG_ORG"

    listed = client.get("/conversations", headers=auth(csr_token)).json()
    assert len(listed) == 1 and listed[0]["my_side"] == "ORG"


def test_org_org_conversation_cannot_be_opened_between_two_ngos(client):
    _, ngo_a = _ngo(client, "a@ngo.org", "Trust A")
    token_b, ngo_b = _ngo(client, "b@ngo.org", "Trust B")

    r = client.post(
        "/conversations",
        json={"subject": "Hi", "message": "Hello", "target_org_id": ngo_a},
        headers=auth(token_b),
    )
    assert r.status_code == 422


def test_org_org_conversation_cannot_be_opened_with_your_own_organisation(client):
    token, org = _ngo(client)
    r = client.post(
        "/conversations",
        json={"subject": "Hi", "message": "Hello", "target_org_id": org},
        headers=auth(token),
    )
    assert r.status_code == 422


def test_reopening_the_same_org_org_conversation_posts_into_it_instead_of_duplicating(client):
    _, ngo_org = _ngo(client)
    csr_token, _csr_org = _csr(client)

    first = client.post(
        "/conversations",
        json={"subject": "Hello", "message": "First message", "target_org_id": ngo_org},
        headers=auth(csr_token),
    ).json()
    second = client.post(
        "/conversations",
        json={"subject": "Hello again", "message": "Second message", "target_org_id": ngo_org},
        headers=auth(csr_token),
    ).json()

    assert first["id"] == second["id"]
    messages = client.get(f"/conversations/{first['id']}/messages", headers=auth(csr_token)).json()
    assert [m["content"] for m in messages] == ["First message", "Second message"]


def test_staff_are_not_a_party_to_an_org_org_conversation(client):
    _, ngo_org = _ngo(client)
    csr_token, _csr_org = _csr(client)
    admin = _staff(client)

    convo = client.post(
        "/conversations",
        json={"subject": "Hello", "message": "Hi there", "target_org_id": ngo_org},
        headers=auth(csr_token),
    ).json()["id"]

    assert client.get(f"/conversations/{convo}/messages", headers=auth(admin)).status_code == 404
    listed = client.get("/conversations", headers=auth(admin)).json()
    assert convo not in [c["id"] for c in listed]


def test_an_unrelated_organisation_cannot_read_an_org_org_conversation(client):
    ngo_token, ngo_org = _ngo(client)
    csr_token, _csr_org = _csr(client)
    outsider_token, _outsider_org = _csr(client, "other@funder.org", "Other Fund")

    convo = client.post(
        "/conversations",
        json={"subject": "Hello", "message": "Hi there", "target_org_id": ngo_org},
        headers=auth(csr_token),
    ).json()["id"]

    assert client.get(f"/conversations/{convo}/messages", headers=auth(outsider_token)).status_code == 404


def test_donor_can_open_a_thread_directly_with_an_ngo(client):
    ngo_token, ngo_org = _ngo(client)
    donor_token = _donor(client, "asha@example.org", "Asha R")

    r = client.post(
        "/conversations",
        json={"subject": "Question about your work", "message": "Do you operate in Bihar?",
              "target_org_id": ngo_org},
        headers=auth(donor_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "DONOR_NGO"
    assert body["my_side"] == "DONOR"
    assert body["org_id"] == ngo_org
    assert body["donor_user_id"] is not None

    listed = client.get("/conversations", headers=auth(ngo_token)).json()
    assert len(listed) == 1 and listed[0]["my_side"] == "ORG"


def test_donor_cannot_open_a_direct_thread_with_a_csr(client):
    donor_token = _donor(client, "asha@example.org", "Asha R")
    _, csr_org = _csr(client)

    r = client.post(
        "/conversations",
        json={"subject": "Hi", "message": "Hello", "target_org_id": csr_org},
        headers=auth(donor_token),
    )
    assert r.status_code == 422


def test_either_side_can_close_an_org_org_conversation(client):
    ngo_token, ngo_org = _ngo(client)
    csr_token, _csr_org = _csr(client)

    convo = client.post(
        "/conversations",
        json={"subject": "Hello", "message": "Hi there", "target_org_id": ngo_org},
        headers=auth(csr_token),
    ).json()["id"]

    r = client.post(f"/conversations/{convo}/close", headers=auth(ngo_token))
    assert r.status_code == 200 and r.json()["status"] == "CLOSED"


def test_cannot_set_both_org_id_and_target_org_id(client):
    admin = _staff(client)
    _, ngo_org = _ngo(client)
    r = client.post(
        "/conversations",
        json={"subject": "Hi", "message": "Hello", "org_id": ngo_org, "target_org_id": ngo_org},
        headers=auth(admin),
    )
    assert r.status_code == 422


def test_filter_and_side_of_agree_across_org_org_and_donor_ngo_threads(client):
    """Same invariant as test_sql_filter_and_per_row_rule_agree, extended to the new kinds."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.domain.conversations import scope_for
    from app.models import Conversation, User

    ngo_token, ngo_org = _ngo(client)
    csr_token, csr_org = _csr(client)
    donor_token = _donor(client, "asha@example.org", "Asha R")
    admin = _staff(client)
    outsider_token = user_token(client, "nobody@elsewhere.org")

    client.post("/conversations", json={"subject": "Org to org", "message": "Hi", "target_org_id": ngo_org},
                headers=auth(csr_token))
    client.post("/conversations", json={"subject": "Donor to NGO", "message": "Hi", "target_org_id": ngo_org},
                headers=auth(donor_token))

    emails = ["owner@ngo.org", "lead@foundation.org", "asha@example.org", "ops@platform.org", "nobody@elsewhere.org"]
    with SessionLocal() as db:
        every = db.scalars(select(Conversation)).all()
        assert len(every) == 2

        for email in emails:
            user = db.scalar(select(User).where(User.email == email))
            scope = scope_for(db, user)
            by_sql = {c.id for c in db.scalars(select(Conversation).where(scope.filter())).all()}
            by_rule = {c.id for c in every if scope.side_of(c) is not None}
            assert by_sql == by_rule, f"for {email}: SQL filter {sorted(by_sql)} vs rule {sorted(by_rule)}"

        # Staff must not see either: neither kind has a staff side.
        admin_user = db.scalar(select(User).where(User.email == "ops@platform.org"))
        assert scope_for(db, admin_user).side_of(every[0]) is None
        assert scope_for(db, admin_user).side_of(every[1]) is None


def test_a_real_donor_with_their_own_bookkeeping_org_still_gets_a_donor_ngo_conversation(client):
    """Registering as a donor via the actual signup flow creates an Organization row
    (org_type INDIVIDUAL) purely for bookkeeping. That must not be mistaken for a real
    NGO/CSR identity: the donor should still reach an NGO as DONOR_NGO, not ORG_ORG."""
    ngo_token, ngo_org = _ngo(client)
    donor_token = user_token(client, "asha@example.org")
    client.post("/orgs", json={"name": "Asha R", "org_type": "INDIVIDUAL"}, headers=auth(donor_token))

    r = client.post(
        "/conversations",
        json={"subject": "Question", "message": "Do you operate in Bihar?", "target_org_id": ngo_org},
        headers=auth(donor_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "DONOR_NGO"
    assert body["my_side"] == "DONOR"
    assert body["org_id"] == ngo_org
    assert body["counterparty_org_id"] is None

    listed = client.get("/conversations", headers=auth(ngo_token)).json()
    assert len(listed) == 1 and listed[0]["my_side"] == "ORG"


def test_a_real_donors_individual_org_is_not_a_reachable_message_target(client):
    donor_token = user_token(client, "asha@example.org")
    individual_org = client.post(
        "/orgs", json={"name": "Asha R", "org_type": "INDIVIDUAL"}, headers=auth(donor_token)
    ).json()["id"]

    r = client.post(
        "/conversations",
        json={"subject": "Hello there", "message": "Hello", "target_org_id": individual_org},
        headers=auth(user_token(client, "stranger@ngo.org")),
    )
    assert r.status_code == 404
