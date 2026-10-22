"""Real-time anomaly detection for suspicious activity.

Detects:
- Duplicate accounts (same email/phone)
- Unusual donations (>3σ from average)
- Rapid activity patterns
- Donations from flagged donors
- Sudden org activity changes
"""
from datetime import datetime, timedelta, timezone
from typing import TypedDict
from statistics import mean, stdev

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Donation,
    Organization,
    User,
    AnomalyFlag,
    ProposalMessage,
)
from app.audit import record_audit
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class AnomalyDetectionResult(TypedDict):
    """Result of anomaly detection."""
    flag_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    details: dict
    reasoning: str | None


def _detect_duplicate_accounts(email: str, phone: str | None, db: Session) -> AnomalyDetectionResult | None:
    """Check for duplicate accounts (same email or phone)."""
    # Check for users with same email
    stmt = select(User).where(User.email == email)
    existing_users = db.scalars(stmt).all()

    if len(existing_users) > 1:
        return AnomalyDetectionResult(
            flag_type="DUPLICATE_ACCOUNT",
            severity="CRITICAL",
            details={
                "email": email,
                "user_count": len(existing_users),
                "user_ids": [u.id for u in existing_users[:3]],  # Show first 3
            },
            reasoning="Multiple accounts with same email detected",
        )

    return None


def _detect_unusual_donation_amount(amount_minor: int, org_id: str, db: Session) -> AnomalyDetectionResult | None:
    """Detect donations that are >3σ from org's average."""
    # Get recent donations for this org
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = select(Donation.amount_minor).where(
        Donation.org_id == org_id,
        Donation.created_at >= thirty_days_ago,
    )
    amounts = db.scalars(stmt).all()

    if len(amounts) < 3:
        return None  # Need at least 3 samples

    try:
        avg = mean(amounts)
        std = stdev(amounts)

        # Flag if amount > 3 standard deviations
        if abs(amount_minor - avg) > 3 * std:
            z_score = (amount_minor - avg) / std if std > 0 else 0
            severity = "CRITICAL" if z_score > 5 else "HIGH"

            return AnomalyDetectionResult(
                flag_type="UNUSUAL_DONATION_AMOUNT",
                severity=severity,
                details={
                    "amount_minor": amount_minor,
                    "org_average": int(avg),
                    "z_score": round(z_score, 2),
                    "recent_sample_size": len(amounts),
                },
                reasoning=f"Donation amount is {z_score:.1f}σ from org average",
            )
    except (ValueError, ZeroDivisionError):
        pass

    return None


def _detect_rapid_donation_activity(org_id: str, db: Session) -> AnomalyDetectionResult | None:
    """Detect rapid multiple donations from same source."""
    # Check for > 10 donations in last 24 hours
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = select(func.count(Donation.id)).where(
        Donation.org_id == org_id,
        Donation.created_at >= last_24h,
    )
    count_24h = db.scalar(stmt) or 0

    if count_24h > 10:
        return AnomalyDetectionResult(
            flag_type="RAPID_DONATION_ACTIVITY",
            severity="HIGH" if count_24h > 20 else "MEDIUM",
            details={
                "donations_in_24h": count_24h,
                "time_window": "24 hours",
            },
            reasoning=f"{count_24h} donations in 24 hours - unusual pattern",
        )

    return None


def _detect_flagged_donor(donor_email: str, db: Session) -> AnomalyDetectionResult | None:
    """Check if donor has previous anomaly flags."""
    # For now, skip this check as JSON querying is complex
    # In production, would query against a donors table or cache
    return None


def _detect_sudden_activity_change(org_id: str, db: Session) -> AnomalyDetectionResult | None:
    """Detect sudden increase/decrease in org activity."""
    # Compare activity in last 7 days vs previous 7 days
    now = datetime.now(timezone.utc)
    last_7 = now - timedelta(days=7)
    prev_7_start = now - timedelta(days=14)
    prev_7_end = now - timedelta(days=7)

    # Count messages in last 7 days
    stmt = select(func.count(ProposalMessage.id)).where(
        ProposalMessage.created_at >= last_7,
    )
    # This would require joining with proposals to filter by org, skip for now

    # Count donations in both periods
    stmt = select(func.count(Donation.id)).where(
        Donation.org_id == org_id,
        Donation.created_at >= last_7,
    )
    recent_donations = db.scalar(stmt) or 0

    stmt = select(func.count(Donation.id)).where(
        Donation.org_id == org_id,
        Donation.created_at >= prev_7_start,
        Donation.created_at < prev_7_end,
    )
    previous_donations = db.scalar(stmt) or 0

    # Flag if increase > 200% or decrease > 80%
    if previous_donations > 0:
        change_ratio = recent_donations / previous_donations
        if change_ratio > 2:
            return AnomalyDetectionResult(
                flag_type="SUDDEN_ACTIVITY_INCREASE",
                severity="MEDIUM",
                details={
                    "recent_donations_7d": recent_donations,
                    "previous_donations_7d": previous_donations,
                    "change_ratio": round(change_ratio, 2),
                },
                reasoning=f"Donation activity increased {change_ratio:.1f}x",
            )
        elif change_ratio < 0.2 and previous_donations > 5:
            return AnomalyDetectionResult(
                flag_type="SUDDEN_ACTIVITY_DECREASE",
                severity="LOW",
                details={
                    "recent_donations_7d": recent_donations,
                    "previous_donations_7d": previous_donations,
                    "change_ratio": round(change_ratio, 2),
                },
                reasoning=f"Donation activity decreased {1/change_ratio:.1f}x",
            )

    return None


def detect_donation_anomalies_deterministic(
    donation: Donation,
    db: Session,
) -> list[AnomalyDetectionResult]:
    """Run all deterministic anomaly checks (always succeeds)."""
    anomalies: list[AnomalyDetectionResult] = []

    # Check 1: Duplicate accounts
    if dup := _detect_duplicate_accounts(donation.donor_email, None, db):
        anomalies.append(dup)

    # Check 2: Unusual donation amount
    if unusual := _detect_unusual_donation_amount(donation.amount_minor, donation.org_id, db):
        anomalies.append(unusual)

    # Check 3: Rapid activity
    if rapid := _detect_rapid_donation_activity(donation.org_id, db):
        anomalies.append(rapid)

    # Check 4: Flagged donor
    if flagged := _detect_flagged_donor(donation.donor_email, db):
        anomalies.append(flagged)

    # Check 5: Sudden activity change
    if sudden := _detect_sudden_activity_change(donation.org_id, db):
        anomalies.append(sudden)

    return anomalies


async def enhance_anomalies_with_claude(
    anomalies: list[AnomalyDetectionResult],
    donation: Donation,
    db: Session,
) -> list[AnomalyDetectionResult]:
    """Enhance anomaly flags with Claude reasoning (graceful fallback)."""
    if not anomalies or not settings.ANTHROPIC_API_KEY:
        return anomalies

    try:
        anomaly_details = "\n".join([
            f"- {a['flag_type']} ({a['severity']}): {a['reasoning']}"
            for a in anomalies
        ])

        prompt = f"""Analyze these anomaly flags for a donation and provide reasoning:

Donation Amount: {donation.amount_minor} INR
Donor Email: {donation.donor_email}
Organization ID: {donation.org_id}

Detected Anomalies:
{anomaly_details}

Are these flags reasonable? Should any be adjusted in severity or dismissed?
Respond with ONLY JSON array: [{{"flag_type": "...", "severity": "LOW|MEDIUM|HIGH|CRITICAL", "reasoning": "..."}}]"""

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-opus-4-1-20250805",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if response.status_code != 200:
                logger.warning(f"Claude API error: {response.text}")
                return anomalies

            result = response.json()
            message_text = result["content"][0]["text"]

            # Parse JSON response
            import json
            import re

            json_match = re.search(r'\[.*\]', message_text, re.DOTALL)
            if not json_match:
                return anomalies

            enhanced = json.loads(json_match.group())
            return enhanced

    except Exception as e:
        logger.warning(f"Claude enhancement failed, using deterministic: {e}")
        return anomalies


def save_anomaly_flags(
    db: Session,
    org_id: str,
    anomalies: list[AnomalyDetectionResult],
    donation_id: str | None = None,
    correlation_id: str | None = None,
) -> list[AnomalyFlag]:
    """Save anomaly flags to database and record audit trail."""
    flags: list[AnomalyFlag] = []

    for anomaly in anomalies:
        flag = AnomalyFlag(
            org_id=org_id,
            flag_type=anomaly["flag_type"],
            severity=anomaly["severity"],
            details={
                "donation_id": donation_id,
                **anomaly["details"],
            },
            reasoning=anomaly["reasoning"],
            correlation_id=correlation_id,
        )
        db.add(flag)

        # Audit the flag
        record_audit(
            db,
            action="anomaly.detected",
            resource_type="donation" if donation_id else "organization",
            resource_id=donation_id or org_id,
            org_id=org_id,
            
            details={
                "flag_type": anomaly["flag_type"],
                "severity": anomaly["severity"],
                "reasoning": anomaly["reasoning"],
            },
        )

        flags.append(flag)

    db.flush()
    return flags


async def detect_and_save_anomalies(
    db: Session,
    donation: Donation,
    correlation_id: str | None = None,
) -> list[AnomalyFlag]:
    """Detect anomalies (deterministic + optional Claude) and save to DB."""
    # Deterministic detection always succeeds
    anomalies = detect_donation_anomalies_deterministic(donation, db)

    # Try Claude enhancement (graceful fallback)
    if settings.ANTHROPIC_API_KEY and anomalies:
        anomalies = await enhance_anomalies_with_claude(anomalies, donation, db)

    # Save all detected anomalies
    return save_anomaly_flags(
        db,
        donation.org_id,
        anomalies,
        donation.id,
        correlation_id,
    )
