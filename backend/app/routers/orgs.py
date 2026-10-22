from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.models import Membership, Organization, Role, User
from app.schemas import MemberAddIn, MemberOut, OrgCreateIn, OrgOut

router = APIRouter(prefix="/orgs", tags=["organizations"])

MANAGE_MEMBERS = frozenset({Role.OWNER, Role.ADMIN})


def _org_out(org: Organization) -> OrgOut:
    return OrgOut(
        id=org.id,
        name=org.name,
        org_type=org.org_type,
        verification_status=org.verification_status,
        verification_reason=org.verification_reason,
        verified_at=org.verified_at,
    )


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: OrgCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgOut:
    org = Organization(name=payload.name.strip(), org_type=payload.org_type)
    db.add(org)
    db.flush()
    db.add(Membership(org_id=org.id, user_id=user.id, role=Role.OWNER))
    record_audit(
        db,
        action="org.created",
        resource_type="organization",
        resource_id=org.id,
        actor_user_id=user.id,
        org_id=org.id,
        details={"org_type": payload.org_type.value},
    )
    db.commit()
    return _org_out(org)


@router.get("", response_model=list[OrgOut])
def list_my_orgs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[OrgOut]:
    # Only organizations the caller belongs to. Never a global list.
    orgs = db.scalars(
        select(Organization)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    ).all()
    return [_org_out(o) for o in orgs]


@router.get("/public/ngos", response_model=list[OrgOut])
def list_all_ngos(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[OrgOut]:
    """List all approved NGOs. Used by CSR users for shortlisting."""
    from app.models import OrgType, VerificationStatus

    ngos = db.scalars(
        select(Organization)
        .where(Organization.org_type == OrgType.NGO, Organization.verification_status == VerificationStatus.APPROVED)
        .order_by(Organization.name)
    ).all()
    return [_org_out(o) for o in ngos]


@router.get("/{org_id}", response_model=OrgOut)
def get_org(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OrgOut:
    require_membership(db, user, org_id)
    org = db.get(Organization, org_id)
    if org is None:  # Membership row exists, so this is a data-integrity fault; fail loudly.
        raise RuntimeError(f"Membership references missing organization {org_id}")
    return _org_out(org)


@router.get("/{org_id}/members", response_model=list[MemberOut])
def list_members(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[MemberOut]:
    require_membership(db, user, org_id)
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id)
        .order_by(User.email)
    ).all()
    return [MemberOut(user_id=u.id, email=u.email, full_name=u.full_name, role=m.role) for m, u in rows]


@router.post("/{org_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    org_id: str,
    payload: MemberAddIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberOut:
    actor = require_membership(db, user, org_id, allowed_roles=MANAGE_MEMBERS)
    invitee = db.scalar(select(User).where(User.email == payload.email.lower()))
    if invitee is None:
        # Invitations to unregistered people are a later slice; say so explicitly.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No registered user with that email")
    if payload.role == Role.OWNER and actor.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can grant the owner role")
    existing = db.scalar(select(Membership).where(Membership.org_id == org_id, Membership.user_id == invitee.id))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member of this organization")
    membership = Membership(org_id=org_id, user_id=invitee.id, role=payload.role)
    db.add(membership)
    db.flush()
    record_audit(
        db,
        action="org.member_added",
        resource_type="membership",
        resource_id=membership.id,
        actor_user_id=user.id,
        org_id=org_id,
        details={"invitee_user_id": invitee.id, "role": payload.role.value},
    )
    db.commit()
    return MemberOut(user_id=invitee.id, email=invitee.email, full_name=invitee.full_name, role=payload.role)
