from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.domain.profile import publish_blockers
from app.models import NgoProfile, Organization, OrgType, ProfileStatus, Role, User
from app.schemas import ProfileIn, ProfileOut, WebsiteExtractIn, WebsiteExtractOut
from app.services.geocoding import geocode
from app.services.website_extractor import fetch_website

router = APIRouter(prefix="/orgs/{org_id}/profile", tags=["profile"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


def _profile_out(p: NgoProfile) -> ProfileOut:
    return ProfileOut(
        org_id=p.org_id,
        status=p.status,
        mission=p.mission,
        about=p.about,
        vision=p.vision,
        description=p.description,
        organization_title=p.organization_title,
        sectors=list(p.sectors),
        geographies=list(p.geographies),
        founded_year=p.founded_year,
        website=p.website,
        registration_number=p.registration_number,
        section_80g_number=p.section_80g_number,
        published_at=p.published_at,
        updated_at=p.updated_at,
    )


def _load_org(db: Session, org_id: str) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:  # Membership was checked first, so this means the data is inconsistent. Fail loudly.
        raise RuntimeError(f"Membership references missing organization {org_id}")
    return org


@router.get("", response_model=ProfileOut | None)
def get_profile(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileOut | None:
    require_membership(db, user, org_id)
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    return _profile_out(profile) if profile else None


@router.put("", response_model=ProfileOut)
async def save_profile(
    org_id: str,
    payload: ProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    org = _load_org(db, org_id)
    if org.org_type is not OrgType.NGO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Profiles are available for NGO organizations")

    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    created = profile is None
    if created:
        profile = NgoProfile(org_id=org_id)
        db.add(profile)

    # Only fields the client actually sent are written. A client that omits a field leaves
    # it untouched; a client that sends an explicit null clears it. Without this, any form
    # that does not yet render every field silently wipes the ones it does not know about --
    # which is how website-extracted vision/description/organization_title were being lost
    # whenever an NGO saved the profile form.
    submitted = payload.model_fields_set
    candidates = {
        "mission": payload.mission,
        "about": payload.about,
        "vision": payload.vision,
        "description": payload.description,
        "organization_title": payload.organization_title,
        "sectors": payload.sectors,
        "geographies": payload.geographies,
        "founded_year": payload.founded_year,
        "website": payload.website,
        "registration_number": payload.registration_number,
        "section_80g_number": payload.section_80g_number,
    }

    changed = []
    for field, value in candidates.items():
        if field not in submitted:
            continue
        if getattr(profile, field) != value:
            setattr(profile, field, value)
            changed.append(field)

    if "geographies" in changed:
        # Reuse the geocode already on file for a query that didn't change; only look up the
        # ones that are new, so saving the profile again doesn't re-hit Nominatim for everything.
        existing_by_query = {p["query"]: p for p in (profile.geography_points or [])}
        points = []
        for query in profile.geographies:
            if query in existing_by_query:
                points.append(existing_by_query[query])
                continue
            point = await geocode(query)
            if point is not None:
                points.append({"query": point.query, "lat": point.lat, "lon": point.lon, "display_name": point.display_name})
        profile.geography_points = points

    profile.updated_at = datetime.now(UTC)
    db.flush()
    record_audit(
        db,
        action="profile.created" if created else "profile.updated",
        resource_type="ngo_profile",
        resource_id=profile.id,
        actor_user_id=user.id,
        org_id=org_id,
        details={"changed_fields": changed},
    )
    db.commit()
    return _profile_out(profile)


@router.post("/publish", response_model=ProfileOut)
def publish_profile(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    org = _load_org(db, org_id)
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    blockers = publish_blockers(org.org_type, org.verification_status, profile)
    if blockers:
        # Structured so the UI can list every reason at once instead of one error at a time.
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "The profile cannot be published yet", "blockers": blockers})
    assert profile is not None  # guaranteed by publish_blockers
    if profile.status is ProfileStatus.PUBLISHED:
        return _profile_out(profile)
    profile.status = ProfileStatus.PUBLISHED
    profile.published_at = datetime.now(UTC)
    record_audit(
        db,
        action="profile.published",
        resource_type="ngo_profile",
        resource_id=profile.id,
        actor_user_id=user.id,
        org_id=org_id,
    )
    db.commit()
    return _profile_out(profile)


@router.post("/unpublish", response_model=ProfileOut)
def unpublish_profile(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileOut:
    require_membership(db, user, org_id, allowed_roles=MANAGE)
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This organization has no profile yet")
    if profile.status is ProfileStatus.DRAFT:
        return _profile_out(profile)
    profile.status = ProfileStatus.DRAFT
    record_audit(
        db,
        action="profile.unpublished",
        resource_type="ngo_profile",
        resource_id=profile.id,
        actor_user_id=user.id,
        org_id=org_id,
    )
    db.commit()
    return _profile_out(profile)


@router.post("/extract-website", response_model=WebsiteExtractOut)
async def extract_website(payload: WebsiteExtractIn) -> WebsiteExtractOut:
    """Extract structured data from a website URL."""
    data = await fetch_website(payload.website_url)
    if data is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not fetch or parse the website")
    return WebsiteExtractOut(
        about=data.about,
        mission=data.mission,
        mission_statements=data.mission_statements or [],
        vision=data.vision,
        founded_year=data.founded_year,
        title=data.title,
        description=data.description,
    )
