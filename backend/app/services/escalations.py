"""Escalation service - checks for proposals needing admin attention."""

from datetime import datetime, timedelta, UTC
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models import (
    Proposal,
    ProposalTimeline,
    ProposalEscalation,
    Notification,
)


def check_and_create_escalations(db: Session) -> dict:
    """
    Check for proposals with no activity for 5+ days and create escalations.
    Returns summary of escalations created.
    """
    now = datetime.now(UTC)
    escalations_created = {"five_day": 0, "ten_day": 0}

    # Get all proposals that are in SUBMITTED or CHANGES_REQUESTED state
    proposals = db.scalars(
        select(Proposal).where(
            Proposal.status.in_(["SUBMITTED", "CHANGES_REQUESTED"])
        )
    ).all()

    for proposal in proposals:
        # Get timeline
        timeline = db.scalar(
            select(ProposalTimeline).where(ProposalTimeline.proposal_id == proposal.id)
        )

        if not timeline:
            continue

        # Check if last activity was more than 5 days ago
        days_since_activity = (now - timeline.last_activity_at).days

        # Get existing escalations
        escalations = db.scalars(
            select(ProposalEscalation).where(
                ProposalEscalation.proposal_id == proposal.id,
                ProposalEscalation.status == "PENDING",
            )
        ).all()

        has_five_day_escalation = any(e.reason == "NO_REPLY_5_DAYS" for e in escalations)
        has_ten_day_escalation = any(e.reason == "NO_REPLY_10_DAYS" for e in escalations)

        # Create 5-day escalation if needed
        if days_since_activity >= 5 and not has_five_day_escalation:
            escalation_5d = ProposalEscalation(
                proposal_id=proposal.id,
                reason="NO_REPLY_5_DAYS",
                admin_notes=f"No activity for {days_since_activity} days. Waiting on: {timeline.waiting_on}",
                status="PENDING",
            )
            db.add(escalation_5d)
            db.flush()

            # Create notification for admins
            # TODO: Send to admin users

            escalations_created["five_day"] += 1

        # Create 10-day escalation if needed
        if days_since_activity >= 10 and not has_ten_day_escalation:
            escalation_10d = ProposalEscalation(
                proposal_id=proposal.id,
                reason="NO_REPLY_10_DAYS",
                admin_notes=f"No activity for {days_since_activity} days. Requires admin intervention.",
                status="PENDING",
            )
            db.add(escalation_10d)
            db.flush()

            escalations_created["ten_day"] += 1

    db.commit()
    return escalations_created


def get_pending_escalations(db: Session, limit: int = 100) -> list:
    """Get all pending escalations."""
    escalations = db.scalars(
        select(ProposalEscalation)
        .where(ProposalEscalation.status == "PENDING")
        .order_by(ProposalEscalation.escalated_at.desc())
        .limit(limit)
    ).all()

    return escalations


def resolve_escalation(db: Session, escalation_id: str, admin_notes: str = "") -> None:
    """Mark an escalation as resolved."""
    escalation = db.get(ProposalEscalation, escalation_id)
    if escalation:
        escalation.status = "RESOLVED"
        escalation.resolved_at = datetime.now(UTC)
        if admin_notes:
            escalation.admin_notes = admin_notes
        db.commit()


def send_admin_follow_up(
    db: Session,
    proposal_id: str,
    admin_id: str,
    follow_up_message: str,
    recipient_type: str,  # "CSR" or "NGO"
) -> None:
    """
    Send a follow-up message from admin to CSR or NGO.
    Creates a ProposalMessage with admin as sender.
    """
    from app.models import ProposalMessage, User

    admin_user = db.get(User, admin_id)

    message = ProposalMessage(
        proposal_id=proposal_id,
        sender_id=admin_id,
        sender_type="ADMIN",
        content=f"[ADMIN FOLLOW-UP] {follow_up_message}",
    )
    db.add(message)
    db.flush()

    # Update timeline
    timeline = db.scalar(
        select(ProposalTimeline).where(ProposalTimeline.proposal_id == proposal_id)
    )
    if timeline:
        timeline.last_activity_at = datetime.now(UTC)

    # Create notification for recipient org
    from app.models import Proposal, Organization, Membership

    proposal = db.get(Proposal, proposal_id)

    if recipient_type == "NGO":
        org = db.get(Organization, proposal.ngo_id)
    else:
        # Get CSR org
        from app.models import Opportunity
        opp = db.get(Opportunity, proposal.opportunity_id)
        org = db.get(Organization, opp.org_id)

    members = db.scalars(
        select(Membership.user_id).where(Membership.org_id == org.id)
    ).all()

    for member_id in members:
        notif = Notification(
            recipient_user_id=member_id,
            proposal_id=proposal_id,
            notification_type="ADMIN_FOLLOW_UP",
            title="Admin Follow-up Required",
            message=f"An admin has sent you a follow-up message regarding this proposal.",
            actor_user_id=admin_id,
        )
        db.add(notif)

    db.commit()
