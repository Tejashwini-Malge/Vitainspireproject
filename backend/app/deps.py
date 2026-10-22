from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Membership, Role, SessionRecord, User
from app.security import hash_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve a Bearer token to a live (unexpired, unrevoked) session's user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    record = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == hash_token(token)))
    now = datetime.now(UTC)
    if record is None or record.revoked_at is not None or _as_utc(record.expires_at) <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is invalid or expired")
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session user no longer exists")
    return user


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user, but anonymous callers (no header) get None instead of a 401.

    A header that is present but invalid still raises: a donor who believes they are signed in
    must be told so, not silently treated as a guest.
    """
    if not authorization:
        return None
    return get_current_user(authorization=authorization, db=db)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def require_membership(
    db: Session,
    user: User,
    org_id: str,
    allowed_roles: frozenset[Role] | None = None,
) -> Membership:
    """Tenant boundary check. Non-members get 404 (org existence is not revealed).

    Members without a permitted role get 403. Every org-scoped route must call this
    before touching org data.
    """
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user.id)
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if allowed_roles is not None and membership.role not in allowed_roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role does not permit this action")
    return membership


def is_member(db: Session, user: User, org_id: str) -> bool:
    return db.scalar(select(Membership.id).where(Membership.org_id == org_id, Membership.user_id == user.id)) is not None


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator access required")
    return user
