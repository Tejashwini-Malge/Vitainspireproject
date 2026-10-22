from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.visibility import PUBLIC_NGO_FILTER
from app.models import (
    Document,
    DocumentReviewDecision,
    NgoProfile,
    Organization,
    OrgType,
    ProfileStatus,
    Project,
    ProjectStatus,
    ReviewStatus,
    VerificationStatus,
)
from app.schemas import ProfileOut, PublicNgoOut, PublicProjectOut, ReviewedDocumentOut

router = APIRouter(prefix="/public", tags=["public"])

DISCLAIMER = (
    "Profile content is provided by the organization. Verification means Imparency reviewed the organization's "
    "registration. Documents are private; only their type and review date are shown."
)


@router.get("/ngos", response_model=list[PublicNgoOut])
def list_public_ngos(db: Session = Depends(get_db)) -> list[PublicNgoOut]:
    rows = db.execute(
        select(Organization, NgoProfile)
        .join(NgoProfile, NgoProfile.org_id == Organization.id)
        .where(*PUBLIC_NGO_FILTER)
        .order_by(Organization.name)
    ).all()
    return [_public_ngo_out(org, profile, _reviewed_documents(db, org.id)) for org, profile in rows]


@router.get("/feed", response_model=list[PublicProjectOut])
def public_feed(db: Session = Depends(get_db)) -> list[PublicProjectOut]:
    rows = db.execute(
        select(Project, Organization.name, NgoProfile.sectors)
        .join(Organization, Organization.id == Project.org_id)
        .join(NgoProfile, NgoProfile.org_id == Organization.id)
        .where(Project.status == ProjectStatus.PUBLISHED, *PUBLIC_NGO_FILTER)
        .order_by(Project.published_at.desc())
    ).all()
    return [
        PublicProjectOut(
            id=p.id,
            org_id=p.org_id,
            org_name=name,
            org_sectors=list(sectors),
            title=p.title,
            summary=p.summary,
            description=p.description,
            published_at=p.published_at,
        )
        for p, name, sectors in rows
    ]


@router.get("/ngos/{org_id}", response_model=PublicNgoOut)
def public_ngo_profile(org_id: str, db: Session = Depends(get_db)) -> PublicNgoOut:
    # Same 404 for "does not exist", "not an NGO", "not verified" and "not published": nothing is leaked.
    org = db.get(Organization, org_id)
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    if (
        org is None
        or org.org_type is not OrgType.NGO
        or org.verification_status is not VerificationStatus.APPROVED
        or profile is None
        or profile.status is not ProfileStatus.PUBLISHED
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return _public_ngo_out(org, profile, _reviewed_documents(db, org_id))


def _reviewed_documents(db: Session, org_id: str) -> list[ReviewedDocumentOut]:
    approved = db.execute(
        select(Document.doc_type, DocumentReviewDecision.decided_at)
        .join(DocumentReviewDecision, DocumentReviewDecision.document_id == Document.id)
        .where(
            Document.org_id == org_id,
            Document.review_status == ReviewStatus.APPROVED,
            DocumentReviewDecision.decision == ReviewStatus.APPROVED,
        )
        .order_by(DocumentReviewDecision.decided_at)
    ).all()
    reviewed: dict[str, ReviewedDocumentOut] = {}
    for doc_type, decided_at in approved:
        reviewed.setdefault(doc_type.value, ReviewedDocumentOut(doc_type=doc_type, reviewed_at=decided_at))
    return list(reviewed.values())


def _public_ngo_out(org: Organization, profile: NgoProfile, reviewed_documents: list[ReviewedDocumentOut]) -> PublicNgoOut:
    return PublicNgoOut(
        id=org.id,
        name=org.name,
        verified_at=org.verified_at,
        profile=ProfileOut(
            org_id=profile.org_id,
            status=profile.status,
            mission=profile.mission,
            about=profile.about,
            vision=profile.vision,
            description=profile.description,
            organization_title=profile.organization_title,
            sectors=list(profile.sectors),
            geographies=list(profile.geographies),
            founded_year=profile.founded_year,
            website=profile.website,
            registration_number=profile.registration_number,
            section_80g_number=profile.section_80g_number,
            published_at=profile.published_at,
            updated_at=profile.updated_at,
        ),
        reviewed_documents=reviewed_documents,
        disclaimer=DISCLAIMER,
    )
