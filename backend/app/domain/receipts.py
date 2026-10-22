"""Donation confirmation and 80G tax-certificate emails for a completed payment.

Deterministic: whether a certificate is attached is decided purely by
`is_pan_verified`, never by AI or by what the donor claims. A donor who is not
PAN-verified still gets a donation confirmation, just without the certificate.
"""

import asyncio
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.domain.pan import is_pan_verified
from app.email_service import EMAIL_TEMPLATES, EmailMessage, EventType, get_email_provider
from app.models import Campaign, EmailQueue, NgoProfile, Organization, PanVerification, Payment, ReviewStatus, SentEmail, TaxReceipt


def _rupees(amount_minor: int) -> str:
    return f"₹{amount_minor / 100:,.2f}"


def _send_now(db: Session, *, recipient_email: str, recipient_user_id: str | None, event_type: EventType,
              subject: str, html_body: str, text_body: str) -> bool:
    """Record the email as queued, attempt delivery immediately, and record the outcome.

    There is no background worker running in this environment, so queuing alone would
    never actually deliver anything; sending inline keeps the record (EmailQueue,
    SentEmail) consistent with what a worker-based delivery would have produced.
    """
    message = EmailMessage(
        recipient_email=recipient_email,
        recipient_user_id=recipient_user_id,
        event_type=event_type.value,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    queued = EmailQueue(
        recipient_email=recipient_email,
        recipient_user_id=recipient_user_id,
        event_type=event_type.value,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        template_name=EMAIL_TEMPLATES[event_type]["template"],
    )
    db.add(queued)
    db.flush()

    provider = get_email_provider()
    success, external_id = asyncio.run(provider.send(message))

    if success:
        queued.status = "SENT"
        queued.sent_at = datetime.now(UTC)
        db.add(SentEmail(
            email_queue_id=queued.id,
            recipient_email=recipient_email,
            recipient_user_id=recipient_user_id,
            event_type=event_type.value,
            subject=subject,
            delivery_provider=provider.__class__.__name__,
            external_message_id=external_id,
        ))
    else:
        queued.status = "FAILED"
        queued.error_message = external_id or "Unknown error"
    db.flush()
    return success


def _generate_tax_receipt(db: Session, payment: Payment, campaign: Campaign, ngo: Organization) -> TaxReceipt:
    pan_submission = db.scalar(
        select(PanVerification)
        .where(PanVerification.user_id == payment.donor_user_id, PanVerification.review_status == ReviewStatus.APPROVED)
        .order_by(PanVerification.uploaded_at.desc())
    )
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == ngo.id))

    year = datetime.now(UTC).year
    count = db.query(TaxReceipt).filter(TaxReceipt.created_at >= datetime(year, 1, 1, tzinfo=UTC)).count() + 1
    receipt = TaxReceipt(
        payment_id=payment.id,
        receipt_number=f"TR-{year}-{count:05d}",
        donor_name=payment.donor_name,
        donor_email=payment.donor_email,
        donor_pan=pan_submission.pan_number if pan_submission else None,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        ngo_name=ngo.name,
        ngo_80g_number=profile.section_80g_number if profile else None,
        ngo_registration_number=profile.registration_number if profile else None,
        receipt_date=date.today(),
    )
    db.add(receipt)
    db.flush()
    record_audit(
        db,
        action="tax_receipt.generated",
        resource_type="tax_receipt",
        resource_id=receipt.id,
        actor_user_id=payment.donor_user_id,
        org_id=campaign.ngo_id,
        details={"payment_id": payment.id, "amount": payment.amount_minor, "receipt_number": receipt.receipt_number},
    )
    return receipt


def send_payment_confirmation_and_certificate(db: Session, payment: Payment) -> TaxReceipt | None:
    """Called once a payment reaches COMPLETED. Commits its own work.

    Always sends a donation confirmation. Additionally generates and emails an 80G tax
    certificate, but only when the donor is PAN-verified -- otherwise the confirmation
    explains what verifying unlocks, and nothing claiming to be a tax certificate is
    ever sent for an unverified donor.
    """
    campaign = db.get(Campaign, payment.campaign_id)
    ngo = db.get(Organization, campaign.ngo_id) if campaign else None
    ngo_name = ngo.name if ngo else "the organization"

    verified = bool(payment.donor_user_id) and is_pan_verified(db, payment.donor_user_id)
    existing_receipt = db.scalar(select(TaxReceipt).where(TaxReceipt.payment_id == payment.id))
    receipt = existing_receipt
    if verified and receipt is None and campaign is not None and ngo is not None:
        receipt = _generate_tax_receipt(db, payment, campaign, ngo)

    confirmation_subject = EMAIL_TEMPLATES[EventType.DONATION_CONFIRMATION]["subject"].format(ngo_name=ngo_name)
    if receipt:
        confirmation_body = (
            f"Thank you for your donation of {_rupees(payment.amount_minor)} to {ngo_name}. "
            f"Your 80G tax certificate ({receipt.receipt_number}) is on its way in a separate email."
        )
    else:
        confirmation_body = (
            f"Thank you for your donation of {_rupees(payment.amount_minor)} to {ngo_name}. "
            "To receive an 80G tax certificate for this donation, verify your PAN from your dashboard."
        )
    _send_now(
        db,
        recipient_email=payment.donor_email,
        recipient_user_id=payment.donor_user_id,
        event_type=EventType.DONATION_CONFIRMATION,
        subject=confirmation_subject,
        html_body=confirmation_body,
        text_body=confirmation_body,
    )
    record_audit(
        db,
        action="payment.confirmation_email_sent",
        resource_type="payment",
        resource_id=payment.id,
        actor_user_id=payment.donor_user_id,
        org_id=campaign.ngo_id if campaign else None,
        details={"recipient_email": payment.donor_email, "certificate_attached": receipt is not None},
    )

    if receipt is not None and receipt.email_sent_at is None:
        cert_subject = EMAIL_TEMPLATES[EventType.TAX_RECEIPT_ISSUED]["subject"].format(ngo_name=ngo_name)
        cert_body = (
            f"Your 80G tax certificate {receipt.receipt_number} for your donation of "
            f"{_rupees(payment.amount_minor)} to {ngo_name} is attached."
        )
        sent = _send_now(
            db,
            recipient_email=receipt.donor_email,
            recipient_user_id=payment.donor_user_id,
            event_type=EventType.TAX_RECEIPT_ISSUED,
            subject=cert_subject,
            html_body=cert_body,
            text_body=cert_body,
        )
        if sent:
            receipt.email_sent_at = datetime.now(UTC)
            record_audit(
                db,
                action="tax_receipt.email_sent",
                resource_type="tax_receipt",
                resource_id=receipt.id,
                actor_user_id=payment.donor_user_id,
                org_id=campaign.ngo_id if campaign else None,
                details={"recipient_email": receipt.donor_email},
            )

    db.commit()
    return receipt
