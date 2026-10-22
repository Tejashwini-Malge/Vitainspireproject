from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, get_current_user_optional, require_membership
from app.domain.donation import DonationError, validate_target
from app.models import Donation, NgoProfile, Organization, Project, User
from app.schemas import BillingAddressIn, DonationIn, DonationOut

router = APIRouter(tags=["donations"])


def _donation_out(d: Donation) -> DonationOut:
    return DonationOut(
        id=d.id,
        org_id=d.org_id,
        project_id=d.project_id,
        donor_name=d.donor_name,
        donor_email=d.donor_email,
        billing_address=BillingAddressIn(**d.billing_address),
        amount_minor=d.amount_minor,
        currency=d.currency,
        message=d.message,
        created_at=d.created_at,
    )


@router.post("/public/ngos/{org_id}/donations", response_model=DonationOut, status_code=status.HTTP_201_CREATED)
def donate(
    org_id: str,
    payload: DonationIn,
    donor: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> DonationOut:
    org = db.get(Organization, org_id)
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    project = db.get(Project, payload.project_id) if payload.project_id else None
    if payload.project_id and project is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This project does not exist")
    amount_minor = int(payload.amount * 100)
    try:
        validate_target(org, profile.status if profile else None, project, amount_minor)
    except DonationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    donation = Donation(
        org_id=org_id,
        project_id=project.id if project else None,
        donor_user_id=donor.id if donor else None,
        donor_name=payload.donor_name,
        donor_email=payload.donor_email,
        billing_address=payload.billing_address.model_dump(),
        amount_minor=amount_minor,
        currency=payload.currency,
        message=payload.message,
    )
    db.add(donation)
    db.flush()
    record_audit(
        db,
        action="donation.received",
        resource_type="donation",
        resource_id=donation.id,
        actor_user_id=donor.id if donor else None,
        org_id=org_id,
        details={"amount_minor": amount_minor, "currency": payload.currency, "project_id": project.id if project else None},
    )
    db.commit()
    return _donation_out(donation)


@router.get("/orgs/{org_id}/donations", response_model=list[DonationOut])
def list_org_donations(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DonationOut]:
    require_membership(db, user, org_id)
    donations = db.scalars(select(Donation).where(Donation.org_id == org_id).order_by(Donation.created_at.desc())).all()
    return [_donation_out(d) for d in donations]


@router.get("/me/donations", response_model=list[DonationOut])
def list_my_donations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DonationOut]:
    donations = db.scalars(
        select(Donation).where(Donation.donor_user_id == user.id).order_by(Donation.created_at.desc())
    ).all()
    return [_donation_out(d) for d in donations]
