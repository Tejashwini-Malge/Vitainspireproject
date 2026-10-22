from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_membership
from app.domain.onboarding import compute_csr_steps, compute_ngo_steps, completion_pct, next_step
from app.models import Document, NgoProfile, Opportunity, Organization, OrgType, Project, Proposal, ReviewStatus, User
from app.schemas import OnboardingStatusOut, OnboardingStepOut

router = APIRouter(prefix="/orgs/{org_id}/onboarding", tags=["onboarding"])


def _load_org(db: Session, org_id: str) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:  # Membership was checked first, so this means the data is inconsistent. Fail loudly.
        raise RuntimeError(f"Membership references missing organization {org_id}")
    return org


@router.get("/status", response_model=OnboardingStatusOut)
def get_onboarding_status(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OnboardingStatusOut:
    require_membership(db, user, org_id)
    org = _load_org(db, org_id)

    if org.org_type is OrgType.NGO:
        profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
        documents = db.scalars(select(Document).where(Document.org_id == org_id)).all()
        projects = db.scalars(select(Project).where(Project.org_id == org_id)).all()
        steps = compute_ngo_steps(
            org,
            profile,
            has_document=len(documents) > 0,
            has_approved_document=any(d.review_status is ReviewStatus.APPROVED for d in documents),
            projects=list(projects),
        )
    elif org.org_type is OrgType.CSR:
        opportunities = db.scalars(select(Opportunity).where(Opportunity.org_id == org_id)).all()
        proposal_rows = db.scalars(
            select(Proposal).join(Opportunity, Proposal.opportunity_id == Opportunity.id).where(Opportunity.org_id == org_id)
        ).all()
        steps = compute_csr_steps(org, list(opportunities), list(proposal_rows))
    else:
        # Individual donor accounts have no org-level workflow to track yet.
        steps = []

    return OnboardingStatusOut(
        org_type=org.org_type.value,
        steps=[OnboardingStepOut(key=s.key, label=s.label, done=s.done, cta_href=s.cta_href) for s in steps],
        next_step=(lambda s: OnboardingStepOut(key=s.key, label=s.label, done=s.done, cta_href=s.cta_href) if s else None)(
            next_step(steps)
        ),
        completion_pct=completion_pct(steps),
    )
