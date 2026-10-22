"""One place to see every conversation you are part of.

Two stores feed this: proposal_messages (an NGO and a funder, keyed by a proposal) and
conversation_messages (direct threads with platform staff, keyed by participants).
They stay separate because they are keyed differently; this module is the single place
that presents them as one list, so a user never has to know which is which.

Every lookup here is batched. The cost of this endpoint is a fixed number of queries
regardless of how many threads a user has, because the obvious implementation -- fetch
the threads, then look up each one's counterparty -- is linear in thread count and gets
slower for exactly the users who use the product most.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.domain.conversations import ADMIN, DONOR, ORG, scope_for
from app.models import (
    Conversation,
    ConversationKind,
    ConversationMessage,
    Membership,
    Opportunity,
    Organization,
    OrgType,
    Proposal,
    ProposalMessage,
    User,
)
from app.schemas import InboxThreadOut

router = APIRouter(prefix="/inbox", tags=["inbox"])

_PREVIEW_CHARS = 160
_STAFF_LABEL = "Platform staff"


def _preview(content: str) -> str:
    return content[:_PREVIEW_CHARS] + ("…" if len(content) > _PREVIEW_CHARS else "")


def _group_by(items, key) -> dict:
    grouped: dict = {}
    for item in items:
        grouped.setdefault(key(item), []).append(item)
    return grouped


def _names_by_id(db: Session, org_ids: set[str]) -> dict[str, str]:
    """Organisation names for a set of ids, in one query."""
    if not org_ids:
        return {}
    rows = db.execute(
        select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
    ).all()
    return {org_id: name for org_id, name in rows}


def _visible_proposals(db: Session, user: User) -> dict[str, str]:
    """Proposal id -> the side this user sits on ("NGO" or "CSR").

    Scoped by membership, so a user who belongs to neither side sees nothing.
    """
    org_rows = db.execute(
        select(Organization.id, Organization.org_type)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id)
    ).all()
    ngo_ids = [oid for oid, otype in org_rows if otype is OrgType.NGO]
    csr_ids = [oid for oid, otype in org_rows if otype is OrgType.CSR]

    sides: dict[str, str] = {}
    if ngo_ids:
        for pid in db.scalars(select(Proposal.id).where(Proposal.ngo_id.in_(ngo_ids))).all():
            sides[pid] = "NGO"
    if csr_ids:
        for pid in db.scalars(
            select(Proposal.id)
            .join(Opportunity, Opportunity.id == Proposal.opportunity_id)
            .where(Opportunity.org_id.in_(csr_ids))
        ).all():
            # A user on both sides is shown as the NGO side; the distinction only drives
            # labelling, and access is already established either way.
            sides.setdefault(pid, "CSR")
    return sides


def _proposal_threads(db: Session, user: User) -> list[InboxThreadOut]:
    sides = _visible_proposals(db, user)
    if not sides:
        return []
    proposal_ids = list(sides)

    proposals = db.scalars(select(Proposal).where(Proposal.id.in_(proposal_ids))).all()
    opportunities = {
        o.id: o
        for o in db.scalars(
            select(Opportunity).where(Opportunity.id.in_({p.opportunity_id for p in proposals}))
        ).all()
    }
    # Counterparties: the funder's organisation for an NGO, the NGO for a funder.
    counterparty_ids = {p.ngo_id for p in proposals} | {o.org_id for o in opportunities.values()}
    org_names = _names_by_id(db, counterparty_ids)

    by_proposal = _group_by(
        db.scalars(
            select(ProposalMessage)
            .where(ProposalMessage.proposal_id.in_(proposal_ids))
            .order_by(ProposalMessage.created_at)
        ).all(),
        lambda m: m.proposal_id,
    )

    threads: list[InboxThreadOut] = []
    for proposal in proposals:
        my_side = sides[proposal.id]
        opportunity = opportunities.get(proposal.opportunity_id)
        if my_side == "NGO":
            other_id = opportunity.org_id if opportunity else None
        else:
            other_id = proposal.ngo_id

        thread = by_proposal.get(proposal.id, [])
        last = thread[-1] if thread else None
        threads.append(
            InboxThreadOut(
                thread_id=proposal.id,
                kind="PROPOSAL",
                title=opportunity.title if opportunity else "(removed opportunity)",
                counterparty_name=org_names.get(other_id, "(unknown organisation)"),
                my_side=my_side,
                status=proposal.status,
                total_messages=len(thread),
                unread_count=sum(1 for m in thread if m.sender_type != my_side and m.read_at is None),
                last_message_preview=_preview(last.content) if last else None,
                last_message_at=last.created_at if last else None,
                last_sender_side=last.sender_type if last else None,
                proposal_id=proposal.id,
                opportunity_id=proposal.opportunity_id,
            )
        )
    return threads


def _direct_threads(db: Session, user: User) -> list[InboxThreadOut]:
    scope = scope_for(db, user)
    conversations = db.scalars(select(Conversation).where(scope.filter())).all()
    if not conversations:
        return []

    sides = {c.id: scope.side_of(c) for c in conversations}
    # scope.filter() and scope.side_of come from the same AccessScope, so this should
    # never drop a row. Guarding anyway: a mismatch must hide a thread, never expose one.
    conversations = [c for c in conversations if sides[c.id] is not None]
    if not conversations:
        return []

    # Counterparty names, batched: organisations for staff viewing org threads, for
    # either side of an ORG_ORG thread, and for the NGO side of a DONOR_NGO thread; donor
    # display names for staff viewing donor threads and for the NGO side of DONOR_NGO.
    needed_org_ids = {
        c.org_id for c in conversations if c.org_id and sides[c.id] == ADMIN and c.kind is ConversationKind.ADMIN_ORG
    }
    for c in conversations:
        if c.kind is ConversationKind.ORG_ORG:
            # Whichever of the two is not mine is the counterparty.
            other = c.counterparty_org_id if c.org_id in scope.org_ids else c.org_id
            if other:
                needed_org_ids.add(other)
        elif c.kind is ConversationKind.DONOR_NGO and sides[c.id] == DONOR and c.org_id:
            needed_org_ids.add(c.org_id)
    org_names = _names_by_id(db, needed_org_ids)

    needed_donor_ids = {
        c.donor_user_id
        for c in conversations
        if c.donor_user_id
        and (
            (sides[c.id] == ADMIN and c.kind is ConversationKind.DONOR_ADMIN)
            or (sides[c.id] == ORG and c.kind is ConversationKind.DONOR_NGO)
        )
    }
    donor_names: dict[str, str] = {}
    if needed_donor_ids:
        donor_names = {
            uid: name
            for uid, name in db.execute(
                select(User.id, User.full_name).where(User.id.in_(needed_donor_ids))
            ).all()
        }

    by_conversation = _group_by(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id.in_([c.id for c in conversations]))
            .order_by(ConversationMessage.created_at)
        ).all(),
        lambda m: m.conversation_id,
    )

    threads: list[InboxThreadOut] = []
    for conversation in conversations:
        my_side = sides[conversation.id]
        if conversation.kind is ConversationKind.ORG_ORG:
            other_org_id = conversation.counterparty_org_id if conversation.org_id in scope.org_ids else conversation.org_id
            counterparty = org_names.get(other_org_id, "(unknown organisation)")
        elif conversation.kind is ConversationKind.DONOR_NGO:
            counterparty = (
                donor_names.get(conversation.donor_user_id, "(unknown donor)")
                if my_side == ORG
                else org_names.get(conversation.org_id, "(unknown organisation)")
            )
        elif my_side == ADMIN:
            if conversation.kind is ConversationKind.ADMIN_ORG:
                counterparty = org_names.get(conversation.org_id, "(unknown organisation)")
            else:
                counterparty = donor_names.get(conversation.donor_user_id, "(unknown donor)")
        else:
            # The organisation and donor sides are both talking to the platform.
            counterparty = _STAFF_LABEL

        thread = by_conversation.get(conversation.id, [])
        last = thread[-1] if thread else None
        threads.append(
            InboxThreadOut(
                thread_id=conversation.id,
                kind=conversation.kind.value,
                title=conversation.subject,
                counterparty_name=counterparty,
                my_side=my_side,
                status=conversation.status,
                total_messages=len(thread),
                unread_count=sum(1 for m in thread if m.sender_side != my_side and m.read_at is None),
                last_message_preview=_preview(last.content) if last else None,
                last_message_at=last.created_at if last else None,
                last_sender_side=last.sender_side if last else None,
                conversation_id=conversation.id,
            )
        )
    return threads


@router.get("", response_model=list[InboxThreadOut])
def list_threads(
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InboxThreadOut]:
    """Every conversation this user is part of, across all channels, newest first."""
    threads = _proposal_threads(db, user) + _direct_threads(db, user)
    if unread_only:
        threads = [t for t in threads if t.unread_count > 0]
    # Threads nobody has spoken in sort last; they have no activity to rank by.
    threads.sort(key=lambda t: (t.last_message_at is not None, t.last_message_at), reverse=True)
    return threads


@router.post("/threads/{proposal_id}/read")
def mark_thread_read(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Mark the other side's messages in a proposal thread as read.

    Direct conversations have their own endpoint, POST /conversations/{id}/read, because
    they are a different store; this one stays specific to proposal threads.
    """
    sides = _visible_proposals(db, user)
    my_side = sides.get(proposal_id)
    if my_side is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    now = datetime.now(UTC)
    marked = 0
    for message in db.scalars(
        select(ProposalMessage).where(
            ProposalMessage.proposal_id == proposal_id,
            ProposalMessage.sender_type != my_side,
            ProposalMessage.read_at.is_(None),
        )
    ).all():
        message.read_at = now
        marked += 1

    db.commit()
    return {"marked_read": marked}
