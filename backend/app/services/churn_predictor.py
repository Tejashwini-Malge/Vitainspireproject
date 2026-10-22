"""Churn prediction service for donors and NGOs.

Predicts the likelihood (0-100) that a donor/NGO will become inactive
in the next 90 days based on engagement trends, behavior changes, and cohort comparison.
"""
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Organization,
    OrgType,
    Donation,
    ProposalMessage,
    ChurnPrediction,
)
from app.audit import record_audit
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ChurnPredictionResult(TypedDict):
    """Churn prediction result."""
    churn_risk_score: int  # 0-100: % likelihood inactive in 90 days
    factors: dict
    intervention_suggested: str | None
    reasoning: str | None


def _compute_engagement_trend(org_id: str, db: Session) -> tuple[float, str]:
    """Compute engagement trend over time. Returns (trend_score 0-100, description)."""
    now = datetime.now(timezone.utc)

    # Compare donations/activity in last 30 days vs previous 30 days
    last_30 = now - timedelta(days=30)
    prev_30_start = now - timedelta(days=60)
    prev_30_end = now - timedelta(days=30)

    stmt = select(func.count(Donation.id)).where(
        Donation.org_id == org_id,
        Donation.created_at >= last_30,
    )
    recent_activity = db.scalar(stmt) or 0

    stmt = select(func.count(Donation.id)).where(
        Donation.org_id == org_id,
        Donation.created_at >= prev_30_start,
        Donation.created_at < prev_30_end,
    )
    previous_activity = db.scalar(stmt) or 0

    if previous_activity == 0:
        if recent_activity == 0:
            trend_score = 70.0  # No activity at all - high churn risk
            description = "No activity in 60 days"
        else:
            trend_score = 20.0  # New activity - low churn risk
            description = "Recent activity surge"
    else:
        ratio = recent_activity / previous_activity
        if ratio > 1.0:
            trend_score = max(0, 40 - (ratio - 1) * 20)  # Growing activity = lower churn
            description = f"Activity growing ({ratio:.1f}x)"
        elif ratio > 0.7:
            trend_score = 40  # Stable activity
            description = "Stable activity"
        elif ratio > 0.3:
            trend_score = 65  # Declining
            description = f"Activity declining ({ratio:.1f}x)"
        else:
            trend_score = 80.0  # Severe decline
            description = f"Severe decline ({ratio:.1f}x)"

    return trend_score, description


def _compute_recency_score(org_id: str, db: Session) -> tuple[float, str]:
    """Score based on how recently the org was active. Returns (score 0-100, description)."""
    stmt = select(func.max(Donation.created_at)).where(Donation.org_id == org_id)
    last_activity = db.scalar(stmt)

    if not last_activity:
        return 90.0, "No donation activity ever"

    days_since = (datetime.now(timezone.utc) - last_activity).days

    if days_since < 7:
        return 10.0, f"Active {days_since}d ago"
    elif days_since < 30:
        return 30.0, f"Last activity {days_since}d ago"
    elif days_since < 60:
        return 60.0, f"Inactive {days_since}d ago"
    else:
        return 85.0, f"Very inactive ({days_since}d)"


def _compute_cohort_score(org: Organization, db: Session) -> tuple[float, str]:
    """Compare with similar orgs to find if this org is an outlier. Returns (score, description)."""
    # Get average donation frequency for similar org types
    org_type = org.org_type

    stmt = select(func.count(Donation.id)).where(
        Donation.org_id.in_(
            select(Organization.id).where(Organization.org_type == org_type)
        )
    )
    cohort_total = db.scalar(stmt) or 1

    # This org's donations
    stmt = select(func.count(Donation.id)).where(Donation.org_id == org.id)
    this_org_donations = db.scalar(stmt) or 0

    # Estimate cohort average
    stmt = select(func.count(Organization.id)).where(Organization.org_type == org_type)
    cohort_size = db.scalar(stmt) or 1

    cohort_avg = cohort_total / cohort_size if cohort_size > 0 else 0

    # Compare this org's activity to cohort
    if this_org_donations < cohort_avg * 0.3:
        return 75.0, "Below-average activity in cohort"
    elif this_org_donations < cohort_avg * 0.7:
        return 45.0, "Below-average activity"
    elif this_org_donations > cohort_avg * 2:
        return 20.0, "Above-average activity"
    else:
        return 40.0, "Average activity for cohort"


def predict_churn_deterministic(org: Organization, db: Session) -> ChurnPredictionResult:
    """Predict churn risk using deterministic rules."""
    engagement_score, engagement_desc = _compute_engagement_trend(org.id, db)
    recency_score, recency_desc = _compute_recency_score(org.id, db)
    cohort_score, cohort_desc = _compute_cohort_score(org, db)

    # Weighted average (engagement 40%, recency 40%, cohort 20%)
    churn_risk = int(engagement_score * 0.4 + recency_score * 0.4 + cohort_score * 0.2)
    churn_risk = min(100, max(0, churn_risk))

    factors = {
        "engagement_trend": int(engagement_score),
        "recency": int(recency_score),
        "cohort_comparison": int(cohort_score),
    }

    intervention = None
    if churn_risk > 75:
        intervention = f"Contact immediately: {org.name} shows severe churn risk"
    elif churn_risk > 60:
        intervention = f"Reach out to {org.name} with engagement incentives"
    elif churn_risk > 45:
        intervention = f"Monitor {org.name} activity closely"

    reasoning = f"{engagement_desc}. {recency_desc}. {cohort_desc}."

    return ChurnPredictionResult(
        churn_risk_score=churn_risk,
        factors=factors,
        intervention_suggested=intervention,
        reasoning=reasoning,
    )


async def predict_churn_with_claude(
    org: Organization,
    db: Session,
    deterministic_result: ChurnPredictionResult,
) -> ChurnPredictionResult:
    """Enhance churn prediction with Claude analysis (graceful fallback)."""
    try:
        prompt = f"""Analyze churn risk for this organization:

Organization: {org.name}
Type: {org.org_type.value}
Current Churn Risk Score: {deterministic_result['churn_risk_score']}/100
Factors: {deterministic_result['factors']}
Reasoning: {deterministic_result['reasoning']}

Is this churn risk assessment accurate? Should the score be adjusted?
Should the intervention strategy change?
Respond with JSON: {{"adjusted_score": <0-100>, "intervention": "...", "reasoning": "..."}}"""

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-opus-4-1-20250805",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if response.status_code != 200:
                return deterministic_result

            result = response.json()
            message_text = result["content"][0]["text"]

            import json
            import re
            json_match = re.search(r'\{.*\}', message_text, re.DOTALL)
            if not json_match:
                return deterministic_result

            enhanced = json.loads(json_match.group())
            adjusted_score = int(enhanced.get("adjusted_score", deterministic_result["churn_risk_score"]))

            # Don't allow too much deviation
            if abs(adjusted_score - deterministic_result["churn_risk_score"]) > 20:
                adjusted_score = deterministic_result["churn_risk_score"]

            return ChurnPredictionResult(
                churn_risk_score=adjusted_score,
                factors=deterministic_result["factors"],
                intervention_suggested=enhanced.get("intervention", deterministic_result["intervention_suggested"]),
                reasoning=enhanced.get("reasoning", deterministic_result["reasoning"]),
            )

    except Exception as e:
        logger.warning(f"Claude enhancement failed: {e}")
        return deterministic_result


def save_churn_prediction(
    db: Session,
    org_id: str,
    org_type: str,
    result: ChurnPredictionResult,
    correlation_id: str | None = None,
) -> ChurnPrediction:
    """Save churn prediction to database."""
    prediction = ChurnPrediction(
        org_id=org_id,
        org_type=org_type,
        churn_risk_score=result["churn_risk_score"],
        factors=result["factors"],
        intervention_suggested=result["intervention_suggested"],
        correlation_id=correlation_id,
    )
    db.add(prediction)

    record_audit(
        db,
        action="churn.predicted",
        resource_type="organization",
        resource_id=org_id,
        actor_user_id=None,
        org_id=org_id,
        details={
            "churn_risk_score": result["churn_risk_score"],
            "intervention": result["intervention_suggested"],
        },
    )

    db.flush()
    return prediction


async def predict_and_save_churn(
    db: Session,
    org: Organization,
    correlation_id: str | None = None,
) -> ChurnPrediction:
    """Predict churn and save to database."""
    deterministic = predict_churn_deterministic(org, db)

    if settings.ANTHROPIC_API_KEY:
        result = await predict_churn_with_claude(org, db, deterministic)
    else:
        result = deterministic

    return save_churn_prediction(
        db,
        org.id,
        org.org_type.value,
        result,
        correlation_id,
    )
