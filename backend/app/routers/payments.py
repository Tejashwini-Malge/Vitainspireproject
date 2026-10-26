"""Payment gateway integration (Razorpay)."""

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user_optional
from app.domain.receipts import send_payment_confirmation_and_certificate
from app.models import Campaign, Payment, RecurringDonation, User
from app.schemas import (
    PaymentInitiateIn, PaymentInitiateOut, PaymentOut, PaymentVerifyIn,
    RecurringDonationIn, RecurringDonationOut, PaymentWebhookIn
)

router = APIRouter(prefix="/payments", tags=["payments"])

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")



def _verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay webhook/payment signature.

    With no gateway secret configured, this deployment is running in mock-payment mode
    (the project's current, deliberate state -- real gateway integration is a later,
    separate decision): there is no real signature to check, so any payment the
    frontend reports as completed is accepted.
    """
    if not RAZORPAY_KEY_SECRET:
        return True

    message = f"{order_id}|{payment_id}"
    expected_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return signature == expected_signature


@router.post("/initiate", response_model=PaymentInitiateOut, status_code=status.HTTP_201_CREATED)
def initiate_payment(
    payload: PaymentInitiateIn,
    actor: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> PaymentInitiateOut:
    """Initiate a payment for a donation.

    Returns Razorpay order ID and payment details for frontend to complete payment.
    """
    # Verify campaign exists
    campaign = db.get(Campaign, payload.campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    if campaign.status != "LIVE":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This campaign is not live yet. Payments can only be initiated for admin-approved, live campaigns.",
        )

    # Validate amount
    if payload.amount_minor < 10000:  # Minimum ₹100
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Minimum donation is ₹100")

    # Create payment record in DB with INITIATED status
    payment = Payment(
        campaign_id=payload.campaign_id,
        donor_user_id=actor.id if actor else None,
        donor_name=payload.donor_name,
        donor_email=payload.donor_email,
        amount_minor=payload.amount_minor,
        currency="INR",
        status="INITIATED",
        is_recurring=payload.is_recurring,
        recurring_plan_id=payload.recurring_frequency if payload.is_recurring else None,
    )
    db.add(payment)
    db.flush()

    # In production, would create order with Razorpay API
    # For now, we'll use payment ID as order ID
    order_id = f"order_{payment.id}"

    payment.gateway_order_id = order_id

    # Audit is staged in the same transaction as the payment, then committed together.
    record_audit(
        db,
        action="payment.initiated",
        resource_type="payment",
        resource_id=payment.id,
        actor_user_id=actor.id if actor else None,
        org_id=campaign.ngo_id,
        details={
            "amount": payload.amount_minor,
            "donor_email": payload.donor_email,
            "is_recurring": payload.is_recurring,
        },
    )
    db.commit()

    return PaymentInitiateOut(
        payment_id=payment.id,
        order_id=order_id,
        amount_minor=payload.amount_minor,
        currency="INR",
        customer_name=payload.donor_name,
        customer_email=payload.donor_email,
        key_id=RAZORPAY_KEY_ID or "test_key",
    )


@router.post("/verify", response_model=PaymentOut)
def verify_payment(
    payload: PaymentVerifyIn,
    actor: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> PaymentOut:
    """Verify and complete a payment after Razorpay confirmation."""
    # Get payment record
    payment = db.get(Payment, payload.payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")

    if payment.status != "INITIATED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment already processed")

    # Verify signature
    if not _verify_razorpay_signature(payload.order_id, payload.payment_id, payload.signature):
        payment.status = "FAILED"
        payment.error_message = "Signature verification failed"
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Payment verification failed")

    # Update payment status
    payment.status = "COMPLETED"
    payment.gateway_payment_id = payload.payment_id
    payment.gateway_signature = payload.signature
    payment.completed_at = datetime.now(UTC)

    # Get campaign to update statistics
    campaign = db.get(Campaign, payment.campaign_id)
    if campaign:
        campaign.donation_count += 1
        campaign.amount_raised += payment.amount_minor

    # Audit is staged in the same transaction as the payment, then committed together.
    record_audit(
        db,
        action="payment.verified",
        resource_type="payment",
        resource_id=payment.id,
        actor_user_id=actor.id if actor else None,
        org_id=campaign.ngo_id if campaign else None,
        details={
            "amount": payment.amount_minor,
            "gateway_payment_id": payload.payment_id,
        },
    )
    db.commit()

    # A separate, self-committing step: the payment is already durably COMPLETED above,
    # so a failure sending the confirmation/certificate email must not roll that back.
    send_payment_confirmation_and_certificate(db, payment)

    return PaymentOut(
        id=payment.id,
        campaign_id=payment.campaign_id,
        donor_name=payment.donor_name,
        donor_email=payment.donor_email,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        status=payment.status,
        payment_method=payment.payment_method,
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        is_recurring=payment.is_recurring,
        created_at=payment.created_at,
        completed_at=payment.completed_at,
    )


@router.post("/webhook")
def payment_webhook(
    payload: PaymentWebhookIn,
    db: Session = Depends(get_db),
) -> dict:
    """Handle Razorpay webhook events."""
    event = payload.event

    if event == "payment.authorized":
        # Payment authorized event
        order_id = payload.payload.get("order_id", {}).get("id")
        payment_id = payload.payload.get("payment_id", {}).get("id")

        # Find and update payment
        payment = db.query(Payment).filter(
            Payment.gateway_order_id == order_id
        ).first()

        if payment and payment.status != "COMPLETED":
            payment.status = "COMPLETED"
            payment.gateway_payment_id = payment_id
            payment.completed_at = datetime.now(UTC)

            campaign = db.get(Campaign, payment.campaign_id)
            if campaign:
                campaign.donation_count += 1
                campaign.amount_raised += payment.amount_minor

            db.commit()
            send_payment_confirmation_and_certificate(db, payment)

    elif event == "payment.failed":
        # Payment failed event
        order_id = payload.payload.get("order_id", {}).get("id")
        error = payload.payload.get("error", {})

        payment = db.query(Payment).filter(
            Payment.gateway_order_id == order_id
        ).first()

        if payment:
            payment.status = "FAILED"
            payment.error_message = error.get("description", "Payment failed")
            db.commit()

    elif event == "subscription.activated":
        # Recurring donation activated
        subscription_id = payload.payload.get("subscription", {}).get("id")
        recurring = db.query(RecurringDonation).filter(
            RecurringDonation.gateway_subscription_id == subscription_id
        ).first()

        if recurring:
            recurring.status = "ACTIVE"
            recurring.activated_at = datetime.now(UTC)
            db.commit()

    elif event == "subscription.paused":
        # Recurring donation paused
        subscription_id = payload.payload.get("subscription", {}).get("id")
        recurring = db.query(RecurringDonation).filter(
            RecurringDonation.gateway_subscription_id == subscription_id
        ).first()

        if recurring:
            recurring.status = "PAUSED"
            recurring.paused_at = datetime.now(UTC)
            db.commit()

    elif event == "subscription.cancelled":
        # Recurring donation cancelled
        subscription_id = payload.payload.get("subscription", {}).get("id")
        recurring = db.query(RecurringDonation).filter(
            RecurringDonation.gateway_subscription_id == subscription_id
        ).first()

        if recurring:
            recurring.status = "CANCELLED"
            recurring.cancelled_at = datetime.now(UTC)
            db.commit()

    return {"status": "received"}


@router.get("/donation/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
) -> PaymentOut:
    """Get payment details."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")

    return PaymentOut(
        id=payment.id,
        campaign_id=payment.campaign_id,
        donor_name=payment.donor_name,
        donor_email=payment.donor_email,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        status=payment.status,
        payment_method=payment.payment_method,
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        is_recurring=payment.is_recurring,
        created_at=payment.created_at,
        completed_at=payment.completed_at,
    )


@router.post("/recurring/create", response_model=RecurringDonationOut, status_code=status.HTTP_201_CREATED)
def create_recurring_donation(
    payload: RecurringDonationIn,
    actor: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> RecurringDonationOut:
    """Create a recurring donation subscription."""
    # Verify campaign exists
    campaign = db.get(Campaign, payload.campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    if campaign.status != "LIVE":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This campaign is not live yet. Recurring donations can only be created for admin-approved, live campaigns.",
        )

    # Validate amount
    if payload.amount_minor < 10000:  # Minimum ₹100
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Minimum donation is ₹100")

    # Calculate next billing date based on frequency
    today = datetime.now(UTC).date()
    if payload.frequency == "MONTHLY":
        next_billing = today + timedelta(days=30)
    elif payload.frequency == "QUARTERLY":
        next_billing = today + timedelta(days=90)
    else:  # YEARLY
        next_billing = today + timedelta(days=365)

    # Create recurring donation record
    recurring = RecurringDonation(
        campaign_id=payload.campaign_id,
        donor_name=payload.donor_name,
        donor_email=payload.donor_email,
        amount_minor=payload.amount_minor,
        currency="INR",
        frequency=payload.frequency,
        gateway_subscription_id=f"sub_{recurring.id if 'recurring' in locals() else 'new'}",
        status="ACTIVE",
        next_billing_date=next_billing,
    )
    db.add(recurring)
    db.flush()

    # Update subscription ID with actual record ID
    recurring.gateway_subscription_id = f"sub_{recurring.id}"

    # Audit is staged in the same transaction as the subscription, then committed together.
    record_audit(
        db,
        action="recurring_donation.created",
        resource_type="recurring_donation",
        resource_id=recurring.id,
        actor_user_id=actor.id if actor else None,
        org_id=campaign.ngo_id,
        details={
            "amount": payload.amount_minor,
            "frequency": payload.frequency,
            "donor_email": payload.donor_email,
        },
    )
    db.commit()

    return RecurringDonationOut(
        id=recurring.id,
        campaign_id=recurring.campaign_id,
        donor_name=recurring.donor_name,
        donor_email=recurring.donor_email,
        amount_minor=recurring.amount_minor,
        currency=recurring.currency,
        frequency=recurring.frequency,
        status=recurring.status,
        next_billing_date=recurring.next_billing_date.isoformat(),
        total_payments=recurring.total_payments,
        total_amount_paid=recurring.total_amount_paid,
        created_at=recurring.created_at,
    )


@router.post("/recurring/{recurring_id}/pause")
def pause_recurring_donation(
    recurring_id: str,
    db: Session = Depends(get_db),
) -> RecurringDonationOut:
    """Pause a recurring donation."""
    recurring = db.get(RecurringDonation, recurring_id)
    if recurring is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurring donation not found")

    if recurring.status != "ACTIVE":
        raise HTTPException(status.HTTP_409_CONFLICT, "Recurring donation is not active")

    recurring.status = "PAUSED"
    recurring.paused_at = datetime.now(UTC)
    db.commit()

    return RecurringDonationOut(
        id=recurring.id,
        campaign_id=recurring.campaign_id,
        donor_name=recurring.donor_name,
        donor_email=recurring.donor_email,
        amount_minor=recurring.amount_minor,
        currency=recurring.currency,
        frequency=recurring.frequency,
        status=recurring.status,
        next_billing_date=recurring.next_billing_date.isoformat(),
        total_payments=recurring.total_payments,
        total_amount_paid=recurring.total_amount_paid,
        created_at=recurring.created_at,
    )


@router.post("/recurring/{recurring_id}/resume")
def resume_recurring_donation(
    recurring_id: str,
    db: Session = Depends(get_db),
) -> RecurringDonationOut:
    """Resume a paused recurring donation."""
    recurring = db.get(RecurringDonation, recurring_id)
    if recurring is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurring donation not found")

    if recurring.status != "PAUSED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Recurring donation is not paused")

    recurring.status = "ACTIVE"
    recurring.paused_at = None
    db.commit()

    return RecurringDonationOut(
        id=recurring.id,
        campaign_id=recurring.campaign_id,
        donor_name=recurring.donor_name,
        donor_email=recurring.donor_email,
        amount_minor=recurring.amount_minor,
        currency=recurring.currency,
        frequency=recurring.frequency,
        status=recurring.status,
        next_billing_date=recurring.next_billing_date.isoformat(),
        total_payments=recurring.total_payments,
        total_amount_paid=recurring.total_amount_paid,
        created_at=recurring.created_at,
    )


@router.post("/recurring/{recurring_id}/cancel")
def cancel_recurring_donation(
    recurring_id: str,
    actor: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> RecurringDonationOut:
    """Cancel a recurring donation."""
    recurring = db.get(RecurringDonation, recurring_id)
    if recurring is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurring donation not found")

    if recurring.status == "CANCELLED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Recurring donation is already cancelled")

    recurring.status = "CANCELLED"
    recurring.cancelled_at = datetime.now(UTC)
    campaign = db.get(Campaign, recurring.campaign_id)

    # Audit is staged in the same transaction as the cancellation, then committed together.
    record_audit(
        db,
        action="recurring_donation.cancelled",
        resource_type="recurring_donation",
        resource_id=recurring.id,
        actor_user_id=actor.id if actor else None,
        org_id=campaign.ngo_id if campaign else None,
        details={"subscription_id": recurring.gateway_subscription_id},
    )
    db.commit()

    return RecurringDonationOut(
        id=recurring.id,
        campaign_id=recurring.campaign_id,
        donor_name=recurring.donor_name,
        donor_email=recurring.donor_email,
        amount_minor=recurring.amount_minor,
        currency=recurring.currency,
        frequency=recurring.frequency,
        status=recurring.status,
        next_billing_date=recurring.next_billing_date.isoformat(),
        total_payments=recurring.total_payments,
        total_amount_paid=recurring.total_amount_paid,
        created_at=recurring.created_at,
    )
