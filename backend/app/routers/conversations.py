"""Direct messaging between platform staff, organisations, and donors.

Proposal threads are handled in app.routers.proposals and stay tied to a specific
proposal. This covers every other channel: an NGO or CSR reaching platform staff, a
donor reaching staff, an NGO and a CSR reaching each other directly (general enquiry,
not tied to any proposal), and an individual donor reaching a specific NGO directly.
Access is decided by app.domain.conversations, never inline here.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, is_member, require_membership
from app.domain.conversations import ADMIN, DONOR, ORG, scope_for, side_for
from app.models import (
    Conversation,
    ConversationKind,
    ConversationMessage,
    Membership,
    Organization,
    OrgType,
    Role,
    User,
)
from app.schemas import (
    ConversationMessageIn,
    ConversationMessageOut,
    ConversationOpenIn,
    ConversationOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

MEMBER_ROLES = frozenset({Role.OWNER, Role.ADMIN, Role.MEMBER})
_REAL_ORG_TYPES = (OrgType.NGO, OrgType.CSR)


def _own_real_org(db: Session, user: User) -> Organization | None:
    """The NGO or CSR organisation this user belongs to, if any.

    An individual donor also gets an Organization row (org_type INDIVIDUAL) purely
    for internal bookkeeping; it is not a participant identity and must never be
    treated as one here, or every donor would be misclassified as an organisation.
    """
    return db.scalar(
        select(Organization)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id, Organization.org_type.in_(_REAL_ORG_TYPES))
    )


def _out(conversation: Conversation, my_side: str) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        kind=conversation.kind.value,
        subject=conversation.subject,
        org_id=conversation.org_id,
        counterparty_org_id=conversation.counterparty_org_id,
        donor_user_id=conversation.donor_user_id,
        status=conversation.status,
        created_at=conversation.created_at,
        closed_at=conversation.closed_at,
        my_side=my_side,
    )


def _message_out(m: ConversationMessage) -> ConversationMessageOut:
    return ConversationMessageOut(
        id=m.id,
        conversation_id=m.conversation_id,
        sender_user_id=m.sender_user_id,
        sender_side=m.sender_side,
        content=m.content,
        created_at=m.created_at,
        read_at=m.read_at,
    )


def _load_participating(db: Session, conversation_id: str, user: User) -> tuple[Conversation, str]:
    """Fetch a conversation this user takes part in, or 404.

    A non-participant gets 404 rather than 403: whether a conversation exists between
    other people is not information they are entitled to.
    """
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    my_side = side_for(db, conversation, user)
    if my_side is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation, my_side


def _post_message(db: Session, conversation: Conversation, user: User, my_side: str, content: str) -> None:
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            sender_user_id=user.id,
            sender_side=my_side,
            content=content.strip(),
        )
    )
    db.flush()
    record_audit(
        db,
        action="conversation.message_sent",
        resource_type="conversation",
        resource_id=conversation.id,
        actor_user_id=user.id,
        org_id=conversation.org_id,
        details={"sent_as": my_side},
    )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def open_conversation(
    payload: ConversationOpenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Open a thread and post its first message, or add to an already-open one.

    A conversation with no message is an empty row nobody asked for, so the opening
    message is required and written in the same transaction. Reaching the same
    organisation again while a thread is still OPEN posts into it rather than
    spawning a duplicate.
    """
    if payload.org_id is not None and payload.target_org_id is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Set either org_id or target_org_id, not both")

    if payload.org_id is not None:
        # Staff opening a thread with an organisation.
        if not user.is_platform_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only platform staff can open a conversation with another organisation",
            )
        org = db.get(Organization, payload.org_id)
        if org is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
        if is_member(db, user, payload.org_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You cannot open a staff conversation with an organization you belong to",
            )
        conversation = Conversation(
            kind=ConversationKind.ADMIN_ORG,
            subject=payload.subject.strip(),
            org_id=payload.org_id,
            opened_by_user_id=user.id,
        )
        my_side = ADMIN
    elif payload.target_org_id is not None:
        # The caller wants to reach a specific organisation directly, not staff:
        # an NGO/CSR reaching the other kind of organisation, or a donor reaching an NGO.
        target_org = db.get(Organization, payload.target_org_id)
        if target_org is None or target_org.org_type not in _REAL_ORG_TYPES:
            # An individual donor's own bookkeeping organisation is not a messageable
            # target; treated the same as a target that does not exist.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")

        own_org = _own_real_org(db, user)
        if own_org is not None:
            require_membership(db, user, own_org.id, allowed_roles=MEMBER_ROLES)
            if own_org.id == target_org.id:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot open a conversation with your own organization")
            if own_org.org_type == target_org.org_type:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Direct organisation conversations are for reaching the other kind (an NGO reaching a CSR, or a CSR reaching an NGO)",
                )
            # Canonical slot order (NGO in org_id, CSR in counterparty_org_id) so a
            # repeat conversation between the same two organisations is found regardless
            # of who opens it this time.
            ngo_id, csr_id = (own_org.id, target_org.id) if own_org.org_type is OrgType.NGO else (target_org.id, own_org.id)
            existing = db.scalar(
                select(Conversation).where(
                    Conversation.kind == ConversationKind.ORG_ORG,
                    Conversation.org_id == ngo_id,
                    Conversation.counterparty_org_id == csr_id,
                    Conversation.status == "OPEN",
                )
            )
            my_side = ORG
            if existing is not None:
                _post_message(db, existing, user, my_side, payload.message)
                db.commit()
                return _out(existing, my_side)
            conversation = Conversation(
                kind=ConversationKind.ORG_ORG,
                subject=payload.subject.strip(),
                org_id=ngo_id,
                counterparty_org_id=csr_id,
                opened_by_user_id=user.id,
            )
        else:
            if target_org.org_type is not OrgType.NGO:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "An individual donor can message an NGO directly, not a CSR organisation")
            existing = db.scalar(
                select(Conversation).where(
                    Conversation.kind == ConversationKind.DONOR_NGO,
                    Conversation.org_id == target_org.id,
                    Conversation.donor_user_id == user.id,
                    Conversation.status == "OPEN",
                )
            )
            my_side = DONOR
            if existing is not None:
                _post_message(db, existing, user, my_side, payload.message)
                db.commit()
                return _out(existing, my_side)
            conversation = Conversation(
                kind=ConversationKind.DONOR_NGO,
                subject=payload.subject.strip(),
                org_id=target_org.id,
                donor_user_id=user.id,
                opened_by_user_id=user.id,
            )
    else:
        # The caller is reaching staff: an organisation member, or a donor.
        own_org = _own_real_org(db, user)
        if own_org is not None:
            require_membership(db, user, own_org.id, allowed_roles=MEMBER_ROLES)
            conversation = Conversation(
                kind=ConversationKind.ADMIN_ORG,
                subject=payload.subject.strip(),
                org_id=own_org.id,
                opened_by_user_id=user.id,
            )
            my_side = ORG
        else:
            conversation = Conversation(
                kind=ConversationKind.DONOR_ADMIN,
                subject=payload.subject.strip(),
                donor_user_id=user.id,
                opened_by_user_id=user.id,
            )
            my_side = DONOR

    db.add(conversation)
    db.flush()

    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            sender_user_id=user.id,
            sender_side=my_side,
            content=payload.message.strip(),
        )
    )
    db.flush()

    record_audit(
        db,
        action="conversation.opened",
        resource_type="conversation",
        resource_id=conversation.id,
        actor_user_id=user.id,
        org_id=conversation.org_id,
        details={"kind": conversation.kind.value, "opened_as": my_side},
    )
    db.commit()
    return _out(conversation, my_side)


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    """Conversations this user takes part in, newest first.

    Scoped in SQL rather than loaded and filtered: the table holds every user's
    conversations, and reading all of them to return a handful gets worse as the
    platform grows.
    """
    scope = scope_for(db, user)
    rows = db.scalars(
        select(Conversation).where(scope.filter()).order_by(Conversation.created_at.desc())
    ).all()
    return [_out(c, side) for c in rows if (side := scope.side_of(c)) is not None]


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageOut])
def list_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationMessageOut]:
    _load_participating(db, conversation_id, user)
    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    ).all()
    return [_message_out(m) for m in messages]


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    conversation_id: str,
    payload: ConversationMessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationMessageOut:
    conversation, my_side = _load_participating(db, conversation_id, user)
    if conversation.status == "CLOSED":
        raise HTTPException(status.HTTP_409_CONFLICT, "This conversation is closed")

    message = ConversationMessage(
        conversation_id=conversation_id,
        sender_user_id=user.id,
        sender_side=my_side,
        content=payload.content.strip(),
    )
    db.add(message)
    db.flush()
    record_audit(
        db,
        action="conversation.message_sent",
        resource_type="conversation",
        resource_id=conversation.id,
        actor_user_id=user.id,
        org_id=conversation.org_id,
        details={"message_id": message.id, "sent_as": my_side},
    )
    db.commit()
    return _message_out(message)


@router.post("/{conversation_id}/read")
def mark_read(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Mark the other side's messages as read. Never touches your own."""
    _conversation, my_side = _load_participating(db, conversation_id, user)
    now = datetime.now(UTC)
    marked = 0
    for message in db.scalars(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.sender_side != my_side,
            ConversationMessage.read_at.is_(None),
        )
    ).all():
        message.read_at = now
        marked += 1
    db.commit()
    return {"marked_read": marked}


@router.post("/{conversation_id}/close", response_model=ConversationOut)
def close_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Close a thread.

    On an ADMIN_ORG/DONOR_ADMIN thread, only platform staff close it: the channel
    exists for them to serve, and the other side has no reason to end it unilaterally.
    On an ORG_ORG/DONOR_NGO thread there is no staff side, so either participant can
    close it -- it is a private conversation between the two of them.
    """
    conversation, my_side = _load_participating(db, conversation_id, user)
    has_staff_side = conversation.kind in (ConversationKind.ADMIN_ORG, ConversationKind.DONOR_ADMIN)
    if has_staff_side and my_side != ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only platform staff can close a conversation")
    if conversation.status == "CLOSED":
        return _out(conversation, my_side)

    conversation.status = "CLOSED"
    conversation.closed_at = datetime.now(UTC)
    db.flush()
    record_audit(
        db,
        action="conversation.closed",
        resource_type="conversation",
        resource_id=conversation.id,
        actor_user_id=user.id,
        org_id=conversation.org_id,
    )
    db.commit()
    return _out(conversation, my_side)
