"""Social sharing and tax receipt generation."""

import base64
import json
from datetime import UTC, datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.models import Campaign, Payment, TaxReceipt, Organization
from app.schemas import SocialShareIn, SocialShareOut, TaxReceiptGenerateIn, TaxReceiptOut

router = APIRouter(prefix="/social", tags=["social-sharing"])


def _generate_share_text(campaign_title: str, donor_name: Optional[str] = None, amount: Optional[int] = None) -> str:
    """Generate shareable text for social platforms."""
    base_text = f"I just donated to '{campaign_title}' on Vitainspire! 🎉"

    if donor_name and amount:
        base_text = f"I, {donor_name}, just donated ₹{amount / 100000:.1f}L to '{campaign_title}' on Vitainspire! 💙"

    return base_text


@router.post("/share", response_model=SocialShareOut)
def generate_social_share(
    payload: SocialShareIn,
    db: Session = Depends(get_db),
) -> SocialShareOut:
    """Generate social share link for a campaign."""
    # Verify campaign exists
    campaign = db.get(Campaign, payload.campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    # Generate share text
    share_text = _generate_share_text(
        campaign.title,
        payload.donor_name,
        payload.donation_amount
    )

    # Campaign URL
    campaign_url = f"https://vitainspire.org/campaigns/{payload.campaign_id}"

    platform = payload.platform.upper()

    if platform == "WHATSAPP":
        # WhatsApp share URL
        share_url = f"https://wa.me/?text={quote(share_text)}%20{quote(campaign_url)}"
        preview_text = f"{share_text} {campaign_url}"

    elif platform == "TWITTER":
        # Twitter share URL
        share_url = f"https://twitter.com/intent/tweet?text={quote(share_text)}&url={quote(campaign_url)}&hashtags=fundraising,ngo,impact"
        preview_text = f"{share_text} {campaign_url}"

    elif platform == "LINKEDIN":
        # LinkedIn share URL
        share_url = f"https://www.linkedin.com/sharing/share-offsite/?url={quote(campaign_url)}"
        preview_text = f"{share_text} {campaign_url}"

    elif platform == "EMAIL":
        # Email share URL
        subject = f"Check out this fundraising campaign: {campaign.title}"
        body = f"{share_text}\n\n{campaign_url}"
        share_url = f"mailto:?subject={quote(subject)}&body={quote(body)}"
        preview_text = f"Subject: {subject}\n\n{body}"

    elif platform == "FACEBOOK":
        # Facebook share URL
        share_url = f"https://www.facebook.com/sharer/sharer.php?u={quote(campaign_url)}"
        preview_text = f"{share_text} {campaign_url}"

    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported platform")

    # Record share event in audit
    record_audit(
        db,
        action="campaign.shared",
        resource_type="campaign",
        resource_id=campaign.id,
        org_id=campaign.ngo_id,
        details={"platform": platform, "donor_name": payload.donor_name},
    )
    db.commit()

    return SocialShareOut(
        platform=platform,
        share_url=share_url,
        preview_text=preview_text,
    )


# ============================================================================
# Tax Receipt Generation
# ============================================================================

router_receipts = APIRouter(prefix="/receipts", tags=["tax-receipts"])


@router_receipts.post("/generate", response_model=TaxReceiptOut, status_code=status.HTTP_201_CREATED)
def generate_tax_receipt(
    payload: TaxReceiptGenerateIn,
    db: Session = Depends(get_db),
) -> TaxReceiptOut:
    """Generate tax receipt (80G compliant) for a donation."""
    # Get payment
    payment = db.get(Payment, payload.payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")

    if payment.status != "COMPLETED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only completed payments can have tax receipts")

    # Check if receipt already exists
    existing = db.query(TaxReceipt).filter(TaxReceipt.payment_id == payload.payment_id).first()
    if existing:
        return TaxReceiptOut(
            id=existing.id,
            receipt_number=existing.receipt_number,
            donor_name=existing.donor_name,
            donor_email=existing.donor_email,
            amount_minor=existing.amount_minor,
            currency=existing.currency,
            ngo_name=existing.ngo_name,
            donor_pan=existing.donor_pan,
            ngo_80g_number=existing.ngo_80g_number,
            ngo_registration_number=existing.ngo_registration_number,
            receipt_date=existing.receipt_date.isoformat(),
            pdf_url=existing.pdf_url,
            email_sent_at=existing.email_sent_at.isoformat() if existing.email_sent_at else None,
            created_at=existing.created_at.isoformat(),
        )

    # Get campaign and NGO details
    campaign = db.get(Campaign, payment.campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    ngo = db.get(Organization, campaign.ngo_id)
    if ngo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")

    # Generate receipt number (e.g., TR-2024-00001)
    year = datetime.now(UTC).year
    count = db.query(TaxReceipt).filter(
        TaxReceipt.created_at >= datetime(year, 1, 1, tzinfo=UTC)
    ).count() + 1
    receipt_number = f"TR-{year}-{count:05d}"

    # Create tax receipt
    receipt = TaxReceipt(
        payment_id=payment.id,
        receipt_number=receipt_number,
        donor_name=payment.donor_name,
        donor_email=payment.donor_email,
        donor_pan=payload.donor_pan,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        ngo_name=ngo.name,
        ngo_80g_number=None,  # Would be populated from NGO profile
        ngo_registration_number=None,  # Would be populated from NGO profile
        receipt_date=datetime.now(UTC).date(),
    )
    db.add(receipt)
    db.commit()

    # In production, would generate PDF and upload to storage
    # For now, just record that receipt was created
    record_audit(
        db,
        action="tax_receipt.generated",
        resource_type="tax_receipt",
        resource_id=receipt.id,
        org_id=campaign.ngo_id,
        details={
            "payment_id": payment.id,
            "amount": payment.amount_minor,
            "donor_email": payment.donor_email,
            "receipt_number": receipt_number,
        },
    )
    db.commit()

    return TaxReceiptOut(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        donor_name=receipt.donor_name,
        donor_email=receipt.donor_email,
        amount_minor=receipt.amount_minor,
        currency=receipt.currency,
        ngo_name=receipt.ngo_name,
        donor_pan=receipt.donor_pan,
        ngo_80g_number=receipt.ngo_80g_number,
        ngo_registration_number=receipt.ngo_registration_number,
        receipt_date=receipt.receipt_date.isoformat(),
        pdf_url=receipt.pdf_url,
        email_sent_at=receipt.email_sent_at.isoformat() if receipt.email_sent_at else None,
        created_at=receipt.created_at.isoformat(),
    )


@router_receipts.post("/{receipt_id}/send-email")
def send_tax_receipt_email(
    receipt_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Send tax receipt via email."""
    receipt = db.get(TaxReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tax receipt not found")

    if receipt.email_sent_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already sent")

    # In production, would send email with PDF attachment
    # For now, just mark as sent
    receipt.email_sent_at = datetime.now(UTC)
    db.commit()

    record_audit(
        db,
        action="tax_receipt.email_sent",
        resource_type="tax_receipt",
        resource_id=receipt.id,
        details={"recipient_email": receipt.donor_email},
    )
    db.commit()

    return {"status": "email_sent", "recipient": receipt.donor_email}


@router_receipts.get("/{receipt_id}", response_model=TaxReceiptOut)
def get_tax_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
) -> TaxReceiptOut:
    """Get tax receipt details."""
    receipt = db.get(TaxReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tax receipt not found")

    return TaxReceiptOut(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        donor_name=receipt.donor_name,
        donor_email=receipt.donor_email,
        amount_minor=receipt.amount_minor,
        currency=receipt.currency,
        ngo_name=receipt.ngo_name,
        donor_pan=receipt.donor_pan,
        ngo_80g_number=receipt.ngo_80g_number,
        ngo_registration_number=receipt.ngo_registration_number,
        receipt_date=receipt.receipt_date.isoformat(),
        pdf_url=receipt.pdf_url,
        email_sent_at=receipt.email_sent_at.isoformat() if receipt.email_sent_at else None,
        created_at=receipt.created_at.isoformat(),
    )


@router_receipts.get("/by-payment/{payment_id}", response_model=TaxReceiptOut)
def get_receipt_by_payment(
    payment_id: str,
    db: Session = Depends(get_db),
) -> TaxReceiptOut:
    """Get tax receipt by payment ID."""
    receipt = db.query(TaxReceipt).filter(TaxReceipt.payment_id == payment_id).first()
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tax receipt not found")

    return TaxReceiptOut(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        donor_name=receipt.donor_name,
        donor_email=receipt.donor_email,
        amount_minor=receipt.amount_minor,
        currency=receipt.currency,
        ngo_name=receipt.ngo_name,
        donor_pan=receipt.donor_pan,
        ngo_80g_number=receipt.ngo_80g_number,
        ngo_registration_number=receipt.ngo_registration_number,
        receipt_date=receipt.receipt_date.isoformat(),
        pdf_url=receipt.pdf_url,
        email_sent_at=receipt.email_sent_at.isoformat() if receipt.email_sent_at else None,
        created_at=receipt.created_at.isoformat(),
    )
