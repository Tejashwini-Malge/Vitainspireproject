"""Public/Donor-facing campaign endpoints - Phase 2."""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user
from app.domain.visibility import PUBLIC_NGO_FILTER
from app.models import (
    Campaign,
    CampaignMilestone,
    DonationType,
    CampaignDonation,
    NgoProfile,
    Organization,
    User,
)
from app.schemas import (
    CampaignOut,
    CampaignMilestoneOut,
    DonationTypeOut,
    CampaignDonationIn,
    CampaignDonationOut,
)

router = APIRouter(tags=["campaigns-public"])


# Public Campaign Browsing
@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    status_filter: str = Query(default="LIVE", description="LIVE, COMPLETED, PAUSED"),
    search: Optional[str] = Query(default=None, description="Search in title/mission"),
    sort_by: str = Query(default="recent", description="recent, trending, ending_soon"),
    sectors: list[str] | None = Query(default=None, description="Only campaigns from NGOs working in one of these sectors"),
    geographies: list[str] | None = Query(default=None, description="Only campaigns from NGOs working in one of these geographies"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CampaignOut]:
    """Browse LIVE campaigns, for NGOs that are verified and have a published profile."""
    query = (
        select(Campaign, Organization.name, NgoProfile.sectors, NgoProfile.geographies)
        .join(Organization, Organization.id == Campaign.ngo_id)
        .join(NgoProfile, NgoProfile.org_id == Organization.id)
        .where(Campaign.status == status_filter, *PUBLIC_NGO_FILTER)
    )

    if search:
        search_term = f"%{search.lower()}%"
        query = query.where((Campaign.title.ilike(search_term)) | (Campaign.mission.ilike(search_term)))

    if sort_by == "trending":
        query = query.order_by(desc(Campaign.donation_count))
    elif sort_by == "ending_soon":
        query = query.order_by(Campaign.last_update_at)
    else:  # recent (default)
        query = query.order_by(desc(Campaign.published_at))

    # Sector/geography filters match against a JSON list column, so they are applied in Python
    # rather than SQL -- the candidate set here is small enough (one NGO's worth of campaigns at
    # a time) that this is simpler than a database-specific JSON-containment query.
    rows = db.execute(query).all()
    if sectors:
        wanted = set(sectors)
        rows = [r for r in rows if wanted & set(r[2])]
    if geographies:
        wanted = set(geographies)
        rows = [r for r in rows if wanted & set(r[3])]

    page = rows[offset : offset + limit]
    return [_campaign_out(c, ngo_name, list(ngo_sectors), list(ngo_geographies)) for c, ngo_name, ngo_sectors, ngo_geographies in page]


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign_for_donor(
    campaign_id: str,
    db: Session = Depends(get_db),
) -> CampaignOut:
    """Get campaign details for donor view (public campaigns only)."""
    row = db.execute(
        select(Campaign, Organization.name, NgoProfile.sectors, NgoProfile.geographies)
        .join(Organization, Organization.id == Campaign.ngo_id)
        .join(NgoProfile, NgoProfile.org_id == Organization.id)
        .where(Campaign.id == campaign_id, Campaign.status == "LIVE", *PUBLIC_NGO_FILTER)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    campaign, ngo_name, ngo_sectors, ngo_geographies = row

    # Increment view count
    campaign.view_count += 1
    db.commit()

    return _campaign_out(campaign, ngo_name, list(ngo_sectors), list(ngo_geographies))


@router.get("/campaigns/{campaign_id}/milestones", response_model=list[CampaignMilestoneOut])
def get_campaign_milestones_for_donor(
    campaign_id: str,
    db: Session = Depends(get_db),
) -> list[CampaignMilestoneOut]:
    """Get milestones for a campaign (donor view)."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != "LIVE":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    milestones = db.scalars(
        select(CampaignMilestone)
        .where(CampaignMilestone.campaign_id == campaign_id)
        .order_by(CampaignMilestone.sequence_num)
    ).all()
    return [_milestone_out(m) for m in milestones]


@router.get("/campaigns/{campaign_id}/donation-types", response_model=list[DonationTypeOut])
def get_donation_types_for_donor(
    campaign_id: str,
    db: Session = Depends(get_db),
) -> list[DonationTypeOut]:
    """Get donation type options for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != "LIVE":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    types = db.scalars(
        select(DonationType)
        .where(DonationType.campaign_id == campaign_id, DonationType.is_available == True)
        .order_by(DonationType.type)
    ).all()
    return [_donation_type_out(dt) for dt in types]


@router.get("/campaigns/{campaign_id}/impact", response_model=dict)
def get_campaign_impact(
    campaign_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get impact metrics for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != "LIVE":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    # Get stats
    total_donors = db.scalar(
        select(func.count(func.distinct(CampaignDonation.donor_email))).where(
            CampaignDonation.campaign_id == campaign_id,
            CampaignDonation.status == "COMPLETED",
        )
    ) or 0

    completion_pct = min(100, int((campaign.amount_raised / campaign.budget_total * 100))) if campaign.budget_total > 0 else 0

    milestones = db.scalars(
        select(CampaignMilestone).where(
            CampaignMilestone.campaign_id == campaign_id
        )
    ).all()

    completed_milestones = sum(1 for m in milestones if m.status == "COMPLETED")

    return {
        "campaign_id": campaign_id,
        "budget_total": campaign.budget_total,
        "amount_raised": campaign.amount_raised,
        "completion_percentage": completion_pct,
        "total_donors": total_donors,
        "donation_count": campaign.donation_count,
        "total_milestones": len(milestones),
        "completed_milestones": completed_milestones,
        "status": campaign.status,
    }


# Donation Creation
@router.post("/campaigns/{campaign_id}/donate", response_model=CampaignDonationOut, status_code=status.HTTP_201_CREATED)
def create_donation(
    campaign_id: str,
    payload: CampaignDonationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignDonationOut:
    """Create a donation to a campaign (authenticated donor)."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != "LIVE":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    # Verify donation type exists and belongs to this campaign
    donation_type = db.get(DonationType, payload.donation_type_id)
    if not donation_type or donation_type.campaign_id != campaign_id or not donation_type.is_available:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid donation type")

    # Create donation record
    donation = CampaignDonation(
        campaign_id=campaign_id,
        donation_type_id=payload.donation_type_id,
        donor_name=payload.donor_name.strip(),
        donor_email=payload.donor_email.lower(),
        donor_user_id=user.id,
        type=donation_type.type,
        amount=payload.amount,
        currency=payload.currency.upper(),
        message=payload.message.strip() if payload.message else None,
        is_anonymous=payload.is_anonymous,
        status="PENDING",  # Will move to COMPLETED after payment
    )
    db.add(donation)
    db.flush()

    # Update campaign stats
    campaign.donation_count += 1
    if donation.type == "CASH":
        campaign.amount_raised += payload.amount

    record_audit(
        db,
        action="donation.created",
        resource_type="donation",
        resource_id=donation.id,
        actor_user_id=user.id,
        org_id=campaign.ngo_id,
    )
    db.commit()

    return _donation_out(donation)


@router.post("/campaigns/{campaign_id}/donate-anonymous", response_model=CampaignDonationOut, status_code=status.HTTP_201_CREATED)
def create_anonymous_donation(
    campaign_id: str,
    payload: CampaignDonationIn,
    db: Session = Depends(get_db),
) -> CampaignDonationOut:
    """Create a donation without logging in."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.status != "LIVE":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    # Verify donation type
    donation_type = db.get(DonationType, payload.donation_type_id)
    if not donation_type or donation_type.campaign_id != campaign_id or not donation_type.is_available:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid donation type")

    # Create donation record
    donation = CampaignDonation(
        campaign_id=campaign_id,
        donation_type_id=payload.donation_type_id,
        donor_name=payload.donor_name.strip(),
        donor_email=payload.donor_email.lower(),
        donor_user_id=None,  # Anonymous
        type=donation_type.type,
        amount=payload.amount,
        currency=payload.currency.upper(),
        message=payload.message.strip() if payload.message else None,
        is_anonymous=True,
        status="PENDING",
    )
    db.add(donation)
    db.flush()

    campaign.donation_count += 1
    if donation.type == "CASH":
        campaign.amount_raised += payload.amount

    record_audit(
        db,
        action="donation.created_anonymous",
        resource_type="donation",
        resource_id=donation.id,
        org_id=campaign.ngo_id,
    )
    db.commit()

    return _donation_out(donation)


# Donor Dashboard
@router.get("/my/donations", response_model=list[CampaignDonationOut])
def get_my_donations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CampaignDonationOut]:
    """Get authenticated donor's donation history."""
    donations = db.scalars(
        select(CampaignDonation)
        .where(CampaignDonation.donor_user_id == user.id)
        .order_by(desc(CampaignDonation.created_at))
        .limit(50)
    ).all()
    return [_donation_out(d) for d in donations]


@router.get("/my/donation-stats", response_model=dict)
def get_my_donation_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get donor's donation statistics."""
    total_donated = db.scalar(
        select(func.sum(CampaignDonation.amount)).where(
            CampaignDonation.donor_user_id == user.id,
            CampaignDonation.status == "COMPLETED",
        )
    ) or 0

    donation_count = db.scalar(
        select(func.count(CampaignDonation.id)).where(
            CampaignDonation.donor_user_id == user.id,
            CampaignDonation.status == "COMPLETED",
        )
    ) or 0

    campaigns_supported = db.scalar(
        select(func.count(func.distinct(CampaignDonation.campaign_id))).where(
            CampaignDonation.donor_user_id == user.id,
            CampaignDonation.status == "COMPLETED",
        )
    ) or 0

    return {
        "total_donated": total_donated,
        "donation_count": donation_count,
        "campaigns_supported": campaigns_supported,
    }


# Helpers
def _campaign_out(c: Campaign, ngo_name: str, ngo_sectors: list[str], ngo_geographies: list[str]) -> CampaignOut:
    return CampaignOut(
        id=c.id,
        ngo_id=c.ngo_id,
        ngo_name=ngo_name,
        ngo_sectors=ngo_sectors,
        ngo_geographies=ngo_geographies,
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


def _donation_out(d: CampaignDonation) -> CampaignDonationOut:
    return CampaignDonationOut(
        id=d.id,
        campaign_id=d.campaign_id,
        donor_name=d.donor_name if not d.is_anonymous else "Anonymous Donor",
        donor_email=d.donor_email if not d.is_anonymous else "***@***.com",
        amount=d.amount,
        currency=d.currency,
        message=d.message,
        is_anonymous=d.is_anonymous,
        status=d.status,
        created_at=d.created_at,
        completed_at=d.completed_at,
    )
