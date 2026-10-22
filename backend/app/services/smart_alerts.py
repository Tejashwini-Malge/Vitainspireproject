"""Smart alerts engine for proactive admin notifications.

Generates alerts for:
- Inactive NGOs (no updates in 30 days)
- Churn risk donors/NGOs
- Underperforming campaigns
- High-risk transactions
- Expiring documents
"""
from datetime import datetime, timedelta, timezone
from typing import TypedDict
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Organization,
    Project,
    SmartAlert,
    ChurnPrediction,
    CampaignPrediction,
    Document,
    OrgType,
)
from app.audit import record_audit
import logging

logger = logging.getLogger(__name__)


class AlertGenerationResult(TypedDict):
    """Alert generation result."""
    alert_count: int
    alerts: list[SmartAlert]


def _create_alert(
    db: Session,
    alert_type: str,
    message: str,
    priority: str,
    subject_org_id: str | None = None,
    subject_project_id: str | None = None,
    recommended_action: str | None = None,
) -> SmartAlert:
    """Create and record an alert."""
    alert = SmartAlert(
        alert_type=alert_type,
        subject_org_id=subject_org_id,
        subject_project_id=subject_project_id,
        message=message,
        priority=priority,
        recommended_action=recommended_action,
    )
    db.add(alert)

    # Record audit
    record_audit(
        db,
        action="alert.generated",
        resource_type="alert",
        resource_id=alert.id or str(uuid.uuid4()),
        org_id=subject_org_id,
        
        details={
            "alert_type": alert_type,
            "priority": priority,
        },
    )

    return alert


def _generate_inactive_ngo_alerts(db: Session) -> list[SmartAlert]:
    """Generate alerts for NGOs that haven't updated in 30 days."""
    alerts: list[SmartAlert] = []

    # Get NGOs with no updates in 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(Organization).where(
        Organization.org_type == OrgType.NGO,
        Organization.updated_at < thirty_days_ago,
    )
    inactive_ngos = db.scalars(stmt).all()

    for ngo in inactive_ngos:
        # Check if alert already exists for this NGO (dismiss old ones first)
        stmt = select(SmartAlert).where(
            SmartAlert.subject_org_id == ngo.id,
            SmartAlert.alert_type == "INACTIVE_NGO",
            SmartAlert.dismissed_at.is_(None),
        )
        existing = db.scalar(stmt)

        if not existing:
            alert = _create_alert(
                db,
                alert_type="INACTIVE_NGO",
                message=f"{ngo.name} has not updated their profile in 30+ days",
                priority="MEDIUM",
                subject_org_id=ngo.id,
                recommended_action=f"Send check-in email to {ngo.name}",
            )
            alerts.append(alert)

    return alerts


def _generate_churn_risk_alerts(db: Session) -> list[SmartAlert]:
    """Generate alerts for high-churn-risk donors/NGOs."""
    alerts: list[SmartAlert] = []

    # Get orgs with churn_risk_score > 70 (high risk)
    stmt = select(ChurnPrediction).where(ChurnPrediction.churn_risk_score > 70)
    high_risk = db.scalars(stmt).all()

    for prediction in high_risk:
        # Check for existing alert
        stmt = select(SmartAlert).where(
            SmartAlert.subject_org_id == prediction.org_id,
            SmartAlert.alert_type == "CHURN_RISK",
            SmartAlert.dismissed_at.is_(None),
        )
        existing = db.scalar(stmt)

        if not existing:
            # Get org name
            org = db.get(Organization, prediction.org_id)
            if org:
                alert = _create_alert(
                    db,
                    alert_type="CHURN_RISK",
                    message=f"{org.name} ({prediction.org_type}) has {prediction.churn_risk_score}% churn risk",
                    priority="HIGH" if prediction.churn_risk_score > 85 else "MEDIUM",
                    subject_org_id=prediction.org_id,
                    recommended_action=prediction.intervention_suggested,
                )
                alerts.append(alert)

    return alerts


def _generate_underperforming_campaign_alerts(db: Session) -> list[SmartAlert]:
    """Generate alerts for campaigns underperforming their success probability."""
    alerts: list[SmartAlert] = []

    # Get projects with low success probability (< 30%)
    stmt = select(CampaignPrediction).where(CampaignPrediction.success_probability < 30)
    low_probability = db.scalars(stmt).all()

    for prediction in low_probability:
        # Check for existing alert
        stmt = select(SmartAlert).where(
            SmartAlert.subject_project_id == prediction.project_id,
            SmartAlert.alert_type == "LOW_SUCCESS_PROBABILITY",
            SmartAlert.dismissed_at.is_(None),
        )
        existing = db.scalar(stmt)

        if not existing:
            project = db.get(Project, prediction.project_id)
            if project:
                alert = _create_alert(
                    db,
                    alert_type="LOW_SUCCESS_PROBABILITY",
                    message=f"Campaign '{project.title}' has only {prediction.success_probability}% success probability",
                    priority="MEDIUM",
                    subject_project_id=prediction.project_id,
                    recommended_action="Review campaign strategy or provide additional promotion",
                )
                alerts.append(alert)

    return alerts


def _generate_expiring_document_alerts(db: Session) -> list[SmartAlert]:
    """Generate alerts for documents expiring soon."""
    alerts: list[SmartAlert] = []

    # Get documents expiring within 7 days
    from datetime import date
    soon = date.today() + timedelta(days=7)

    stmt = select(Document).where(
        Document.valid_until_stated <= soon,
        Document.valid_until_stated >= date.today(),
    )
    expiring = db.scalars(stmt).all()

    for doc in expiring:
        # Check for existing alert
        stmt = select(SmartAlert).where(
            SmartAlert.subject_org_id == doc.org_id,
            SmartAlert.alert_type == "EXPIRING_DOCUMENT",
            SmartAlert.dismissed_at.is_(None),
        )
        existing = db.scalar(stmt)

        if not existing:
            org = db.get(Organization, doc.org_id)
            if org:
                days_left = (doc.valid_until_stated - date.today()).days if doc.valid_until_stated else 0
                alert = _create_alert(
                    db,
                    alert_type="EXPIRING_DOCUMENT",
                    message=f"Document '{doc.title}' for {org.name} expires in {days_left} day(s)",
                    priority="HIGH" if days_left <= 3 else "MEDIUM",
                    subject_org_id=doc.org_id,
                    recommended_action=f"Reach out to {org.name} to renew their {doc.doc_type.value} document",
                )
                alerts.append(alert)

    return alerts


def generate_all_alerts(db: Session) -> AlertGenerationResult:
    """Generate all smart alerts. Called by background job."""
    all_alerts: list[SmartAlert] = []

    try:
        # Generate each type of alert
        all_alerts.extend(_generate_inactive_ngo_alerts(db))
        all_alerts.extend(_generate_churn_risk_alerts(db))
        all_alerts.extend(_generate_underperforming_campaign_alerts(db))
        all_alerts.extend(_generate_expiring_document_alerts(db))

        # Commit all alerts
        db.commit()

        logger.info(f"Generated {len(all_alerts)} smart alerts")

    except Exception as e:
        logger.error(f"Error generating alerts: {e}")
        db.rollback()
        all_alerts = []

    return AlertGenerationResult(
        alert_count=len(all_alerts),
        alerts=all_alerts,
    )


def get_alert_queue(db: Session, limit: int = 50, priority_filter: str | None = None) -> list[SmartAlert]:
    """Get active alert queue for admin dashboard."""
    stmt = select(SmartAlert).where(
        SmartAlert.dismissed_at.is_(None),
        SmartAlert.read_at.is_(None),
    )

    if priority_filter and priority_filter in ["LOW", "MEDIUM", "HIGH", "URGENT"]:
        stmt = stmt.where(SmartAlert.priority == priority_filter)

    stmt = stmt.order_by(SmartAlert.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


def dismiss_alert(db: Session, alert_id: str, dismissed_by_user_id: str) -> SmartAlert:
    """Mark alert as dismissed by admin."""
    alert = db.get(SmartAlert, alert_id)
    if alert:
        alert.dismissed_at = datetime.now(timezone.utc)
        alert.dismissed_by_user_id = dismissed_by_user_id

        record_audit(
            db,
            action="alert.dismissed",
            resource_type="alert",
            resource_id=alert_id,
            actor_user_id=dismissed_by_user_id,
            org_id=alert.subject_org_id,
            details={
                "alert_type": alert.alert_type,
                "dismissed_by": dismissed_by_user_id,
            },
        )

        db.commit()

    return alert


def read_alert(db: Session, alert_id: str) -> SmartAlert:
    """Mark alert as read by admin."""
    alert = db.get(SmartAlert, alert_id)
    if alert:
        alert.read_at = datetime.now(timezone.utc)
        db.commit()

    return alert
