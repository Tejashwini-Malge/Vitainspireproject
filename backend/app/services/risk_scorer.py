"""Risk scoring service for NGOs and donors.

Uses deterministic rules with optional Claude enhancement. Scores are 0-100,
with factors breakdown and confidence levels.
"""
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Organization,
    OrgType,
    Document,
    Donation,
    Project,
    ProposalMessage,
    RiskScore,
    VerificationStatus,
    ReviewStatus,
)
from app.audit import record_audit
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class FactorsBreakdown(TypedDict):
    """Risk score factor weights."""
    verification: int  # 0-30 points
    completion_rate: int  # 0-20 points
    donation_velocity: int  # 0-25 points
    account_activity: int  # 0-15 points
    blacklist_risk: int  # 0-10 points


class RiskScoreOut(TypedDict):
    """Risk score result."""
    score_value: int  # 0-100
    factors: FactorsBreakdown
    confidence: str  # LOW, MEDIUM, HIGH
    reasoning: str | None


def _compute_verification_score(org: Organization, db: Session) -> int:
    """Verification status factor (0-30 points). Higher is riskier."""
    if org.verification_status == VerificationStatus.APPROVED:
        return 0
    elif org.verification_status == VerificationStatus.PENDING:
        # Penalize older pending orgs more
        age_days = (datetime.now(timezone.utc) - org.created_at).days
        if age_days > 30:
            return 20
        elif age_days > 14:
            return 15
        else:
            return 10
    else:  # REJECTED
        return 30


def _compute_document_score(org: Organization, db: Session) -> int:
    """Document verification completeness. Lower score = lower risk."""
    # Check for approved documents
    stmt = select(func.count(Document.id)).where(
        Document.org_id == org.id,
        Document.review_status == ReviewStatus.APPROVED
    )
    approved_count = db.scalar(stmt) or 0

    # Required documents for low-risk orgs: at least 2 approved
    if approved_count >= 2:
        return 0  # Low risk
    elif approved_count == 1:
        return 15
    else:
        return 30


def _compute_completion_score(org: Organization, db: Session) -> int:
    """Project completion rate (0-20 points). Higher is riskier."""
    if org.org_type != OrgType.NGO:
        return 0  # Not applicable for donors/CSR

    # Count completed vs total projects
    stmt = select(func.count(Project.id)).where(Project.org_id == org.id)
    total_projects = db.scalar(stmt) or 0

    if total_projects == 0:
        return 10  # New org - slight risk

    # Count "completed" projects (we don't have explicit completion status in model,
    # so use projects with recent updates as proxy for active projects)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(func.count(Project.id)).where(
        Project.org_id == org.id,
        Project.updated_at >= thirty_days_ago
    )
    active_projects = db.scalar(stmt) or 0

    completion_rate = active_projects / total_projects if total_projects > 0 else 0
    if completion_rate >= 0.7:
        return 0  # Good completion rate
    elif completion_rate >= 0.4:
        return 10
    else:
        return 20


def _compute_donation_velocity_score(org: Organization, db: Session) -> int:
    """Donation velocity and patterns (0-25 points). Look for anomalies."""
    if org.org_type == OrgType.NGO:
        # For NGOs, check project fundraising
        stmt = select(func.count(Donation.id)).where(Donation.org_id == org.id)
        total_donations = db.scalar(stmt) or 0
        org_age_days = (datetime.now(timezone.utc) - org.created_at).days

        if total_donations == 0:
            return 15 if org_age_days > 14 else 10

        # Check for unusually rapid donations (fraud signal)
        last_7_days = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = select(func.count(Donation.id)).where(
            Donation.org_id == org.id,
            Donation.created_at >= last_7_days
        )
        recent_donations = db.scalar(stmt) or 0

        # If > 50 donations in 7 days, flag as unusual
        if recent_donations > 50:
            return 25
        elif recent_donations > 20:
            return 15
        else:
            return 0
    else:
        # For donors, check donation frequency
        stmt = select(func.count(Donation.id)).where(Donation.donor_email == org.name)
        donor_donations = db.scalar(stmt) or 0

        if donor_donations == 0:
            return 0  # New donor
        elif donor_donations > 100:
            return 20  # Suspicious high frequency
        else:
            return 0


def _compute_account_activity_score(org: Organization, db: Session) -> int:
    """Account age and activity (0-15 points)."""
    age_days = (datetime.now(timezone.utc) - org.created_at).days

    # Recent accounts are riskier
    if age_days < 7:
        return 15
    elif age_days < 14:
        return 10
    elif age_days < 30:
        return 5
    else:
        return 0


def _compute_blacklist_score(org: Organization) -> int:
    """Blacklist check (0-10 points). Placeholder for external blacklist service."""
    # TODO: Integrate with external fraud database/blacklist API
    return 0


def compute_risk_score_deterministic(org: Organization, db: Session) -> RiskScoreOut:
    """Compute risk score using deterministic rules (always succeeds)."""
    factors: FactorsBreakdown = {
        "verification": _compute_verification_score(org, db),
        "completion_rate": _compute_completion_score(org, db),
        "donation_velocity": _compute_donation_velocity_score(org, db),
        "account_activity": _compute_account_activity_score(org, db),
        "blacklist_risk": _compute_blacklist_score(org),
    }

    # Sum all factors (max = 100)
    total_score = sum(factors.values())
    score_value = min(total_score, 100)

    # Determine confidence based on data completeness
    if sum(1 for v in factors.values() if v > 0) >= 3:
        confidence = "HIGH"
    elif sum(1 for v in factors.values() if v > 0) >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return RiskScoreOut(
        score_value=score_value,
        factors=factors,
        confidence=confidence,
        reasoning=None,
    )


async def compute_risk_score_with_claude(
    org: Organization,
    db: Session,
    deterministic_result: RiskScoreOut,
) -> RiskScoreOut:
    """Enhance deterministic score with Claude reasoning (graceful fallback)."""
    try:
        # Get additional context about the org
        org_type = org.org_type.value
        age_days = (datetime.now(timezone.utc) - org.created_at).days

        prompt = f"""Analyze the risk profile of this organization and refine the risk score:

Organization: {org.name}
Type: {org_type}
Account Age: {age_days} days
Verification: {org.verification_status.value}
Current Risk Score: {deterministic_result['score_value']}/100
Factor Breakdown: {deterministic_result['factors']}

Current reasoning: {deterministic_result.get('reasoning') or 'See factors breakdown'}

Considering the context above, is the risk score appropriate? Should it be adjusted?
Respond with ONLY a JSON object: {{"adjusted_score": <0-100 int>, "reasoning": "<brief explanation>"}}"""

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
                logger.warning(f"Claude API error: {response.text}")
                return deterministic_result

            result = response.json()
            message_text = result["content"][0]["text"]

            # Parse JSON response
            import json
            import re

            json_match = re.search(r'\{.*\}', message_text, re.DOTALL)
            if not json_match:
                return deterministic_result

            claude_result = json.loads(json_match.group())
            adjusted_score = int(claude_result.get("adjusted_score", deterministic_result["score_value"]))
            reasoning = claude_result.get("reasoning", None)

            # Keep adjusted score within bounds and close to original (±15 points max)
            adjusted_score = min(100, max(0, adjusted_score))
            if abs(adjusted_score - deterministic_result["score_value"]) > 15:
                adjusted_score = deterministic_result["score_value"]  # Reject outliers
                reasoning = "Claude adjustment too large, reverting to deterministic"

            return RiskScoreOut(
                score_value=adjusted_score,
                factors=deterministic_result["factors"],
                confidence="HIGH",  # Claude review increases confidence
                reasoning=reasoning,
            )

    except Exception as e:
        logger.warning(f"Claude enhancement failed, using deterministic: {e}")
        return deterministic_result


def save_risk_score(
    db: Session,
    org_id: str,
    score_type: str,
    result: RiskScoreOut,
    correlation_id: str | None = None,
) -> RiskScore:
    """Save risk score to database and record audit trail."""
    risk_score = RiskScore(
        org_id=org_id,
        score_type=score_type,
        score_value=result["score_value"],
        factors=result["factors"],
        confidence=result["confidence"],
        reasoning=result["reasoning"],
        correlation_id=correlation_id,
    )
    db.add(risk_score)

    # Audit the score computation
    record_audit(
        db,
        action="risk_score.computed",
        resource_type="organization",
        resource_id=org_id,
        actor_user_id=None,
        org_id=org_id,
        details={
            "score_type": score_type,
            "score_value": result["score_value"],
            "confidence": result["confidence"],
            "factors": result["factors"],
        },
    )

    db.flush()
    return risk_score


async def compute_and_save_risk_score(
    db: Session,
    org: Organization,
    correlation_id: str | None = None,
) -> RiskScore:
    """Compute risk score (deterministic + optional Claude) and save to DB."""
    # Deterministic always succeeds
    deterministic = compute_risk_score_deterministic(org, db)

    # Try Claude enhancement (graceful fallback)
    if settings.ANTHROPIC_API_KEY:
        result = await compute_risk_score_with_claude(org, db, deterministic)
    else:
        result = deterministic

    return save_risk_score(
        db,
        org.id,
        org.org_type.value,
        result,
        correlation_id,
    )
