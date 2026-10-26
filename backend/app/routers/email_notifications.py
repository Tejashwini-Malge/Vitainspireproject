"""Email notification preferences and management endpoints."""

import secrets
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.models import NotificationPreferences, User, EmailQueue
from app.schemas import (
    NotificationPreferencesIn,
    NotificationPreferencesOut,
    EmailQueueItemOut,
    UnsubscribeIn,
)
from app.deps import get_current_user
from app.audit import record_audit

router = APIRouter(prefix="/email", tags=["email-notifications"])


@router.get("/preferences", response_model=NotificationPreferencesOut, name="get_email_preferences")
def get_notification_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferencesOut:
    """Get current user's notification preferences."""
    prefs = db.scalar(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user.id)
    )
    if not prefs:
        # Auto-create with defaults
        prefs = NotificationPreferences(
            id=str(uuid.uuid4()),
            user_id=user.id,
            unsubscribe_token=secrets.token_urlsafe(75),
        )
        db.add(prefs)
        db.commit()

    return NotificationPreferencesOut(
        id=prefs.id,
        user_id=prefs.user_id,
        donation_received=prefs.donation_received,
        milestone_reached=prefs.milestone_reached,
        campaign_published=prefs.campaign_published,
        ngo_verified=prefs.ngo_verified,
        donor_digest=prefs.donor_digest,
        marketing_emails=prefs.marketing_emails,
        unsubscribed_at=prefs.unsubscribed_at,
        updated_at=prefs.updated_at,
    )


@router.patch("/preferences", response_model=NotificationPreferencesOut)
def update_notification_preferences(
    body: NotificationPreferencesIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferencesOut:
    """Update current user's notification preferences."""
    prefs = db.scalar(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user.id)
    )
    if not prefs:
        prefs = NotificationPreferences(
            id=str(uuid.uuid4()),
            user_id=user.id,
            unsubscribe_token=secrets.token_urlsafe(75),
        )
        db.add(prefs)

    # Update preferences
    prefs.donation_received = body.donation_received
    prefs.milestone_reached = body.milestone_reached
    prefs.campaign_published = body.campaign_published
    prefs.ngo_verified = body.ngo_verified
    prefs.donor_digest = body.donor_digest
    prefs.marketing_emails = body.marketing_emails
    db.flush()

    # Audit is staged in the same transaction as the preference change, then committed together.
    record_audit(
        db,
        action="notification_preferences_updated",
        resource_type="notification_preferences",
        resource_id=prefs.id,
        actor_user_id=user.id,
        details={
            "donation_received": body.donation_received,
            "milestone_reached": body.milestone_reached,
            "campaign_published": body.campaign_published,
            "ngo_verified": body.ngo_verified,
            "donor_digest": body.donor_digest,
            "marketing_emails": body.marketing_emails,
        },
    )

    db.commit()
    db.refresh(prefs)

    return NotificationPreferencesOut(
        id=prefs.id,
        user_id=prefs.user_id,
        donation_received=prefs.donation_received,
        milestone_reached=prefs.milestone_reached,
        campaign_published=prefs.campaign_published,
        ngo_verified=prefs.ngo_verified,
        donor_digest=prefs.donor_digest,
        marketing_emails=prefs.marketing_emails,
        unsubscribed_at=prefs.unsubscribed_at,
        updated_at=prefs.updated_at,
    )


@router.post("/unsubscribe", response_model=dict)
def unsubscribe_from_emails(body: UnsubscribeIn, db: Session = Depends(get_db)) -> dict:
    """Unsubscribe from all emails using token (no authentication required)."""
    prefs = db.scalar(
        select(NotificationPreferences).where(
            NotificationPreferences.unsubscribe_token == body.token
        )
    )
    if not prefs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid unsubscribe token")

    prefs.marketing_emails = False
    prefs.unsubscribed_at = prefs.updated_at

    db.commit()

    return {"status": "unsubscribed", "user_id": prefs.user_id}


@router.get("/queue", response_model=list[EmailQueueItemOut])
def get_email_queue(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: str = "PENDING",
) -> list[EmailQueueItemOut]:
    """Get email queue (admin only). Shows queued emails waiting to be sent."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    items = db.execute(
        select(EmailQueue)
        .where(EmailQueue.status == status_filter)
        .order_by(EmailQueue.created_at.desc())
    ).scalars().all()

    return [
        EmailQueueItemOut(
            id=item.id,
            recipient_email=item.recipient_email,
            event_type=item.event_type,
            subject=item.subject,
            status=item.status,
            retry_count=item.retry_count,
            created_at=item.created_at,
            sent_at=item.sent_at,
        )
        for item in items
    ]


@router.post("/test-email")
def send_test_email(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Send a test email to current user (for testing notification preferences)."""
    from datetime import datetime

    # Queue a test email
    test_email = EmailQueue(
        id=str(uuid.uuid4()),
        recipient_email=user.email,
        recipient_user_id=user.id,
        event_type="test_email",
        subject="Test email from Imparency",
        html_body="<p>This is a test email to verify your notification settings are working.</p>",
        text_body="This is a test email to verify your notification settings are working.",
        template_name="test_email",
        status="PENDING",
    )
    db.add(test_email)
    db.flush()

    # Audit is staged in the same transaction as the queued email, then committed together.
    record_audit(
        db,
        action="test_email_sent",
        resource_type="email_queue",
        resource_id=test_email.id,
        actor_user_id=user.id,
        details={"recipient_email": user.email},
    )

    db.commit()

    return {"status": "test email queued", "email_id": test_email.id}
