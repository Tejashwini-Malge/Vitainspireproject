"""Admin Intelligence API - Risk scores, anomalies, alerts, predictions, and recommendations.

All endpoints require platform_admin authorization.
"""
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import (
    User,
    Organization,
    RiskScore,
    AnomalyFlag,
    SmartAlert,
    ChurnPrediction,
    CampaignPrediction,
    Document,
)
from app.services.risk_scorer import (
    compute_risk_score_deterministic,
    save_risk_score,
)
from app.services.smart_alerts import (
    generate_all_alerts,
    get_alert_queue,
    dismiss_alert,
    read_alert,
)
import logging

router = APIRouter(prefix="/api/admin", tags=["admin-intelligence"])
logger = logging.getLogger(__name__)


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure user is platform admin."""
    if not user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    return user


# ============================================================================
# Risk Score Endpoints
# ============================================================================


class RiskScoreOut:
    """Risk score response."""
    def __init__(self, score: RiskScore):
        self.org_id = score.org_id
        self.score_type = score.score_type
        self.score_value = score.score_value
        self.factors = score.factors
        self.confidence = score.confidence
        self.reasoning = score.reasoning
        self.computed_at = score.computed_at.isoformat()


@router.get("/risk-scores")
def list_risk_scores(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=500),
    score_type: str | None = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
):
    """List risk scores for all organizations, filterable."""
    stmt = select(RiskScore).order_by(RiskScore.computed_at.desc()).limit(limit)

    if score_type:
        stmt = stmt.where(RiskScore.score_type == score_type)
    stmt = stmt.where(
        RiskScore.score_value >= min_score,
        RiskScore.score_value <= max_score,
    )

    scores = db.scalars(stmt).all()
    return {
        "count": len(scores),
        "scores": [RiskScoreOut(s).__dict__ for s in scores],
    }


@router.get("/risk-scores/{org_id}")
def get_risk_score_detail(
    org_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Get detailed risk score for an organization."""
    stmt = select(RiskScore).where(RiskScore.org_id == org_id).order_by(RiskScore.computed_at.desc())
    latest = db.scalar(stmt)

    if not latest:
        raise HTTPException(status_code=404, detail="No risk score found for this organization")

    return RiskScoreOut(latest).__dict__


@router.post("/risk-scores/recompute")
def recompute_all_risk_scores(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Trigger recomputation of risk scores for all organizations."""
    correlation_id = str(uuid4())

    stmt = select(Organization)
    orgs = db.scalars(stmt).all()

    recomputed = 0
    for org in orgs:
        try:
            # Compute deterministic score (synchronous, no Claude)
            result = compute_risk_score_deterministic(org, db)
            save_risk_score(db, org.id, org.org_type.value, result, correlation_id)
            recomputed += 1
        except Exception as e:
            logger.error(f"Error recomputing risk score for {org.id}: {e}")

    db.commit()
    return {
        "message": f"Risk scores recomputed for {recomputed} organizations",
        "count": recomputed,
        "correlation_id": correlation_id,
    }


# ============================================================================
# Anomaly Flag Endpoints
# ============================================================================


@router.get("/anomalies")
def list_anomaly_flags(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=500),
    severity: str | None = Query(None),
    acknowledged: bool = Query(False),
):
    """List active anomaly flags."""
    stmt = select(AnomalyFlag).order_by(AnomalyFlag.created_at.desc()).limit(limit)

    if severity:
        stmt = stmt.where(AnomalyFlag.severity == severity)

    if not acknowledged:
        stmt = stmt.where(AnomalyFlag.acknowledged_at.is_(None))

    flags = db.scalars(stmt).all()
    return {
        "count": len(flags),
        "flags": [
            {
                "id": f.id,
                "org_id": f.org_id,
                "flag_type": f.flag_type,
                "severity": f.severity,
                "details": f.details,
                "reasoning": f.reasoning,
                "acknowledged": f.acknowledged_at is not None,
                "created_at": f.created_at.isoformat(),
            }
            for f in flags
        ],
    }


@router.post("/anomalies/{flag_id}/acknowledge")
def acknowledge_anomaly_flag(
    flag_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Mark an anomaly flag as reviewed."""
    flag = db.get(AnomalyFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Anomaly flag not found")

    from datetime import datetime, timezone
    flag.acknowledged_by_user_id = admin.id
    flag.acknowledged_at = datetime.now(timezone.utc)

    from app.audit import record_audit
    record_audit(
        db,
        action="anomaly.acknowledged",
        resource_type="anomaly_flag",
        resource_id=flag_id,
        actor_user_id=admin.id,
        org_id=flag.org_id,
        details={"flag_type": flag.flag_type},
    )

    db.commit()
    return {"status": "acknowledged", "flag_id": flag_id}


# ============================================================================
# Smart Alerts Endpoints
# ============================================================================


@router.get("/smart-alerts")
def get_smart_alerts(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=500),
    priority: str | None = Query(None),
):
    """Get active alert queue."""
    alerts = get_alert_queue(db, limit=limit, priority_filter=priority)
    return {
        "count": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "message": a.message,
                "priority": a.priority,
                "subject_org_id": a.subject_org_id,
                "subject_project_id": a.subject_project_id,
                "recommended_action": a.recommended_action,
                "created_at": a.created_at.isoformat(),
                "read": a.read_at is not None,
            }
            for a in alerts
        ],
    }


@router.post("/smart-alerts/{alert_id}/dismiss")
def dismiss_smart_alert(
    alert_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Dismiss a smart alert."""
    alert = dismiss_alert(db, alert_id, admin.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "dismissed", "alert_id": alert_id}


@router.post("/smart-alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Mark alert as read."""
    alert = read_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "read", "alert_id": alert_id}


@router.post("/smart-alerts/generate")
def manually_generate_alerts(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Manually trigger alert generation (normally done by background job)."""
    result = generate_all_alerts(db)
    return {
        "message": f"Generated {result['alert_count']} new alerts",
        "count": result["alert_count"],
    }


# ============================================================================
# Churn Risk Endpoints
# ============================================================================


@router.get("/churn-risks")
def get_churn_risks(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=500),
    min_risk: int = Query(0, ge=0, le=100),
):
    """Get organizations ranked by churn risk."""
    stmt = (
        select(ChurnPrediction)
        .where(ChurnPrediction.churn_risk_score >= min_risk)
        .order_by(ChurnPrediction.churn_risk_score.desc())
        .limit(limit)
    )

    predictions = db.scalars(stmt).all()

    # Get org names
    org_ids = [p.org_id for p in predictions]
    orgs = {o.id: o for o in db.scalars(select(Organization).where(Organization.id.in_(org_ids)))}

    return {
        "count": len(predictions),
        "churn_risks": [
            {
                "org_id": p.org_id,
                "org_name": orgs.get(p.org_id, {}).name if p.org_id in orgs else None,
                "org_type": p.org_type,
                "churn_risk_score": p.churn_risk_score,
                "intervention": p.intervention_suggested,
                "computed_at": p.computed_at.isoformat(),
            }
            for p in predictions
        ],
    }


# ============================================================================
# Campaign Forecast Endpoints
# ============================================================================


@router.get("/campaign-forecasts")
def get_campaign_forecasts(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=500),
    min_success_probability: int = Query(0, ge=0, le=100),
):
    """Get campaign success forecasts."""
    stmt = (
        select(CampaignPrediction)
        .where(CampaignPrediction.success_probability >= min_success_probability)
        .order_by(CampaignPrediction.success_probability.desc())
        .limit(limit)
    )

    predictions = db.scalars(stmt).all()

    from app.models import Project
    project_ids = [p.project_id for p in predictions]
    projects = {
        p.id: p for p in db.scalars(select(Project).where(Project.id.in_(project_ids)))
    }

    return {
        "count": len(predictions),
        "forecasts": [
            {
                "project_id": p.project_id,
                "project_title": projects.get(p.project_id, {}).title if p.project_id in projects else None,
                "success_probability": p.success_probability / 100.0,  # Convert back to 0.0-1.0
                "confidence": p.confidence,
                "computed_at": p.computed_at.isoformat(),
            }
            for p in predictions
        ],
    }


# ============================================================================
# Auto-Approve Recommendations
# ============================================================================


@router.get("/auto-approve-queue")
def get_auto_approve_queue(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=500),
):
    """Get documents recommended for auto-approval."""
    # Documents with low risk scores should be auto-approved
    from app.models import ReviewStatus, VerificationStatus

    stmt = (
        select(Document)
        .where(Document.review_status == ReviewStatus.PENDING_REVIEW)
        .order_by(Document.uploaded_at.desc())
        .limit(limit)
    )

    documents = db.scalars(stmt).all()

    # Get risk scores for orgs
    org_ids = [d.org_id for d in documents]
    risk_scores = {}
    for org_id in set(org_ids):
        risk_stmt = (
            select(RiskScore)
            .where(RiskScore.org_id == org_id)
            .order_by(RiskScore.computed_at.desc())
            .limit(1)
        )
        latest = db.scalar(risk_stmt)
        if latest:
            risk_scores[org_id] = latest

    return {
        "count": len(documents),
        "queue": [
            {
                "document_id": d.id,
                "org_id": d.org_id,
                "document_type": d.doc_type.value,
                "title": d.title,
                "risk_score": risk_scores.get(d.org_id, {}).score_value if d.org_id in risk_scores else None,
                "auto_approve_recommendation": (
                    "APPROVE" if d.org_id in risk_scores and risk_scores[d.org_id].score_value < 30 else None
                ),
                "uploaded_at": d.uploaded_at.isoformat(),
            }
            for d in documents
        ],
    }


# ============================================================================
# Admin Dashboard Summary
# ============================================================================


@router.get("/dashboard/summary")
def get_admin_dashboard_summary(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Get comprehensive admin dashboard summary."""
    from app.models import ReviewStatus

    # Count high-risk orgs
    stmt = select(func.count(RiskScore.id)).where(RiskScore.score_value > 70)
    high_risk_count = db.scalar(stmt) or 0

    # Count active anomaly flags
    stmt = select(func.count(AnomalyFlag.id)).where(AnomalyFlag.acknowledged_at.is_(None))
    active_anomalies = db.scalar(stmt) or 0

    # Count unread alerts
    stmt = select(func.count(SmartAlert.id)).where(
        SmartAlert.read_at.is_(None),
        SmartAlert.dismissed_at.is_(None),
    )
    unread_alerts = db.scalar(stmt) or 0

    # Count high-churn-risk orgs
    stmt = select(func.count(ChurnPrediction.id)).where(ChurnPrediction.churn_risk_score > 70)
    churn_risks = db.scalar(stmt) or 0

    # Count pending documents
    stmt = select(func.count(Document.id)).where(Document.review_status == ReviewStatus.PENDING_REVIEW)
    pending_docs = db.scalar(stmt) or 0

    return {
        "summary": {
            "high_risk_organizations": high_risk_count,
            "active_anomaly_flags": active_anomalies,
            "unread_alerts": unread_alerts,
            "churn_risk_organizations": churn_risks,
            "pending_documents": pending_docs,
        },
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
