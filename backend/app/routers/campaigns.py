"""NGO campaigns - fundraising with AI-assisted admin review."""

import uuid
from datetime import UTC, datetime, date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from annotated_types import MinLen

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.models import (
    Campaign,
    CampaignMilestone,
    DonationType,
    CampaignDonation,
    CampaignReview,
    NgoProfile,
    Organization,
    OrgType,
    Role,
    User,
    Membership,
)
from app.schemas import (
    CampaignIn,
    CampaignOut,
    CampaignMilestoneIn,
    CampaignMilestoneOut,
    DonationTypeIn,
    DonationTypeOut,
    CampaignReviewOut,
    CampaignApprovalIn,
    CampaignSuggestionOut,
    SuggestedField,
    WebsiteExtractIn,
)
from app.services.website_extractor import fetch_website

router = APIRouter(tags=["campaigns"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


# NGO Campaign Routes
@router.post("/ngo/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignOut:
    """Create a new campaign (starts in DRAFT status)."""
    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User must be a member of an NGO organization")

    require_membership(db, user, ngo_org.id, allowed_roles=MANAGE)

    campaign = Campaign(
        ngo_id=ngo_org.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        mission=payload.mission.strip(),
        beneficiary_count=payload.beneficiary_count,
        beneficiary_description=payload.beneficiary_description.strip(),
        impact_statement=payload.impact_statement.strip(),
        budget_total=payload.budget_total,
        currency=payload.currency.upper(),
        budget_breakdown=payload.budget_breakdown,
        duration_months=payload.duration_months,
        hero_image_url=payload.hero_image_url,
        status="DRAFT",
    )
    db.add(campaign)
    db.flush()

    record_audit(
        db,
        action="campaign.created",
        resource_type="campaign",
        resource_id=campaign.id,
        actor_user_id=user.id,
        org_id=ngo_org.id,
    )
    db.commit()
    return _campaign_out(db, campaign)


@router.get("/ngo/campaigns", response_model=list[CampaignOut])
def list_ngo_campaigns(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CampaignOut]:
    """List all campaigns for user's NGO."""
    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        return []

    campaigns = db.scalars(
        select(Campaign).where(Campaign.ngo_id == ngo_org.id).order_by(Campaign.created_at.desc())
    ).all()
    return [_campaign_out(db, c) for c in campaigns]


@router.get("/ngo/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignOut:
    """Get campaign details (NGO can only see their own)."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot access this campaign")

    return _campaign_out(db, campaign)


@router.put("/ngo/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: str,
    payload: CampaignIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignOut:
    """Update campaign (only in DRAFT or CHANGES_REQUESTED status)."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    if campaign.status not in ["DRAFT", "CHANGES_REQUESTED"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Cannot edit campaign in {campaign.status} status",
        )

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit this campaign")

    require_membership(db, user, ngo_org.id, allowed_roles=MANAGE)

    campaign.title = payload.title.strip()
    campaign.description = payload.description.strip()
    campaign.mission = payload.mission.strip()
    campaign.beneficiary_count = payload.beneficiary_count
    campaign.beneficiary_description = payload.beneficiary_description.strip()
    campaign.impact_statement = payload.impact_statement.strip()
    campaign.budget_total = payload.budget_total
    campaign.currency = payload.currency.upper()
    campaign.budget_breakdown = payload.budget_breakdown
    campaign.duration_months = payload.duration_months
    campaign.hero_image_url = payload.hero_image_url
    campaign.last_update_at = datetime.now(UTC)

    db.commit()
    return _campaign_out(db, campaign)


@router.post("/ngo/campaigns/{campaign_id}/submit-for-review")
def submit_campaign_for_review(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Submit campaign for admin review."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    if campaign.status != "DRAFT":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only DRAFT campaigns can be submitted for review",
        )

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot submit this campaign")

    campaign.status = "PENDING_REVIEW"

    # Create review record if not exists
    existing_review = db.scalar(select(CampaignReview).where(CampaignReview.campaign_id == campaign.id))
    if not existing_review:
        review = CampaignReview(campaign_id=campaign.id)
        db.add(review)

    db.commit()

    record_audit(
        db,
        action="campaign.submitted_for_review",
        resource_type="campaign",
        resource_id=campaign.id,
        actor_user_id=user.id,
        org_id=ngo_org.id,
    )

    return {"campaign_id": campaign.id, "status": "PENDING_REVIEW"}


@router.post("/ngo/campaigns/{campaign_id}/milestones", response_model=CampaignMilestoneOut, status_code=status.HTTP_201_CREATED)
def add_milestone(
    campaign_id: str,
    payload: CampaignMilestoneIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignMilestoneOut:
    """Add a milestone to a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot add milestones to this campaign")

    require_membership(db, user, ngo_org.id, allowed_roles=MANAGE)

    # Get next sequence number
    max_seq = db.scalar(
        select(func.max(CampaignMilestone.sequence_num)).where(CampaignMilestone.campaign_id == campaign.id)
    ) or 0

    milestone = CampaignMilestone(
        campaign_id=campaign.id,
        sequence_num=max_seq + 1,
        title=payload.title.strip(),
        description=payload.description.strip(),
        target_date=payload.target_date,
        target_amount=payload.target_amount,
    )
    db.add(milestone)
    db.flush()

    record_audit(
        db,
        action="campaign_milestone.created",
        resource_type="campaign_milestone",
        resource_id=milestone.id,
        actor_user_id=user.id,
        org_id=ngo_org.id,
    )
    db.commit()
    return _milestone_out(milestone)


@router.get("/ngo/campaigns/{campaign_id}/milestones", response_model=list[CampaignMilestoneOut])
def list_milestones(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CampaignMilestoneOut]:
    """List milestones for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot view these milestones")

    milestones = db.scalars(
        select(CampaignMilestone)
        .where(CampaignMilestone.campaign_id == campaign.id)
        .order_by(CampaignMilestone.sequence_num)
    ).all()
    return [_milestone_out(m) for m in milestones]


@router.post("/ngo/campaigns/{campaign_id}/donation-types", response_model=DonationTypeOut, status_code=status.HTTP_201_CREATED)
def add_donation_type(
    campaign_id: str,
    payload: DonationTypeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DonationTypeOut:
    """Add a donation type option to a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot add donation types to this campaign")

    require_membership(db, user, ngo_org.id, allowed_roles=MANAGE)

    donation_type = DonationType(
        campaign_id=campaign.id,
        type=payload.type.upper(),
        label=payload.label.strip(),
        description=payload.description.strip(),
        quantity_unit=payload.quantity_unit,
        value_in_rupees=payload.value_in_rupees,
    )
    db.add(donation_type)
    db.flush()

    record_audit(
        db,
        action="donation_type.created",
        resource_type="donation_type",
        resource_id=donation_type.id,
        actor_user_id=user.id,
        org_id=ngo_org.id,
    )
    db.commit()
    return _donation_type_out(donation_type)


@router.get("/ngo/campaigns/{campaign_id}/donation-types", response_model=list[DonationTypeOut])
def list_donation_types(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DonationTypeOut]:
    """List donation type options for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None or campaign.ngo_id != ngo_org.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot view these donation types")

    types = db.scalars(
        select(DonationType).where(DonationType.campaign_id == campaign.id)
    ).all()
    return [_donation_type_out(dt) for dt in types]


# Admin Routes
@router.get("/admin/campaigns/pending-review", response_model=list[CampaignOut])
def get_pending_campaigns(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CampaignOut]:
    """Get campaigns awaiting admin review."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    campaigns = db.scalars(
        select(Campaign)
        .where(Campaign.status == "PENDING_REVIEW")
        .order_by(Campaign.created_at.asc())
    ).all()
    return [_campaign_out(db, c) for c in campaigns]


@router.get("/admin/campaigns/{campaign_id}/review", response_model=CampaignReviewOut)
def get_campaign_review(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignReviewOut:
    """Get campaign review details for admin."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    review = db.scalar(select(CampaignReview).where(CampaignReview.campaign_id == campaign_id))
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")

    return _review_out(review)


@router.post("/admin/campaigns/{campaign_id}/approve")
def approve_campaign(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Approve a campaign and make it LIVE."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    campaign.status = "LIVE"
    campaign.verification_status = "APPROVED"
    campaign.verified_by_user_id = user.id
    campaign.verified_at = datetime.now(UTC)
    campaign.published_at = datetime.now(UTC)

    review = db.scalar(select(CampaignReview).where(CampaignReview.campaign_id == campaign.id))
    if review:
        review.admin_user_id = user.id
        review.admin_decision = "APPROVED"
        review.admin_review_at = datetime.now(UTC)

    db.commit()

    record_audit(
        db,
        action="campaign.approved",
        resource_type="campaign",
        resource_id=campaign.id,
        actor_user_id=user.id,
        org_id=campaign.ngo_id,
    )

    return {"campaign_id": campaign.id, "status": "LIVE"}


@router.post("/admin/campaigns/{campaign_id}/reject")
def reject_campaign(
    campaign_id: str,
    payload: CampaignApprovalIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Reject a campaign with reason."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    campaign.status = "REJECTED"
    campaign.verification_status = "REJECTED"
    campaign.verified_by_user_id = user.id
    campaign.verified_at = datetime.now(UTC)
    campaign.rejection_reason = payload.reason or ""

    review = db.scalar(select(CampaignReview).where(CampaignReview.campaign_id == campaign.id))
    if review:
        review.admin_user_id = user.id
        review.admin_decision = "REJECTED"
        review.admin_review_at = datetime.now(UTC)
        review.admin_notes = payload.reason

    db.commit()

    record_audit(
        db,
        action="campaign.rejected",
        resource_type="campaign",
        resource_id=campaign.id,
        actor_user_id=user.id,
        org_id=campaign.ngo_id,
    )

    return {"campaign_id": campaign.id, "status": "REJECTED"}


@router.post("/admin/campaigns/{campaign_id}/request-changes")
def request_changes(
    campaign_id: str,
    payload: CampaignApprovalIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Request NGO to make changes to campaign."""
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    campaign.status = "CHANGES_REQUESTED"
    campaign.admin_notes = payload.reason or ""

    review = db.scalar(select(CampaignReview).where(CampaignReview.campaign_id == campaign.id))
    if review:
        review.admin_user_id = user.id
        review.admin_decision = "CHANGES_REQUESTED"
        review.admin_review_at = datetime.now(UTC)
        review.admin_changes_requested = payload.reason

    db.commit()

    record_audit(
        db,
        action="campaign.changes_requested",
        resource_type="campaign",
        resource_id=campaign.id,
        actor_user_id=user.id,
        org_id=campaign.ngo_id,
    )

    return {"campaign_id": campaign.id, "status": "CHANGES_REQUESTED", "requested": payload.reason}


# Helpers
def _campaign_out(db: Session, c: Campaign) -> CampaignOut:
    org = db.get(Organization, c.ngo_id)
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == c.ngo_id))
    return CampaignOut(
        id=c.id,
        ngo_id=c.ngo_id,
        ngo_name=org.name if org else "",
        ngo_sectors=list(profile.sectors) if profile else [],
        ngo_geographies=list(profile.geographies) if profile else [],
        title=c.title,
        description=c.description,
        mission=c.mission,
        beneficiary_count=c.beneficiary_count,
        beneficiary_description=c.beneficiary_description,
        impact_statement=c.impact_statement,
        budget_total=c.budget_total,
        currency=c.currency,
        budget_breakdown=c.budget_breakdown,
        duration_months=c.duration_months,
        status=c.status,
        hero_image_url=c.hero_image_url,
        images=c.images or [],
        view_count=c.view_count,
        donation_count=c.donation_count,
        amount_raised=c.amount_raised,
        verification_status=c.verification_status,
        verified_at=c.verified_at,
        rejection_reason=c.rejection_reason,
        admin_notes=c.admin_notes,
        created_at=c.created_at,
        published_at=c.published_at,
    )


def _milestone_out(m: CampaignMilestone) -> CampaignMilestoneOut:
    return CampaignMilestoneOut(
        id=m.id,
        sequence_num=m.sequence_num,
        title=m.title,
        description=m.description,
        target_date=m.target_date,
        target_amount=m.target_amount,
        status=m.status,
        completed_at=m.completed_at,
        evidence_url=m.evidence_url,
    )


def _donation_type_out(dt: DonationType) -> DonationTypeOut:
    return DonationTypeOut(
        id=dt.id,
        type=dt.type,
        label=dt.label,
        description=dt.description,
        quantity_unit=dt.quantity_unit,
        value_in_rupees=dt.value_in_rupees,
        is_available=dt.is_available,
    )


def _review_out(r: CampaignReview) -> CampaignReviewOut:
    return CampaignReviewOut(
        id=r.id,
        campaign_id=r.campaign_id,
        ai_review_at=r.ai_review_at,
        ai_recommendation=r.ai_recommendation,
        trustworthiness_score=r.trustworthiness_score,
        ai_flags=r.ai_flags or [],
        ai_analysis=r.ai_analysis,
        admin_decision=r.admin_decision,
        admin_notes=r.admin_notes,
        admin_changes_requested=r.admin_changes_requested,
    )


def _suggest(value: str | None, field_name: str, source_url: str) -> SuggestedField | None:
    """Wrap an extracted value, reporting whether it clears CampaignIn's length rule."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    minimum = 0
    for constraint in CampaignIn.model_fields[field_name].metadata:
        if isinstance(constraint, MinLen):
            minimum = constraint.min_length
    return SuggestedField(
        value=text,
        source_url=source_url,
        meets_minimum=len(text) >= minimum,
        minimum_length=minimum,
    )


@router.post("/ngo/campaigns/suggest-from-website", response_model=CampaignSuggestionOut)
async def suggest_campaign_from_website(
    payload: WebsiteExtractIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignSuggestionOut:
    """Propose campaign copy from the organisation's own website.

    This saves nothing. It returns a draft with the source it came from, for a human to
    accept or rewrite. Fields the extractor cannot find are named in needs_your_input
    rather than invented, so no sentence is attributed to the NGO unless their site
    actually said it.
    """
    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User must be a member of an NGO organization")
    require_membership(db, user, ngo_org.id, allowed_roles=MANAGE)

    url = (payload.website_url if payload else None) or ""
    if not url:
        profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == ngo_org.id))
        url = (profile.website if profile else None) or ""
    if not url:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Add your website to your profile first, or pass one in, so there is something to read.",
        )

    data = await fetch_website(url)
    if data is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not fetch or read {url}")

    title = _suggest(data.title, "title", url)
    description = _suggest(data.description or data.about, "description", url)
    mission = _suggest(data.mission, "mission", url)

    # Named explicitly: a website rarely states beneficiary numbers or a measurable
    # impact claim, and guessing them would put words in the NGO's mouth.
    needs: list[str] = ["beneficiary_description", "impact_statement", "budget_total", "duration_months"]
    for name, field in (("title", title), ("description", description), ("mission", mission)):
        if field is None:
            needs.append(name)

    return CampaignSuggestionOut(
        source_url=url,
        fetched_at=datetime.now(UTC),
        title=title,
        description=description,
        mission=mission,
        needs_your_input=sorted(needs),
        disclaimer=(
            "This draft was read from your website on the date shown. Nothing has been "
            "saved. Check every line before you submit it: you are publishing it, not us."
        ),
    )
