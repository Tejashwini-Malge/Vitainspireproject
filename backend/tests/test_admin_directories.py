"""Admin directories: every organisation, and every project with its owner."""

from app.db import SessionLocal
from app.models import Campaign, CampaignDonation, DonationType, Organization, Payment, User
from tests.helpers import auth, login, make_platform_admin, user_token


def _staff(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def _org(client, token, name, org_type="NGO"):
    return client.post("/orgs", json={"name": name, "org_type": org_type},
                       headers=auth(token)).json()["id"]


def test_directory_lists_every_organisation_with_counts(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = _org(client, ngo_token, "Shanti Trust")
    client.post(f"/orgs/{ngo}/projects",
                json={"title": "Borewells", "summary": "Restore wells."},
                headers=auth(ngo_token))
    csr_token = user_token(client, "lead@foundation.org")
    _org(client, csr_token, "Acme Foundation", org_type="CSR")

    admin = _staff(client)
    rows = client.get("/admin/organizations", headers=auth(admin)).json()
    by_name = {r["name"]: r for r in rows}

    assert "Shanti Trust" in by_name and "Acme Foundation" in by_name
    assert by_name["Shanti Trust"]["org_type"] == "NGO"
    assert by_name["Shanti Trust"]["project_count"] == 1
    assert by_name["Shanti Trust"]["member_count"] == 1
    assert by_name["Acme Foundation"]["project_count"] == 0
    assert by_name["Shanti Trust"]["verification_status"] == "PENDING"


def test_directory_filters_by_type_and_status(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = _org(client, ngo_token, "Shanti Trust")
    csr_token = user_token(client, "lead@foundation.org")
    _org(client, csr_token, "Acme Foundation", org_type="CSR")
    admin = _staff(client)

    ngos = client.get("/admin/organizations?org_type=NGO", headers=auth(admin)).json()
    assert {r["name"] for r in ngos} == {"Shanti Trust"}

    donors = client.get("/admin/organizations?org_type=CSR", headers=auth(admin)).json()
    assert {r["name"] for r in donors} == {"Acme Foundation"}

    # Nothing is approved yet.
    assert client.get("/admin/organizations?verification_status=APPROVED",
                      headers=auth(admin)).json() == []

    client.post(f"/admin/organizations/{ngo}/verification",
                json={"decision": "APPROVED", "reason": "Checked."}, headers=auth(admin))
    approved = client.get("/admin/organizations?verification_status=APPROVED",
                          headers=auth(admin)).json()
    assert [r["name"] for r in approved] == ["Shanti Trust"]
    assert approved[0]["verified_at"] is not None


def test_project_directory_carries_the_owning_organisation(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = _org(client, ngo_token, "Shanti Trust")
    client.post(f"/orgs/{ngo}/projects",
                json={"title": "Borewell rehabilitation", "summary": "Restore 12 borewells."},
                headers=auth(ngo_token))
    admin = _staff(client)

    rows = client.get("/admin/projects", headers=auth(admin)).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "Borewell rehabilitation"
    assert row["org_name"] == "Shanti Trust"
    # The thing an admin most needs to spot: a project from an unverified organisation.
    assert row["org_verification_status"] == "PENDING"
    assert row["status"] == "DRAFT"
    assert row["campaign_id"] is None


def test_project_directory_filters_by_status(client):
    ngo_token = user_token(client, "owner@ngo.org")
    ngo = _org(client, ngo_token, "Shanti Trust")
    client.post(f"/orgs/{ngo}/projects", json={"title": "A", "summary": "One."},
                headers=auth(ngo_token))
    admin = _staff(client)

    assert len(client.get("/admin/projects?status_filter=DRAFT", headers=auth(admin)).json()) == 1
    assert client.get("/admin/projects?status_filter=PUBLISHED", headers=auth(admin)).json() == []


def test_empty_platform_returns_empty_lists_not_an_error(client):
    admin = _staff(client)
    assert client.get("/admin/projects", headers=auth(admin)).json() == []
    # The reviewer's own account creates no organisation, so the directory is empty too.
    assert client.get("/admin/organizations?org_type=NGO", headers=auth(admin)).json() == []


def test_directories_are_platform_admin_only(client):
    ngo_token = user_token(client, "owner@ngo.org")
    _org(client, ngo_token, "Shanti Trust")

    assert client.get("/admin/organizations", headers=auth(ngo_token)).status_code == 403
    assert client.get("/admin/projects", headers=auth(ngo_token)).status_code == 403
    assert client.get("/admin/organizations").status_code == 401


def test_directory_cost_does_not_grow_with_organisation_count(client):
    """Counts must come from grouped aggregates, not a query per organisation."""
    from sqlalchemy import event

    from app.db import engine

    admin = _staff(client)
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def cost() -> int:
        statements.clear()
        r = client.get("/admin/organizations", headers=auth(admin))
        assert r.status_code == 200, r.text
        return len(statements)

    try:
        for i in range(2):
            tok = user_token(client, f"o{i}@ngo.org")
            _org(client, tok, f"Trust {i}")
        few = cost()

        for i in range(2, 12):
            tok = user_token(client, f"o{i}@ngo.org")
            _org(client, tok, f"Trust {i}")
        many = cost()
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert len(client.get("/admin/organizations", headers=auth(admin)).json()) == 12
    assert many == few, (
        f"12 organisations cost {many} queries but 2 cost {few}: the directory is "
        "issuing roughly one query per organisation"
    )


def _campaign_for(db, ngo_org_id: str) -> str:
    campaign = Campaign(
        ngo_id=ngo_org_id,
        title="Clean Water",
        description="Wells for three villages.",
        mission="Safe drinking water.",
        beneficiary_description="300 households",
        impact_statement="Fewer waterborne illnesses.",
        budget_total=500_000,
        duration_months=6,
        status="LIVE",
    )
    db.add(campaign)
    db.flush()
    donation_type = DonationType(
        campaign_id=campaign.id, type="CASH", label="Cash", description="Cash donation", value_in_rupees=100
    )
    db.add(donation_type)
    db.flush()
    db.commit()
    return campaign.id, donation_type.id


def test_individual_donors_are_listed_separately_from_organisations(client):
    donor_token = user_token(client, "donor@example.com")
    ngo_token = user_token(client, "owner@ngo.org")
    ngo_org = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"},
                          headers=auth(ngo_token)).json()["id"]
    admin = _staff(client)

    with SessionLocal() as db:
        donor = db.query(User).filter(User.email == "donor@example.com").first()
        campaign_id, donation_type_id = _campaign_for(db, ngo_org)
        db.add(CampaignDonation(
            campaign_id=campaign_id, donation_type_id=donation_type_id, donor_name="Demo Donor",
            donor_email="donor@example.com", donor_user_id=donor.id, type="CASH", amount=150_000,
            status="COMPLETED",
        ))
        db.add(Payment(
            campaign_id=campaign_id, donor_user_id=donor.id, donor_name="Demo Donor",
            donor_email="donor@example.com", amount_minor=50_000, status="COMPLETED",
        ))
        # A failed payment must not count toward the total.
        db.add(Payment(
            campaign_id=campaign_id, donor_user_id=donor.id, donor_name="Demo Donor",
            donor_email="donor@example.com", amount_minor=999_999, status="FAILED",
        ))
        db.commit()

    rows = client.get("/admin/individual-donors", headers=auth(admin)).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["email"] == "donor@example.com"
    assert row["pan_status"] is None
    assert row["donation_count"] == 2
    assert row["total_donated_minor"] == 200_000
    assert row["ngo_count"] == 1

    # The NGO owner and the CSR-less admin are excluded: they belong to an organisation
    # or are platform staff, neither of which is an "individual donor".
    emails = {r["email"] for r in rows}
    assert "owner@ngo.org" not in emails
    assert "ops@platform.org" not in emails

    # Organisation directories stay untouched by this new table.
    orgs = client.get("/admin/organizations", headers=auth(admin)).json()
    assert {o["name"] for o in orgs} == {"Shanti Trust"}


def test_individual_donors_endpoint_is_admin_only(client):
    token = user_token(client, "donor2@example.com")
    assert client.get("/admin/individual-donors", headers=auth(token)).status_code == 403


def test_individual_donor_with_no_activity_still_appears(client):
    user_token(client, "quiet-donor@example.com")
    admin = _staff(client)
    rows = client.get("/admin/individual-donors", headers=auth(admin)).json()
    by_email = {r["email"]: r for r in rows}
    assert "quiet-donor@example.com" in by_email
    assert by_email["quiet-donor@example.com"]["donation_count"] == 0
    assert by_email["quiet-donor@example.com"]["total_donated_minor"] == 0
    assert by_email["quiet-donor@example.com"]["pan_status"] is None


def test_a_real_donor_with_their_own_bookkeeping_org_still_appears(client):
    """Registering as a donor via the actual signup flow creates an Organization row
    (org_type INDIVIDUAL) for bookkeeping. That membership must not disqualify them
    from the individual-donor directory the way real NGO/CSR membership would."""
    donor_token = user_token(client, "real-donor@example.com")
    client.post("/orgs", json={"name": "Real Donor", "org_type": "INDIVIDUAL"}, headers=auth(donor_token))

    admin = _staff(client)
    rows = client.get("/admin/individual-donors", headers=auth(admin)).json()
    assert "real-donor@example.com" in {r["email"] for r in rows}
