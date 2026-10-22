"""Notification service - handles creating notifications for various events."""

from sqlalchemy.orm import Session

from app.models import Notification, Proposal, Organization, User, OrgType
from sqlalchemy import select


def notify_on_new_message(
    db: Session,
    proposal: Proposal,
    sender_id: str,
    sender_type: str,
) -> None:
    """Create notification when a message is sent."""

    # Get the other party (NGO or CSR)
    ngo_org = db.get(Organization, proposal.ngo_id)

    if sender_type == "NGO":
        # CSR needs to be notified
        # Get CSR org
        opportunity = db.get(Proposal, proposal.opportunity_id)
        if opportunity:
            csr_org = db.get(Organization, opportunity.org_id)

            # Get all CSR org members
            from app.models import Membership
            csr_members = db.scalars(
                select(Membership.user_id).where(Membership.org_id == csr_org.id)
            ).all()

            sender = db.get(User, sender_id)

            for member_id in csr_members:
                notif = Notification(
                    recipient_user_id=member_id,
                    proposal_id=proposal.id,
                    notification_type="NEW_MESSAGE",
                    title=f"New message from {ngo_org.name}",
                    message=f"{ngo_org.name} sent you a message on the proposal",
                    actor_user_id=sender_id,
                )
                db.add(notif)
    else:
        # NGO needs to be notified
        from app.models import Membership
        ngo_members = db.scalars(
            select(Membership.user_id).where(Membership.org_id == ngo_org.id)
        ).all()

        # Get CSR org name
        opportunity = db.get(Proposal, proposal.opportunity_id)
        if opportunity:
            csr_org = db.get(Organization, opportunity.org_id)

            sender = db.get(User, sender_id)

            for member_id in ngo_members:
                notif = Notification(
                    recipient_user_id=member_id,
                    proposal_id=proposal.id,
                    notification_type="NEW_MESSAGE",
                    title=f"New message from {csr_org.name}",
                    message=f"{csr_org.name} sent you a message on the proposal",
                    actor_user_id=sender_id,
                )
                db.add(notif)


def notify_on_proposal_approved(
    db: Session,
    proposal: Proposal,
    approver_id: str,
) -> None:
    """Create notification when proposal is approved."""
    from app.models import Membership

    ngo_org = db.get(Organization, proposal.ngo_id)
    ngo_members = db.scalars(
        select(Membership.user_id).where(Membership.org_id == ngo_org.id)
    ).all()

    approver = db.get(User, approver_id)

    for member_id in ngo_members:
        notif = Notification(
            recipient_user_id=member_id,
            proposal_id=proposal.id,
            notification_type="PROPOSAL_APPROVED",
            title="Proposal Approved! 🎉",
            message=f"Your proposal has been approved. A commitment of ₹{proposal.budget_requested/100000:.1f}L has been created.",
            actor_user_id=approver_id,
        )
        db.add(notif)


def notify_on_changes_requested(
    db: Session,
    proposal: Proposal,
    feedback: str,
    requester_id: str,
) -> None:
    """Create notification when changes are requested."""
    from app.models import Membership

    ngo_org = db.get(Organization, proposal.ngo_id)
    ngo_members = db.scalars(
        select(Membership.user_id).where(Membership.org_id == ngo_org.id)
    ).all()

    requester = db.get(User, requester_id)

    for member_id in ngo_members:
        notif = Notification(
            recipient_user_id=member_id,
            proposal_id=proposal.id,
            notification_type="CHANGES_REQUESTED",
            title="Changes Requested",
            message=f"Your proposal needs updates. Review the feedback and respond in the message thread.",
            actor_user_id=requester_id,
        )
        db.add(notif)
