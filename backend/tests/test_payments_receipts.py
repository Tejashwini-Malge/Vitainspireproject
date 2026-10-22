"""Mock payment completion: donation confirmation, and an 80G certificate gated on PAN verification."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Campaign, EmailQueue, Organization, SentEmail, TaxReceipt
from tests.helpers import auth, login, make_platform_admin, user_token

PDF = b"%PDF-1.7\n% pan card scan\n" + b"0" * 200
VALID_PAN = "ABCDE1234F"


def _ngo_with_campaign(client) -> tuple[str, str]:
    ngo_token = user_token(client, "owner@ngo.org")
    ngo_org = client.post("/orgs", json={"name": "Shanti Trust", "org_type": "NGO"}, headers=auth(ngo_token)).json()["id"]
    client.put(
        f"/orgs/{ngo_org}/profile",
        json={"mission": "Clean water for all.", "registration_number": "REG-123", "section_80g_number": "80G-456"},
        headers=auth(ngo_token),
    )
    with SessionLocal() as db:
        campaign = Campaign(
            ngo_id=ngo_org, title="Clean Water", description="Wells.", mission="Safe water.",
            beneficiary_description="300 households", impact_statement="Fewer illnesses.",
            budget_total=500_000, duration_months=6, status="LIVE",
        )
        db.add(campaign)
        db.commit()
        campaign_id = campaign.id
    return ngo_org, campaign_id


def _admin(client):
    user_token(client, "ops@platform.org")
    make_platform_admin("ops@platform.org")
    return login(client, "ops@platform.org")


def _pan_verify(client, donor_token: str) -> None:
    client.post(
        "/me/pan-verification",
        data={"pan_number": VALID_PAN},
        files={"file": ("pan.pdf", PDF, "application/pdf")},
        headers=auth(donor_token),
    )
    admin = _admin(client)
    sub_id = client.get("/me/pan-verification", headers=auth(donor_token)).json()[0]["id"]
    r = client.post(
        f"/admin/pan-verifications/{sub_id}/decisions",
        json={"decision": "APPROVED", "reason": "Matches scan"},
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text


def _pay(client, donor_token: str, campaign_id: str, amount_minor: int = 50_000) -> str:
    r = client.post(
        "/payments/initiate",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor", "donor_email": "donor@example.com", "amount_minor": amount_minor},
        headers=auth(donor_token),
    )
    assert r.status_code == 201, r.text
    payment_id = r.json()["payment_id"]
    order_id = r.json()["order_id"]
    r = client.post(
        "/payments/verify",
        json={"payment_id": payment_id, "order_id": order_id, "signature": "mock-signature-anything"},
        headers=auth(donor_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"
    return payment_id


def test_mock_payment_verifies_without_a_real_gateway_configured(client):
    donor = user_token(client, "donor@example.com")
    _, campaign_id = _ngo_with_campaign(client)
    _pay(client, donor, campaign_id)


def test_unverified_donor_gets_confirmation_but_no_certificate(client):
    donor = user_token(client, "donor@example.com")
    _, campaign_id = _ngo_with_campaign(client)
    payment_id = _pay(client, donor, campaign_id)

    with SessionLocal() as db:
        assert db.scalar(select(TaxReceipt).where(TaxReceipt.payment_id == payment_id)) is None
        sent = db.scalars(select(EmailQueue).where(EmailQueue.event_type == "donation_confirmation")).all()
        assert len(sent) == 1
        assert sent[0].status == "SENT"
        assert sent[0].recipient_email == "donor@example.com"
        assert "verify your PAN" in sent[0].html_body
        assert db.scalars(select(EmailQueue).where(EmailQueue.event_type == "tax_receipt_issued")).all() == []


def test_verified_donor_gets_certificate_with_ngo_numbers(client):
    donor = user_token(client, "donor@example.com")
    ngo_org, campaign_id = _ngo_with_campaign(client)
    _pan_verify(client, donor)
    payment_id = _pay(client, donor, campaign_id)

    with SessionLocal() as db:
        receipt = db.scalar(select(TaxReceipt).where(TaxReceipt.payment_id == payment_id))
        assert receipt is not None
        assert receipt.donor_pan == VALID_PAN
        assert receipt.ngo_80g_number == "80G-456"
        assert receipt.ngo_registration_number == "REG-123"
        assert receipt.email_sent_at is not None

        confirmation = db.scalars(select(EmailQueue).where(EmailQueue.event_type == "donation_confirmation")).all()
        certificate = db.scalars(select(EmailQueue).where(EmailQueue.event_type == "tax_receipt_issued")).all()
        assert len(confirmation) == 1 and confirmation[0].status == "SENT"
        assert len(certificate) == 1 and certificate[0].status == "SENT"
        assert receipt.receipt_number in certificate[0].html_body

        sent_rows = db.scalars(select(SentEmail).where(SentEmail.recipient_email == "donor@example.com")).all()
        assert len(sent_rows) == 2


def test_initiate_links_the_payment_to_the_logged_in_donor(client):
    donor = user_token(client, "donor@example.com")
    _, campaign_id = _ngo_with_campaign(client)
    payment_id = _pay(client, donor, campaign_id)

    from app.models import Payment, User
    with SessionLocal() as db:
        payment = db.get(Payment, payment_id)
        donor_user = db.query(User).filter(User.email == "donor@example.com").first()
        assert payment.donor_user_id == donor_user.id


def test_webhook_payment_authorized_also_triggers_confirmation_email(client):
    donor = user_token(client, "donor@example.com")
    _, campaign_id = _ngo_with_campaign(client)

    r = client.post(
        "/payments/initiate",
        json={"campaign_id": campaign_id, "donor_name": "Demo Donor", "donor_email": "donor@example.com", "amount_minor": 50_000},
        headers=auth(donor),
    )
    order_id = r.json()["order_id"]
    payment_id = r.json()["payment_id"]

    webhook = client.post(
        "/payments/webhook",
        json={"event": "payment.authorized", "payload": {"order_id": {"id": order_id}, "payment_id": {"id": "pay_mock_1"}}},
    )
    assert webhook.status_code == 200

    with SessionLocal() as db:
        sent = db.scalars(select(EmailQueue).where(EmailQueue.event_type == "donation_confirmation")).all()
        assert len(sent) == 1

    # A duplicate webhook delivery for an already-completed payment must not double-send.
    webhook2 = client.post(
        "/payments/webhook",
        json={"event": "payment.authorized", "payload": {"order_id": {"id": order_id}, "payment_id": {"id": "pay_mock_1"}}},
    )
    assert webhook2.status_code == 200
    with SessionLocal() as db:
        sent = db.scalars(select(EmailQueue).where(EmailQueue.event_type == "donation_confirmation")).all()
        assert len(sent) == 1


def test_admin_payments_directory_lists_real_transactions_with_campaign_and_ngo(client):
    donor = user_token(client, "donor@example.com")
    ngo_org, campaign_id = _ngo_with_campaign(client)
    _pay(client, donor, campaign_id, amount_minor=75_000)
    admin = _admin(client)

    rows = client.get("/admin/payments", headers=auth(admin)).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "COMPLETED"
    assert row["amount_minor"] == 75_000
    assert row["donor_email"] == "donor@example.com"
    assert row["campaign_id"] == campaign_id
    assert row["campaign_title"] == "Clean Water"
    assert row["ngo_name"] == "Shanti Trust"
    assert row["is_recurring"] is False


def test_admin_payments_directory_filters_by_status(client):
    donor = user_token(client, "donor@example.com")
    _, campaign_id = _ngo_with_campaign(client)
    _pay(client, donor, campaign_id)
    admin = _admin(client)

    assert len(client.get("/admin/payments?status_filter=COMPLETED", headers=auth(admin)).json()) == 1
    assert client.get("/admin/payments?status_filter=FAILED", headers=auth(admin)).json() == []


def test_admin_payments_directory_is_admin_only(client):
    donor = user_token(client, "donor@example.com")
    assert client.get("/admin/payments", headers=auth(donor)).status_code == 403


def test_admin_payments_directory_empty_is_not_an_error(client):
    admin = _admin(client)
    assert client.get("/admin/payments", headers=auth(admin)).json() == []
