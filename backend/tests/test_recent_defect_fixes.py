"""Edge-case coverage for the five live defects found in the 2026-10-25 acceptance
report (D1-D5) and fixed the same day:

D1 - POST /ngo/campaigns/{id}/milestones 500'd on every campaign because the route built
     its "next sequence number" query with Python's builtin max() instead of
     sqlalchemy.func.max().
D2 - PATCH /email/preferences 500'd after already committing the change, because it
     called an undefined log_action() instead of app.audit.record_audit().
D3 - POST /ngo/generate-about (and its sibling /ngo/proposals/generate-draft) 500'd
     because they imported the `requests` package, which is not a declared dependency
     of this backend (only httpx is).
D4 - POST /payments/initiate and /payments/recurring/create accepted orders/subscriptions
     against campaigns that were never approved to LIVE.
D5 - POST /campaigns/{id}/donate required auth even though it sits on the public
     campaigns router and a sibling donate-anonymous route already allows anonymous
     donations; it is now consistent with the org-level donate endpoint, which accepts
     an optional bearer token.

Writing edge cases for D5 surfaced two more pre-existing bugs that the original
acceptance report never reached (it only tried an unauthenticated call, which 401'd
before hitting either of these):

D6 - CampaignDonationIn had no `currency` field at all, even though both donate routes
     read payload.currency.upper(). Any call that got past auth/validation crashed with
     AttributeError. Fixed by adding currency: str (default "INR") to the schema.
D7 - create_anonymous_donation called record_audit() without the required actor_user_id
     keyword, so the anonymous donation route crashed with TypeError on every call.
     Fixed by passing actor_user_id=None explicitly.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditEvent, CampaignDonation, CampaignMilestone, DonationType, Payment, RecurringDonation, User
from tests.helpers import auth, login, make_platform_admin, user_token

GOOD_CAMPAIGN = {
    "title": "Restore twelve village borewells",
    "description": (
        "Twelve borewells across four villages have failed, leaving families walking "
        "four kilometres for water. This campaign funds their full rehabilitation."
    ),
    "mission": "Clean water for rural schools",
    "beneficiary_count": 4000,
    "beneficiary_description": "Families and school children across four villages.",
    "impact_statement": "Four thousand people gain year-round access to safe water.",
    "budget_total": 5_000_000,
    "duration_months": 9,
}


def _ngo_org(client, token, name="Shanti Trust") -> str:
    r = client.post("/orgs", json={"name": name, "org_type": "NGO"}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _draft_campaign(client, token) -> str:
    r = client.post("/ngo/campaigns", json=GOOD_CAMPAIGN, headers=auth(token))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "DRAFT"
    return r.json()["id"]


def _pending_campaign(client, token) -> str:
    campaign_id = _draft_campaign(client, token)
    r = client.post(f"/ngo/campaigns/{campaign_id}/submit-for-review", headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PENDING_REVIEW"
    return campaign_id


def _admin(client) -> str:
    """Idempotent: a test may need more than one LIVE campaign (e.g. to isolate a
    cross-campaign donation type), and register() 409s on a repeat email."""
    with SessionLocal() as db:
        already_registered = db.scalar(select(User).where(User.email == "ops@platform.org")) is not None
    if not already_registered:
        user_token(client, "ops@platform.org")
        make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def _live_campaign(client, token) -> str:
    campaign_id = _pending_campaign(client, token)
    admin = _admin(client)
    r = client.post(f"/admin/campaigns/{campaign_id}/approve", headers=auth(admin))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "LIVE"
    return campaign_id


def _donation_type_for(campaign_id: str) -> str:
    with SessionLocal() as db:
        dt = DonationType(
            campaign_id=campaign_id, type="CASH", label="Cash", description="Cash donation",
            value_in_rupees=100,
        )
        db.add(dt)
        db.commit()
        return dt.id


# --------------------------------------------------------------------------- D1: milestones

def test_milestone_can_be_added_to_a_draft_campaign(client):
    """Previously 500'd on every status, including DRAFT, because of the bare max() bug."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _draft_campaign(client, token)

    r = client.post(
        f"/ngo/campaigns/{campaign_id}/milestones",
        json={"title": "Site survey", "description": "Survey all twelve borewell sites.",
              "target_date": "2027-01-15", "target_amount": 400_000},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["sequence_num"] == 1
    assert r.json()["status"] == "PENDING"


def test_milestone_can_be_added_to_a_pending_review_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _pending_campaign(client, token)

    r = client.post(
        f"/ngo/campaigns/{campaign_id}/milestones",
        json={"title": "Procurement", "description": "Buy pumps and platform materials.",
              "target_date": "2027-02-01", "target_amount": 800_000},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text


def test_milestone_can_be_added_to_a_live_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)

    r = client.post(
        f"/ngo/campaigns/{campaign_id}/milestones",
        json={"title": "Installation", "description": "Install pumps at all twelve sites.",
              "target_date": "2027-03-01", "target_amount": 800_000},
        headers=auth(token),
    )
    assert r.status_code == 201, r.text


def test_milestone_sequence_numbers_increment_across_repeated_calls(client):
    """The max()->func.max() fix must still compute the right next sequence number,
    not just avoid crashing."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _draft_campaign(client, token)

    seqs = []
    for i in range(4):
        r = client.post(
            f"/ngo/campaigns/{campaign_id}/milestones",
            json={"title": f"Phase {i}", "description": f"Phase {i} of the rollout plan.",
                  "target_date": "2027-01-01", "target_amount": 100_000},
            headers=auth(token),
        )
        assert r.status_code == 201, r.text
        seqs.append(r.json()["sequence_num"])
    assert seqs == [1, 2, 3, 4]

    with SessionLocal() as db:
        rows = db.scalars(
            select(CampaignMilestone).where(CampaignMilestone.campaign_id == campaign_id)
        ).all()
        assert sorted(m.sequence_num for m in rows) == [1, 2, 3, 4]


def test_milestone_on_unknown_campaign_is_404_not_500(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    r = client.post(
        "/ngo/campaigns/00000000-0000-0000-0000-000000000000/milestones",
        json={"title": "Ghost", "description": "Points at nothing at all.",
              "target_date": "2027-01-01", "target_amount": 1000},
        headers=auth(token),
    )
    assert r.status_code == 404, r.text


def test_milestone_cannot_be_added_by_a_non_owning_ngo(client):
    owner_token = user_token(client, "owner@ngo.org")
    _ngo_org(client, owner_token)
    campaign_id = _draft_campaign(client, owner_token)

    other_token = user_token(client, "other@ngo.org")
    _ngo_org(client, other_token, name="Other Trust")

    r = client.post(
        f"/ngo/campaigns/{campaign_id}/milestones",
        json={"title": "Hijack", "description": "Trying to add to someone else's campaign.",
              "target_date": "2027-01-01", "target_amount": 1000},
        headers=auth(other_token),
    )
    assert r.status_code == 403, r.text


def test_milestone_invalid_payload_is_422_not_500(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _draft_campaign(client, token)

    r = client.post(
        f"/ngo/campaigns/{campaign_id}/milestones",
        json={"title": "ok", "description": "too short", "target_date": "2027-01-01",
              "target_amount": -500},
        headers=auth(token),
    )
    assert r.status_code == 422, r.text


# --------------------------------------------------------------------- D2: preferences PATCH

def test_preferences_patch_returns_200_not_500_on_first_write(client):
    """No NotificationPreferences row exists yet for this user -- the PATCH must create
    one, persist it, and actually return 200 (previously 500 from the undefined
    log_action() call, even though the DB write had already succeeded)."""
    token = user_token(client, "donor@example.com")

    r = client.patch(
        "/email/preferences",
        json={"donation_received": "DAILY", "milestone_reached": "NEVER",
              "campaign_published": "INSTANT", "ngo_verified": "INSTANT",
              "donor_digest": "NEVER", "marketing_emails": True},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["donation_received"] == "DAILY"
    assert body["milestone_reached"] == "NEVER"
    assert body["marketing_emails"] is True


def test_preferences_patch_persists_and_is_reflected_on_get(client):
    token = user_token(client, "donor@example.com")
    client.patch(
        "/email/preferences",
        json={"donation_received": "WEEKLY", "milestone_reached": "INSTANT",
              "campaign_published": "INSTANT", "ngo_verified": "INSTANT",
              "donor_digest": "WEEKLY", "marketing_emails": False},
        headers=auth(token),
    )
    got = client.get("/email/preferences", headers=auth(token))
    assert got.status_code == 200
    assert got.json()["donation_received"] == "WEEKLY"


def test_preferences_patch_writes_an_audit_row_in_the_same_transaction(client):
    """CLAUDE.md: audit rows must be written in the same transaction as the action
    they record. Confirm the audit event actually lands, now that it uses
    record_audit() instead of the undefined log_action()."""
    token = user_token(client, "donor@example.com")
    r = client.patch(
        "/email/preferences",
        json={"donation_received": "NEVER", "milestone_reached": "INSTANT",
              "campaign_published": "INSTANT", "ngo_verified": "INSTANT",
              "donor_digest": "WEEKLY", "marketing_emails": False},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    prefs_id = r.json()["id"]

    with SessionLocal() as db:
        # audit_events is append-only and never truncated between tests (see conftest.py),
        # so scope by the resource this test actually created, not just the action name.
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "notification_preferences_updated",
                AuditEvent.resource_id == prefs_id,
            )
        ).all()
        assert len(events) == 1


def test_preferences_patch_rejects_invalid_frequency_with_422(client):
    """Schema validation should reject before the handler runs at all."""
    token = user_token(client, "donor@example.com")
    r = client.patch(
        "/email/preferences",
        json={"donation_received": "SOMETIMES", "milestone_reached": "INSTANT",
              "campaign_published": "INSTANT", "ngo_verified": "INSTANT",
              "donor_digest": "WEEKLY", "marketing_emails": False},
        headers=auth(token),
    )
    assert r.status_code == 422, r.text


def test_preferences_patch_requires_auth(client):
    r = client.patch(
        "/email/preferences",
        json={"donation_received": "DAILY", "milestone_reached": "NEVER",
              "campaign_published": "INSTANT", "ngo_verified": "INSTANT",
              "donor_digest": "NEVER", "marketing_emails": True},
    )
    assert r.status_code == 401, r.text


def test_test_email_endpoint_also_fixed_by_the_same_record_audit_change(client):
    """send_test_email had the identical undefined-log_action() bug but was never
    exercised in the acceptance run; confirm it does not 500 either."""
    token = user_token(client, "donor@example.com")
    r = client.post("/email/test-email", headers=auth(token))
    assert r.status_code == 200, r.text


# --------------------------------------------------------------------- D3: generate-about

def test_generate_about_without_llm_key_returns_fallback_not_500(client):
    """No VITA_LLM_API_KEY is configured in tests -- the route must hit its documented
    fallback, not crash on `import requests` (never a declared dependency)."""
    token = user_token(client, "owner@ngo.org")
    r = client.post(
        "/ngo/generate-about",
        json={"mission": "Clean water for rural schools", "sectors": ["WASH", "Education"]},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["about"], str) and len(r.json()["about"]) > 0


def test_generate_about_with_unreachable_website_still_returns_fallback(client):
    """website_url fetch failures must be swallowed, not surfaced as a 500."""
    token = user_token(client, "owner@ngo.org")
    r = client.post(
        "/ngo/generate-about",
        json={"mission": "Clean water for rural schools", "sectors": ["WASH"],
              "website_url": "https://this-domain-does-not-exist-xyz123.invalid"},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["about"], str)


def test_generate_about_missing_mission_is_400_not_500(client):
    token = user_token(client, "owner@ngo.org")
    r = client.post(
        "/ngo/generate-about",
        json={"sectors": ["WASH"]},
        headers=auth(token),
    )
    assert r.status_code == 400, r.text


def test_generate_about_missing_sectors_is_400_not_500(client):
    token = user_token(client, "owner@ngo.org")
    r = client.post(
        "/ngo/generate-about",
        json={"mission": "Clean water for rural schools"},
        headers=auth(token),
    )
    assert r.status_code == 400, r.text


def test_generate_about_requires_auth(client):
    r = client.post(
        "/ngo/generate-about",
        json={"mission": "Clean water for rural schools", "sectors": ["WASH"]},
    )
    assert r.status_code == 401, r.text


def test_generate_proposal_draft_sibling_also_fixed_same_requests_bug(client):
    """generate_proposal_draft had the identical `import requests` bug (AI-005 was
    NOT RUN in the acceptance report, but the same fix applies). Needs a real
    opportunity to attach to."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)

    csr_token = user_token(client, "csr@foundation.org")
    client.post("/orgs", json={"name": "Acme Foundation", "org_type": "CSR"}, headers=auth(csr_token))
    opp = client.post(
        "/csr/opportunities",
        json={"title": "Education Grant 2027", "description": "Support digital learning programs.",
              "sectors": ["Education"], "geographies": ["Telangana"],
              "deadline": "2027-06-30", "requirements_text": "No special requirements."},
        headers=auth(csr_token),
    )
    assert opp.status_code == 201, opp.text
    opp_id = opp.json()["id"]

    r = client.post(
        "/ngo/proposals/generate-draft",
        json={"opportunity_id": opp_id},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    for key in ("problem_statement", "solution", "timeline", "expected_outcomes"):
        assert r.json()[key]


# --------------------------------------------------------------- D4: payment gating

def test_payment_initiate_rejected_for_draft_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _draft_campaign(client, token)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        "/payments/initiate",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor",
              "donor_email": "donor@example.com", "amount_minor": 50_000},
        headers=auth(donor),
    )
    assert r.status_code == 422, r.text


def test_payment_initiate_rejected_for_pending_review_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _pending_campaign(client, token)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        "/payments/initiate",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor",
              "donor_email": "donor@example.com", "amount_minor": 50_000},
        headers=auth(donor),
    )
    assert r.status_code == 422, r.text


def test_payment_initiate_succeeds_for_live_campaign(client):
    """Happy path must keep working -- the gate must not over-block."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        "/payments/initiate",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor",
              "donor_email": "donor@example.com", "amount_minor": 50_000},
        headers=auth(donor),
    )
    assert r.status_code == 201, r.text
    assert r.json()["order_id"].startswith("order_")

    with SessionLocal() as db:
        assert db.scalar(select(Payment).where(Payment.campaign_id == campaign_id)) is not None


def test_payment_initiate_on_unknown_campaign_is_still_404_not_422(client):
    """The new LIVE-status gate must not shadow the existing not-found check."""
    donor = user_token(client, "donor@example.com")
    r = client.post(
        "/payments/initiate",
        json={"campaign_id": "00000000-0000-0000-0000-000000000000", "donor_name": "Demo Donor",
              "donor_email": "donor@example.com", "amount_minor": 50_000},
        headers=auth(donor),
    )
    assert r.status_code == 404, r.text


def test_recurring_donation_rejected_for_non_live_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _draft_campaign(client, token)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        "/payments/recurring/create",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor",
              "donor_email": "donor@example.com", "amount_minor": 50_000, "frequency": "MONTHLY"},
        headers=auth(donor),
    )
    assert r.status_code == 422, r.text


def test_recurring_donation_succeeds_for_live_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        "/payments/recurring/create",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor",
              "donor_email": "donor@example.com", "amount_minor": 50_000, "frequency": "MONTHLY"},
        headers=auth(donor),
    )
    assert r.status_code == 201, r.text

    with SessionLocal() as db:
        assert db.scalar(select(RecurringDonation).where(RecurringDonation.campaign_id == campaign_id)) is not None


# ------------------------------------------------------------- D5: public donate auth

def test_donate_without_auth_succeeds_and_is_recorded_as_anonymous(client):
    """Previously 401'd unauthenticated -- now consistent with the org-level donate
    endpoint, which already accepted unauthenticated calls."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)
    donation_type_id = _donation_type_for(campaign_id)

    r = client.post(
        f"/campaigns/{campaign_id}/donate",
        json={"donation_type_id": donation_type_id, "donor_name": "Anon Donor",
              "donor_email": "anon@example.com", "amount": 500},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_anonymous"] is True

    with SessionLocal() as db:
        donation = db.scalar(select(CampaignDonation).where(CampaignDonation.campaign_id == campaign_id))
        assert donation.donor_user_id is None
        assert donation.is_anonymous is True


def test_donate_with_auth_still_links_the_donor_and_is_not_anonymous_by_default(client):
    """The optional-auth fix must not silently anonymise logged-in donors."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)
    donation_type_id = _donation_type_for(campaign_id)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        f"/campaigns/{campaign_id}/donate",
        json={"donation_type_id": donation_type_id, "donor_name": "Named Donor",
              "donor_email": "donor@example.com", "amount": 500},
        headers=auth(donor),
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_anonymous"] is False

    with SessionLocal() as db:
        donation = db.scalar(select(CampaignDonation).where(CampaignDonation.campaign_id == campaign_id))
        assert donation.donor_user_id is not None


def test_donate_with_auth_and_explicit_is_anonymous_true_is_still_honoured(client):
    """A logged-in donor can still choose to donate anonymously via the flag."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)
    donation_type_id = _donation_type_for(campaign_id)

    donor = user_token(client, "donor@example.com")
    r = client.post(
        f"/campaigns/{campaign_id}/donate",
        json={"donation_type_id": donation_type_id, "donor_name": "Named Donor",
              "donor_email": "donor@example.com", "amount": 500, "is_anonymous": True},
        headers=auth(donor),
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_anonymous"] is True

    with SessionLocal() as db:
        donation = db.scalar(select(CampaignDonation).where(CampaignDonation.campaign_id == campaign_id))
        # Donor identity is still recorded internally even when displayed anonymously.
        assert donation.donor_user_id is not None


def test_donate_to_non_live_campaign_is_still_404(client):
    """The auth relaxation must not loosen the existing LIVE-only gate on this route."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _draft_campaign(client, token)

    with SessionLocal() as db:
        dt = DonationType(campaign_id=campaign_id, type="CASH", label="Cash",
                           description="Cash donation", value_in_rupees=100)
        db.add(dt)
        db.commit()
        donation_type_id = dt.id

    r = client.post(
        f"/campaigns/{campaign_id}/donate",
        json={"donation_type_id": donation_type_id, "donor_name": "Anon Donor",
              "donor_email": "anon@example.com", "amount": 500},
    )
    assert r.status_code == 404, r.text


def test_donate_rejects_a_donation_type_from_a_different_campaign(client):
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)

    other_token = user_token(client, "other@ngo.org")
    _ngo_org(client, other_token, name="Other Trust")
    other_campaign_id = _live_campaign(client, other_token)
    foreign_donation_type_id = _donation_type_for(other_campaign_id)

    r = client.post(
        f"/campaigns/{campaign_id}/donate",
        json={"donation_type_id": foreign_donation_type_id, "donor_name": "Anon Donor",
              "donor_email": "anon@example.com", "amount": 500},
    )
    assert r.status_code == 400, r.text


def test_donate_anonymous_route_still_works_unchanged(client):
    """Backward compatibility: the pre-existing dedicated anonymous route was kept and
    must keep working exactly as before."""
    token = user_token(client, "owner@ngo.org")
    _ngo_org(client, token)
    campaign_id = _live_campaign(client, token)
    donation_type_id = _donation_type_for(campaign_id)

    r = client.post(
        f"/campaigns/{campaign_id}/donate-anonymous",
        json={"donation_type_id": donation_type_id, "donor_name": "Anon Donor",
              "donor_email": "anon@example.com", "amount": 500},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_anonymous"] is True
