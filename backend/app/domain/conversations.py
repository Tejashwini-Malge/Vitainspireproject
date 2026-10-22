"""Who may read and write a direct conversation.

One module so the rule is stated once. The rule has to serve two callers with very
different needs: the router asks "may this user touch this one row?", while the inbox
needs "give me every row this user may touch" without loading the table.

Both come from a single AccessScope, so the SQL predicate and the per-row decision
cannot drift apart. AccessScope.side_of performs no queries: everything it needs is
captured when the scope is built.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.orm import Session

from app.models import Conversation, ConversationKind, Membership, User

ADMIN = "ADMIN"
ORG = "ORG"
DONOR = "DONOR"


@dataclass(frozen=True)
class AccessScope:
    """Everything needed to decide access for one user, captured once."""

    user_id: str
    is_staff: bool
    org_ids: frozenset[str]

    def side_of(self, conversation: Conversation) -> str | None:
        """Which side this user speaks as, or None if they are not a participant.

        Platform staff are the ADMIN side on ADMIN_ORG/DONOR_ADMIN threads (the
        channels that exist for staff to be reached), except on a conversation with an
        organisation they belong to: the same conflict-of-interest rule that governs
        verification and document review applies to talking to themselves. ORG_ORG and
        DONOR_NGO threads are private between their two participants; staff are never a
        side on those, by design -- the whole point is that the two parties can talk
        directly without going through the platform.
        """
        if conversation.kind is ConversationKind.ADMIN_ORG:
            in_org = conversation.org_id is not None and conversation.org_id in self.org_ids
            if in_org:
                return ORG
            if self.is_staff:
                return ADMIN
            return None

        if conversation.kind is ConversationKind.DONOR_ADMIN:
            if conversation.donor_user_id == self.user_id:
                return DONOR
            if self.is_staff:
                return ADMIN
            return None

        if conversation.kind is ConversationKind.ORG_ORG:
            if conversation.org_id in self.org_ids or conversation.counterparty_org_id in self.org_ids:
                return ORG
            return None

        if conversation.kind is ConversationKind.DONOR_NGO:
            if conversation.donor_user_id == self.user_id:
                return DONOR
            if conversation.org_id in self.org_ids:
                return ORG
            return None

        return None

    def filter(self) -> ColumnElement[bool]:
        """SQL predicate selecting exactly the rows side_of would accept.

        Kept beside side_of deliberately: a change to one that is not mirrored in the
        other would either hide a user's own conversations or expose someone else's.
        tests/test_conversations.py asserts the two agree.
        """
        mine = [
            # A conversation with an organisation I belong to, on either side.
            Conversation.org_id.in_(self.org_ids) if self.org_ids else None,
            Conversation.counterparty_org_id.in_(self.org_ids) if self.org_ids else None,
            # A donor conversation that is mine.
            Conversation.donor_user_id == self.user_id,
        ]
        clauses = [c for c in mine if c is not None]

        if self.is_staff:
            # Staff see every other ADMIN_ORG/DONOR_ADMIN conversation: organisation
            # threads for organisations they do not belong to, and all donor-staff
            # threads. ORG_ORG and DONOR_NGO stay out of this: staff are not a party to
            # those regardless of which organisations are involved.
            clauses.append(
                or_(
                    Conversation.kind == ConversationKind.DONOR_ADMIN,
                    and_(
                        Conversation.kind == ConversationKind.ADMIN_ORG,
                        Conversation.org_id.notin_(self.org_ids) if self.org_ids else True,
                    ),
                )
            )

        return or_(*clauses)


def scope_for(db: Session, user: User) -> AccessScope:
    """Build the access scope for a user. One query, regardless of how many
    conversations are later checked against it."""
    org_ids = frozenset(
        db.scalars(select(Membership.org_id).where(Membership.user_id == user.id)).all()
    )
    return AccessScope(user_id=user.id, is_staff=bool(user.is_platform_admin), org_ids=org_ids)


def side_for(db: Session, conversation: Conversation, user: User) -> str | None:
    """Which side this user speaks as on one conversation, or None."""
    return scope_for(db, user).side_of(conversation)


def can_access(db: Session, conversation: Conversation, user: User) -> bool:
    return side_for(db, conversation, user) is not None
