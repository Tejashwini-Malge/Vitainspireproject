"""CSR organization profile: donor-facing identity plus the statutory fields the sheet
expects (CIN, CSR budget, Schedule VII categories). Mirrors app.routers.profiles, but
there is no publish/draft gate -- nothing downstream depends on a CSR profile being
complete, so there is nothing to block.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.models import CsrProfile, Organization, OrgType, Role, User
from app.schemas import CsrProfileIn, CsrProfileOut

router = APIRouter(prefix="/orgs/{org_id}/csr-profile", tags=["csr-profile"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


def _profile_out(p: CsrProfile) -> CsrProfileOut:
    return CsrProfileOut(
        org_id=p.org_id,
        mission=p.mission,
        about=p.about,
        website=p.website,
        cin=p.cin,
        csr_budget_minor=p.csr_budget_minor,
        schedule_vii_categories=list(p.schedule_vii_categories),
        updated_at=p.updated_at,
    )


@router.get("", response_model=CsrProfileOut | None)
def get_csr_profile(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CsrProfileOut | None:
    require_membership(db, user, org_id)
    profile = db.scalar(select(CsrProfile).where(CsrProfile.org_id == org_id))
    return _profile_out(profile) if profile else None


@router.put("", response_model=CsrProfileOut)
def save_csr_profile(
    org_id: str,
    payload: CsrProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CsrProfileOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    org = db.get(Organization, org_id)
    if org is None:  # Membership was checked first, so this means the data is inconsistent. Fail loudly.
        raise RuntimeError(f"Membership references missing organization {org_id}")
    if org.org_type is not OrgType.CSR:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This profile is available for CSR organizations")

    profile = db.scalar(select(CsrProfile).where(CsrProfile.org_id == org_id))
    created = profile is None
    if created:
        profile = CsrProfile(org_id=org_id)
        db.add(profile)

    # Only fields the client actually sent are written, same convention as the NGO profile:
    # a client that omits a field leaves it untouched, an explicit null clears it.
    submitted = payload.model_fields_set
    candidates = {
        "mission": payload.mission,
        "about": payload.about,
        "website": payload.website,
        "cin": payload.cin,
        "csr_budget_minor": payload.csr_budget_minor,
        "schedule_vii_categories": payload.schedule_vii_categories,
    }

    changed = []
    for field, value in candidates.items():
        if field not in submitted:
            continue
        if getattr(profile, field) != value:
            setattr(profile, field, value)
            changed.append(field)

    profile.updated_at = datetime.now(UTC)
    db.flush()
    record_audit(
        db,
        action="csr_profile.created" if created else "csr_profile.updated",
        resource_type="csr_profile",
        resource_id=profile.id,
        actor_user_id=user.id,
        org_id=org_id,
        details={"changed_fields": changed},
    )
    db.commit()
    return _profile_out(profile)
