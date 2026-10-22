"""Campaign success prediction service.

Predicts the likelihood (0.0-1.0) of a campaign reaching its funding goal
based on historical NGO success rate, sector demand, and comparable campaigns.
"""
from datetime import datetime, timezone
from typing import TypedDict

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Project,
    Organization,
    Donation,
    CampaignPrediction,
)
from app.audit import record_audit
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class CampaignSuccessPredictionResult(TypedDict):
    """Campaign success prediction."""
    success_probability: float  # 0.0-1.0
    reasoning: dict
    confidence: str  # LOW, MEDIUM, HIGH


def _compute_ngo_success_rate(ngo_id: str, db: Session) -> tuple[float, str]:
    """Historical success rate for this NGO's projects."""
    # Get all projects by this NGO
    stmt = select(Project).where(Project.org_id == ngo_id)
    projects = db.scalars(stmt).all()

    if not projects:
        return 0.5, "New NGO, no historical data"

    # For now, assume success if project has any donations
    # In a real system, we'd track completion
    stmt = select(func.count(Donation.id).distinct()).where(
        Project.id.in_(select(Project.id).where(Project.org_id == ngo_id))
    )
    projects_with_donations = db.scalar(stmt) or 0

    success_rate = projects_with_donations / len(projects) if projects else 0
    return success_rate, f"NGO has {success_rate:.0%} historical success rate ({projects_with_donations}/{len(projects)})"


def _compute_sector_demand(project: Project, db: Session) -> tuple[float, str]:
    """Sector popularity and demand."""
    # This would require sector tracking in Project model
    # For now, estimate based on donation velocity in general

    # Get average donations per campaign
    stmt = select(func.count(Donation.id))
    total_donations = db.scalar(stmt) or 1

    stmt = select(func.count(Project.id))
    total_projects = db.scalar(stmt) or 1

    avg_donations_per_project = total_donations / total_projects

    # Estimate this project's position
    if project.id:
        stmt = select(func.count(Donation.id)).where(
            Donation.org_id == project.org_id,
        )
        project_donations = db.scalar(stmt) or 0

        if project_donations > avg_donations_per_project * 1.5:
            return 0.8, "High demand for this NGO's projects"
        elif project_donations > avg_donations_per_project:
            return 0.6, "Above-average demand"

    return 0.5, "Average demand"


def _compute_comparable_performance(project: Project, db: Session) -> tuple[float, str]:
    """Performance of comparable projects."""
    # Find projects of similar NGOs with similar descriptions
    stmt = select(func.count(Donation.id)).where(
        Project.org_id == project.org_id,
    )
    org_projects_donations = db.scalar(stmt) or 0

    # Average donations per project for this org
    stmt = select(func.count(Project.id)).where(Project.org_id == project.org_id)
    org_project_count = db.scalar(stmt) or 1

    org_avg = org_projects_donations / org_project_count

    # Project's current performance
    stmt = select(func.count(Donation.id)).where(Donation.org_id == project.org_id)
    this_project_donations = db.scalar(stmt) or 0

    if this_project_donations > org_avg * 1.2:
        return 0.7, f"Outperforming org average ({this_project_donations:.0f} vs {org_avg:.0f} donations)"
    elif this_project_donations > org_avg:
        return 0.55, "Performing at org average"
    else:
        return 0.4, f"Underperforming org average ({this_project_donations:.0f} vs {org_avg:.0f})"


def predict_campaign_success_deterministic(project: Project, db: Session) -> CampaignSuccessPredictionResult:
    """Predict campaign success using deterministic rules."""
    ngo_rate, ngo_desc = _compute_ngo_success_rate(project.org_id, db)
    sector_demand, sector_desc = _compute_sector_demand(project, db)
    comparable, comparable_desc = _compute_comparable_performance(project, db)

    # Weighted average (NGO history 40%, sector demand 30%, comparable 30%)
    success_probability = ngo_rate * 0.4 + sector_demand * 0.3 + comparable * 0.3
    success_probability = min(1.0, max(0.0, success_probability))

    # Determine confidence based on data
    if ngo_rate > 0.5:
        confidence = "HIGH"
    else:
        confidence = "MEDIUM" if ngo_rate > 0 else "LOW"

    return CampaignSuccessPredictionResult(
        success_probability=success_probability,
        reasoning={
            "ngo_historical_rate": ngo_desc,
            "sector_demand": sector_desc,
            "comparable_performance": comparable_desc,
            "ngo_weight": 0.4,
            "sector_weight": 0.3,
            "comparable_weight": 0.3,
        },
        confidence=confidence,
    )


async def predict_campaign_success_with_claude(
    project: Project,
    db: Session,
    deterministic_result: CampaignSuccessPredictionResult,
) -> CampaignSuccessPredictionResult:
    """Enhance prediction with Claude analysis (graceful fallback)."""
    try:
        prompt = f"""Assess the likelihood of this campaign reaching its funding goal:

Campaign: {project.title}
Summary: {project.summary}
Current Success Probability: {deterministic_result['success_probability']:.0%}
Reasoning:
- NGO Historical Rate: {deterministic_result['reasoning'].get('ngo_historical_rate')}
- Sector Demand: {deterministic_result['reasoning'].get('sector_demand')}
- Comparable Performance: {deterministic_result['reasoning'].get('comparable_performance')}

Based on this information, should the success probability be adjusted?
Respond with JSON: {{"adjusted_probability": <0.0-1.0>, "confidence": "LOW|MEDIUM|HIGH", "reasoning": "..."}}"""

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
            adjusted_prob = float(enhanced.get("adjusted_probability", deterministic_result["success_probability"]))

            # Clamp to valid range
            adjusted_prob = min(1.0, max(0.0, adjusted_prob))

            # Don't deviate too much from deterministic
            if abs(adjusted_prob - deterministic_result["success_probability"]) > 0.25:
                adjusted_prob = deterministic_result["success_probability"]

            return CampaignSuccessPredictionResult(
                success_probability=adjusted_prob,
                reasoning={**deterministic_result["reasoning"], "claude_review": enhanced.get("reasoning")},
                confidence=enhanced.get("confidence", deterministic_result["confidence"]),
            )

    except Exception as e:
        logger.warning(f"Claude enhancement failed: {e}")
        return deterministic_result


def save_campaign_prediction(
    db: Session,
    project_id: str,
    result: CampaignSuccessPredictionResult,
    correlation_id: str | None = None,
) -> CampaignPrediction:
    """Save campaign prediction to database."""
    # Store probability as 0-100 integer
    probability_int = int(result["success_probability"] * 100)

    prediction = CampaignPrediction(
        project_id=project_id,
        success_probability=probability_int,
        reasoning=result["reasoning"],
        confidence=result["confidence"],
        correlation_id=correlation_id,
    )
    db.add(prediction)

    record_audit(
        db,
        action="campaign.success_predicted",
        resource_type="project",
        resource_id=project_id,
        
        details={
            "success_probability": result["success_probability"],
            "confidence": result["confidence"],
        },
    )

    db.flush()
    return prediction


async def predict_and_save_campaign_success(
    db: Session,
    project: Project,
    correlation_id: str | None = None,
) -> CampaignPrediction:
    """Predict campaign success and save to database."""
    deterministic = predict_campaign_success_deterministic(project, db)

    if settings.ANTHROPIC_API_KEY:
        result = await predict_campaign_success_with_claude(project, db, deterministic)
    else:
        result = deterministic

    return save_campaign_prediction(
        db,
        project.id,
        result,
        correlation_id,
    )
