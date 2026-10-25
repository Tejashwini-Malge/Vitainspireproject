"""Notification service - handles creating notifications for various events."""

from sqlalchemy.orm import Session

from app.models import Membership, Notification, Opportunity, Proposal, Organization, User, OrgType
from sqlalchemy import select


def _org_member_ids(db: Session, org_id: str) -> list[str]:
    return list(db.scalars(select(Membership.user_id).where(Membership.org_id == org_id)).all())


def notify_on_new_message(
    db: Session,
    proposal: Proposal,
    sender_id: str,
    sender_type: str,
) -> None:
    """Notify the party that did not send the message.

    `proposal.opportunity_id` points at an Opportunity, not a Proposal. Looking it up with
    the wrong model returned None and silently skipped every notification, in both
    directions -- which is why the in-app thread never raised a badge for either side.
    """
    ngo_org = db.get(Organization, proposal.ngo_id)
    opportunity = db.get(Opportunity, proposal.opportunity_id)
    if ngo_org is None or opportunity is None:
        return
    csr_org = db.get(Organization, opportunity.org_id)
    if csr_org is None:
        return

    if sender_type == "NGO":
        recipients = _org_member_ids(db, csr_org.id)
        sender_name = ngo_org.name
    else:
        recipients = _org_member_ids(db, ngo_org.id)
        sender_name = csr_org.name

    for member_id in recipients:
        if member_id == sender_id:
            continue
        db.add(
            Notification(
                recipient_user_id=member_id,
                proposal_id=proposal.id,
                opportunity_id=opportunity.id,
                notification_type="NEW_MESSAGE",
                title=f"New message from {sender_name}",
                message=f"{sender_name} sent you a message on the proposal",
                actor_user_id=sender_id,
            )
        )


def notify_on_shortlisted(
    db: Session,
    opportunity: Opportunity,
    ngo_ids: list[str],
    actor_id: str,
    previously_shortlisted: frozenset[str] = frozenset(),
) -> None:
    """Tell each newly shortlisted NGO that a CSR selected it for this opportunity.

    Only NGOs that were not on the previous current revision are notified, so revising a
    shortlist does not re-notify organisations that were already on it.
    """
    csr_org = db.get(Organization, opportunity.org_id)
    if csr_org is None:
        return

    for ngo_id in ngo_ids:
        if ngo_id in previously_shortlisted:
            continue
        for member_id in _org_member_ids(db, ngo_id):
            db.add(
                Notification(
                    recipient_user_id=member_id,
                    opportunity_id=opportunity.id,
                    notification_type="SHORTLISTED",
                    title=f"{csr_org.name} shortlisted you",
                    message=(
                        f"{csr_org.name} selected your organisation for "
                        f"“{opportunity.title}”. Review the requirements and submit a "
                        "proposal, or message them to discuss budget or timeline first."
                    ),
                    actor_user_id=actor_id,
                )
            )


def notify_on_milestone_update(
    db: Session,
    proposal: Proposal,
    milestone_title: str,
    new_status: str,
    actor_id: str,
) -> None:
    """Tell the funding CSR that the NGO moved a delivery milestone."""
    opportunity = db.get(Opportunity, proposal.opportunity_id)
    ngo_org = db.get(Organization, proposal.ngo_id)
    if opportunity is None or ngo_org is None:
        return

    for member_id in _org_member_ids(db, opportunity.org_id):
        if member_id == actor_id:
            continue
        db.add(
            Notification(
                recipient_user_id=member_id,
                proposal_id=proposal.id,
                opportunity_id=opportunity.id,
                notification_type="MILESTONE_UPDATED",
                title=f"{ngo_org.name}: {milestone_title}",
                message=f"Milestone “{milestone_title}” is now {new_status}.",
                actor_user_id=actor_id,
            )
        )


def notify_on_proposal_approved(
    db: Session,
    proposal: Proposal,
    approver_id: str,
    committed_amount_minor: int | None = None,
) -> None:
    """Create notification when proposal is approved.

    `committed_amount_minor` is the amount actually committed, which after a negotiation
    may be lower than what the NGO originally requested.
    """
    ngo_org = db.get(Organization, proposal.ngo_id)
    if ngo_org is None:
        return
    opportunity = db.get(Opportunity, proposal.opportunity_id)
    amount = committed_amount_minor if committed_amount_minor is not None else proposal.budget_requested

    for member_id in _org_member_ids(db, ngo_org.id):
        db.add(
            Notification(
                recipient_user_id=member_id,
                proposal_id=proposal.id,
                opportunity_id=opportunity.id if opportunity else None,
                notification_type="PROPOSAL_APPROVED",
                title="Proposal approved",
                message=(
                    f"Your proposal has been approved with a commitment of "
                    f"₹{amount / 100000:.1f}L. Add your delivery milestones to start work."
                ),
                actor_user_id=approver_id,
            )
        )


def notify_on_changes_requested(
    db: Session,
    proposal: Proposal,
    feedback: str,
    requester_id: str,
) -> None:
    """Create notification when changes are requested."""
    ngo_org = db.get(Organization, proposal.ngo_id)
    if ngo_org is None:
        return
    opportunity = db.get(Opportunity, proposal.opportunity_id)
    detail = feedback.strip() if feedback and feedback.strip() else (
        "Review the feedback and respond in the message thread."
    )

    for member_id in _org_member_ids(db, ngo_org.id):
        db.add(
            Notification(
                recipient_user_id=member_id,
                proposal_id=proposal.id,
                opportunity_id=opportunity.id if opportunity else None,
                notification_type="CHANGES_REQUESTED",
                title="Changes requested",
                message=detail,
                actor_user_id=requester_id,
            )
        )
