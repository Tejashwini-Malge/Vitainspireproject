# Phase 3: Email Notification Integration Guide
**How to wire Phase 3 emails into Phase 1 & 2 workflows**

---

## Integration Points

### 1. Donation Created → Send Confirmation Emails

**Location:** `backend/app/routers/donations.py`

```python
# In the donate endpoint, after donation is recorded:

from app.email_worker import queue_email

# Send confirmation to donor
queue_email(
    db=db,
    recipient_email=donor_email,
    recipient_user_id=donor_user_id,  # if authenticated
    event_type="donation_confirmation",
    subject=f"Your ₹{amount} donation was received",
    html_body=render_template(
        "donation_confirmation",
        donor_name=donor_name,
        amount=amount,
        ngo_name=org.name,
        campaign_title=project.title if project else None,
        donation_receipt_url=f"https://imparency.org/donations/{donation_id}",
        preferences_url=f"https://imparency.org/dashboard/email-preferences",
        unsubscribe_url=f"https://imparency.org/email/unsubscribe?token={prefs.unsubscribe_token}"
    ),
    template_name="donation_confirmation",
    template_data={
        "donor_name": donor_name,
        "amount": amount,
        "ngo_name": org.name,
        "campaign_title": project.title if project else None,
    }
)

# Send notification to NGO owners/admins
# Get NGO members
org_members = db.execute(
    select(User)
    .join(Membership)
    .where(
        (Membership.org_id == org.id) & 
        (Membership.role.in_(['OWNER', 'ADMIN']))
    )
).scalars().all()

for member in org_members:
    prefs = db.scalar(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == member.id
        )
    )
    
    # Check preference (default: INSTANT)
    frequency = prefs.donation_received if prefs else "INSTANT"
    if frequency == "NEVER":
        continue
    
    queue_email(
        db=db,
        recipient_email=member.email,
        recipient_user_id=member.id,
        event_type="donation_received",
        subject=f"💚 Donation received: ₹{amount}",
        html_body=render_template(
            "donation_received",
            donor_name=donor_name,
            amount=amount,
            campaign_title=project.title if project else None,
            campaign_url=f"https://imparency.org/campaigns/{project.id}" if project else None,
            dashboard_url=f"https://imparency.org/dashboard/donations"
        ),
        template_name="donation_received",
        template_data={
            "donor_name": donor_name,
            "amount": amount,
            "campaign_title": project.title if project else None,
            "donation_date": datetime.now().isoformat(),
        }
    )
```

### 2. Campaign Published → Send Notifications

**Location:** `backend/app/routers/campaigns.py`

```python
# When admin approves and publishes campaign:

from app.email_worker import queue_email

# Notify NGO that campaign is live
ngo_members = db.execute(
    select(User)
    .join(Membership)
    .where(
        (Membership.org_id == campaign.ngo_id) & 
        (Membership.role.in_(['OWNER', 'ADMIN']))
    )
).scalars().all()

for member in ngo_members:
    queue_email(
        db=db,
        recipient_email=member.email,
        recipient_user_id=member.id,
        event_type="campaign_published",
        subject=f"✨ '{campaign.title}' is now live for donations",
        html_body=render_template(
            "campaign_published",
            campaign_title=campaign.title,
            campaign_url=f"https://imparency.org/campaigns/{campaign.id}",
            description_excerpt=campaign.description[:200],
        ),
        template_name="campaign_published",
        template_data={
            "campaign_title": campaign.title,
            "campaign_url": f"https://imparency.org/campaigns/{campaign.id}",
        }
    )

# Notify followers/supporters (if we have that feature in Phase 4)
# Send digest to donors who want it (frequency: DAILY/WEEKLY)
```

### 3. NGO Verified → Send Congratulations

**Location:** `backend/app/routers/admin.py`

```python
# When admin approves organization:

from app.email_worker import queue_email

# Notify organization owners
org_members = db.execute(
    select(User)
    .join(Membership)
    .where(
        (Membership.org_id == org.id) & 
        (Membership.role == 'OWNER')
    )
).scalars().all()

for member in org_members:
    queue_email(
        db=db,
        recipient_email=member.email,
        recipient_user_id=member.id,
        event_type="ngo_verified",
        subject="✅ Your organization is now verified on Imparency",
        html_body=render_template(
            "ngo_verified",
            org_name=org.name,
            verification_message="Your organization has passed our verification process and is now visible to donors.",
            next_steps_link="https://imparency.org/dashboard/getting-started",
        ),
        template_name="ngo_verified",
        template_data={
            "org_name": org.name,
            "next_steps": ["Set up your profile", "Create a campaign", "Share with donors"],
        }
    )
```

### 4. Milestone Reached → Send Updates

**Location:** `backend/app/routers/campaigns.py` or background job

```python
# When campaign reaches a milestone:

from app.email_worker import queue_email

# Notify NGO
ngo_members = db.execute(
    select(User)
    .join(Membership)
    .where(
        (Membership.org_id == campaign.ngo_id) & 
        (Membership.role.in_(['OWNER', 'ADMIN']))
    )
).scalars().all()

for member in ngo_members:
    queue_email(
        db=db,
        recipient_email=member.email,
        recipient_user_id=member.id,
        event_type="milestone_reached",
        subject=f"🎉 {campaign.title} reached {milestone.title}",
        html_body=render_template(
            "milestone_reached",
            campaign_title=campaign.title,
            milestone_title=milestone.title,
            milestone_description=milestone.description,
            campaign_url=f"https://imparency.org/campaigns/{campaign.id}",
        ),
        template_name="milestone_reached",
        template_data={
            "campaign_title": campaign.title,
            "milestone_title": milestone.title,
            "progress_percent": (campaign.amount_raised / campaign.budget_total) * 100,
        }
    )

# Optional: Notify donors who gave to this campaign
donors = db.execute(
    select(User)
    .join(CampaignDonation)
    .where(
        (CampaignDonation.campaign_id == campaign.id) &
        (CampaignDonation.donor_user_id == User.id)
    )
    .distinct()
).scalars().all()

for donor in donors:
    prefs = db.scalar(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == donor.id
        )
    )
    
    # Check preference
    if prefs and prefs.milestone_reached == "NEVER":
        continue
    
    queue_email(
        db=db,
        recipient_email=donor.email,
        recipient_user_id=donor.id,
        event_type="milestone_reached",
        subject=f"Impact Update: {campaign.title} reached {milestone.title}",
        html_body=render_template(
            "milestone_update_for_donor",
            campaign_title=campaign.title,
            milestone_title=milestone.title,
            donor_name=donor.full_name,
            campaign_url=f"https://imparency.org/campaigns/{campaign.id}",
        ),
        template_name="milestone_update_for_donor",
        template_data={
            "campaign_title": campaign.title,
            "donor_name": donor.full_name,
        }
    )
```

### 5. Scheduled: Donor Digest (Weekly)

**Location:** Background job or cron scheduler

```python
# Run every Monday at 9 AM

from app.email_worker import queue_email
from datetime import datetime, timedelta

def send_donor_digests():
    """Send weekly digest to donors who opted in."""
    db = SessionLocal()
    
    # Get all donors with WEEKLY preference
    weekly_donors = db.execute(
        select(User)
        .join(NotificationPreferences)
        .where(
            NotificationPreferences.donor_digest == "WEEKLY"
        )
    ).scalars().all()
    
    for donor in weekly_donors:
        # Get their donations from past week
        week_ago = datetime.now() - timedelta(days=7)
        donations = db.execute(
            select(CampaignDonation)
            .join(Campaign)
            .where(
                (CampaignDonation.donor_user_id == donor.id) &
                (CampaignDonation.created_at >= week_ago)
            )
        ).scalars().all()
        
        # Calculate impact
        total_donated = sum(d.amount for d in donations) / 100  # Convert to rupees
        campaigns_count = len(set(d.campaign_id for d in donations))
        
        # Get recommendations (campaigns similar to ones they donated to)
        recommended_campaigns = get_personalized_campaigns(donor.id, limit=3)
        
        queue_email(
            db=db,
            recipient_email=donor.email,
            recipient_user_id=donor.id,
            event_type="donor_digest",
            subject="Your weekly Imparency digest",
            html_body=render_template(
                "donor_digest",
                donor_name=donor.full_name,
                total_donated=total_donated,
                campaigns_count=campaigns_count,
                donations=donations,
                recommended_campaigns=recommended_campaigns,
                dashboard_url="https://imparency.org/dashboard/donations",
            ),
            template_name="donor_digest",
            template_data={
                "donor_name": donor.full_name,
                "stats": {
                    "total_donated": total_donated,
                    "campaigns_supported": campaigns_count,
                    "ngo_count": len(set(d.campaign.org_id for d in donations)),
                },
                "recommendations": recommended_campaigns,
            }
        )
    
    db.close()
```

---

## Email Template Rendering

### Using Jinja2 for Dynamic Content

```python
# backend/app/email_templates.py

from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('app/email_templates/'))

def render_template(template_name: str, **context) -> str:
    """Render an email template with given context."""
    template = env.get_template(f'{template_name}.html')
    return template.render(**context)
```

### Template File Structure
```
backend/
├── app/
│   ├── email_templates/
│   │   ├── donation_confirmation.html
│   │   ├── donation_received.html
│   │   ├── campaign_published.html
│   │   ├── milestone_reached.html
│   │   ├── ngo_verified.html
│   │   ├── donor_digest.html
│   │   └── base.html (extends with header/footer)
│   └── ...
```

---

## Checking Notification Preferences

### Helper Function

```python
# In app/email_service.py or utils

from app.models import NotificationPreferences

def should_send_notification(
    user_id: str,
    event_type: str,
    db: Session
) -> bool:
    """Check if user wants to receive this type of notification."""
    prefs = db.scalar(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == user_id
        )
    )
    
    if not prefs:
        # Default to INSTANT if no preferences set
        return True
    
    # Map event type to preference field
    preference_map = {
        "donation_received": prefs.donation_received,
        "campaign_published": prefs.campaign_published,
        "milestone_reached": prefs.milestone_reached,
        "ngo_verified": prefs.ngo_verified,
        "donor_digest": prefs.donor_digest,
    }
    
    frequency = preference_map.get(event_type, "INSTANT")
    
    # NEVER = don't send
    if frequency == "NEVER":
        return False
    
    # INSTANT = always send (handled by immediate queueing)
    # DAILY/WEEKLY = handled by digest scheduler
    
    return True
```

---

## Testing the Integration

### 1. Test Email Queueing

```python
# In test_donations.py

def test_donation_queues_confirmation_emails(client, db):
    """Donation creates confirmation emails in queue."""
    # Register donor
    donor_email = "test@donor.com"
    # ... register ...
    
    # Make donation
    # ... donation api call ...
    
    # Check email queue
    queued = db.execute(
        select(EmailQueue).where(
            (EmailQueue.recipient_email == donor_email) &
            (EmailQueue.event_type == "donation_confirmation")
        )
    ).scalar()
    
    assert queued is not None
    assert queued.status == "PENDING"
    assert "donation was received" in queued.subject.lower()
```

### 2. Test Preference Respecting

```python
def test_ngo_receives_donation_only_if_preference_allows(client, db, ngo_owner):
    """NGO doesn't get email if preference is NEVER."""
    # Set preference to NEVER
    prefs = db.scalar(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == ngo_owner.id
        )
    )
    if not prefs:
        prefs = NotificationPreferences(
            user_id=ngo_owner.id,
            donation_received="NEVER"
        )
        db.add(prefs)
    else:
        prefs.donation_received = "NEVER"
    db.commit()
    
    # Make donation
    # ... donation ...
    
    # Check NO email was queued
    queued = db.execute(
        select(EmailQueue).where(
            (EmailQueue.recipient_email == ngo_owner.email) &
            (EmailQueue.event_type == "donation_received")
        )
    ).scalar()
    
    assert queued is None
```

### 3. Test Worker Processing

```python
@pytest.mark.asyncio
async def test_email_worker_sends_queued_emails():
    """Email worker processes queue."""
    # Queue some emails
    # ... queue emails ...
    
    # Process queue
    stats = await process_email_queue()
    
    # Check results
    assert stats['sent'] == 2
    assert stats['failed'] == 0
    
    # Verify audit trail created
    sent = db.execute(
        select(SentEmail).where(
            SentEmail.event_type == "test_email"
        )
    ).scalars().all()
    
    assert len(sent) == 2
```

---

## Deployment Checklist

- [ ] Apply migration 0008 to production database
- [ ] Set up SendGrid account (or use mock for staging)
- [ ] Configure environment variables (EMAIL_PROVIDER, SENDGRID_API_KEY)
- [ ] Set up background job scheduler (APScheduler or Celery)
- [ ] Create email templates in `app/email_templates/`
- [ ] Wire integration points into Phase 1 & 2 code
- [ ] Run full test suite
- [ ] Test with actual emails (staging)
- [ ] Monitor queue depth and processing latency
- [ ] Set up SendGrid webhook for delivery status
- [ ] Create frontend UI for email preferences
- [ ] Train NGOs on notification settings

---

## Monitoring

### Key Metrics to Track

```sql
-- Queue health
SELECT 
  status,
  COUNT(*) as count,
  AVG(retry_count) as avg_retries
FROM email_queue
GROUP BY status;

-- Processing latency
SELECT 
  AVG(EXTRACT(EPOCH FROM (sent_at - created_at))) as avg_seconds
FROM sent_emails
WHERE sent_at IS NOT NULL;

-- Event volume
SELECT 
  event_type,
  COUNT(*) as count,
  COUNT(CASE WHEN bounced THEN 1 END) as bounced_count
FROM sent_emails
WHERE sent_at > NOW() - INTERVAL '7 days'
GROUP BY event_type;

-- Unsubscribe rate
SELECT 
  COUNT(CASE WHEN unsubscribed_at IS NOT NULL THEN 1 END) as unsubscribed,
  COUNT(*) as total,
  ROUND(
    100.0 * COUNT(CASE WHEN unsubscribed_at IS NOT NULL THEN 1 END) / COUNT(*),
    2
  ) as percentage
FROM notification_preferences;
```

### Alerts to Set Up

- [ ] Email queue > 1000 pending emails (slow processing)
- [ ] Email failure rate > 5% (SendGrid issue)
- [ ] Worker not running (no emails sent in 1 hour)
- [ ] Database growth (sent_emails table > 1GB)

---

## Summary

✅ **Phase 3 Integration ready**
- Donation → Email to NGO + Donor confirmation
- Campaign published → Email to NGO team
- NGO verified → Congratulations email
- Milestone reached → Impact update email
- Weekly digest → Aggregated donor summary

All integrated with user preferences, retry logic, and audit trails.

