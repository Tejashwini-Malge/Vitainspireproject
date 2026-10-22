from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.models import (
    Opportunity,
    Organization,
    OrgType,
    Role,
    User,
    Membership,
    EligibilityResult,
    FitScore,
    Shortlist,
)
from app.schemas import OpportunityIn, OpportunityOut, FitScoreOut, ShortlistIn, ShortlistOut

router = APIRouter(prefix="/csr/opportunities", tags=["csr-opportunities"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


@router.post("", response_model=OpportunityOut, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OpportunityOut:
    # Get user's CSR org
    org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.CSR)
    )
    if org is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User must be a member of a CSR organization")

    require_membership(db, user, org.id, allowed_roles=MANAGE)

    opp = Opportunity(
        org_id=org.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        sectors=payload.sectors,
        geographies=payload.geographies,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
        deadline=payload.deadline,
        requirements_text=payload.requirements_text.strip(),
    )
    db.add(opp)
    db.flush()
    record_audit(
        db,
        action="opportunity.created",
        resource_type="opportunity",
        resource_id=opp.id,
        actor_user_id=user.id,
        org_id=org.id,
    )
    db.commit()
    return _opportunity_out(opp)


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OpportunityOut]:
    """Opportunities belonging to the CSR organisations this user is a member of.

    Scoped by membership, so a user who belongs to no CSR organisation gets an empty
    list rather than another organisation's data.
    """
    org_ids = list(
        db.scalars(
            select(Organization.id)
            .join(Membership, Membership.org_id == Organization.id)
            .where(Membership.user_id == user.id, Organization.org_type == OrgType.CSR)
        ).all()
    )
    if not org_ids:
        return []

    query = select(Opportunity).where(Opportunity.org_id.in_(org_ids))
    if status_filter:
        query = query.where(Opportunity.status == status_filter)

    opps = db.scalars(query.order_by(Opportunity.created_at.desc())).all()
    return [_opportunity_out(o) for o in opps]


@router.post("/shortlist", response_model=ShortlistOut, status_code=status.HTTP_201_CREATED)
def create_shortlist(
    payload: ShortlistIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShortlistOut:
    opp = db.get(Opportunity, payload.opportunity_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    # Get the highest revision number for this opportunity and calculate next revision
    from sqlalchemy import func
    max_revision = db.scalar(
        select(func.max(Shortlist.revision_num))
        .where(Shortlist.opportunity_id == opp.id)
    ) or 0
    next_revision = max_revision + 1

    # Mark any existing current shortlist as not current
    db.execute(
        select(Shortlist)
        .where(Shortlist.opportunity_id == opp.id, Shortlist.is_current == True)
    ).scalars().all()

    current_shortlists = db.scalars(
        select(Shortlist)
        .where(Shortlist.opportunity_id == opp.id, Shortlist.is_current == True)
    ).all()
    for sl in current_shortlists:
        sl.is_current = False

    shortlist = Shortlist(
        shortlist_id=opp.id,
        opportunity_id=opp.id,
        revision_num=next_revision,
        ngo_ids=payload.ngo_ids,
        is_current=True,
        selected_by_user_id=user.id,
    )
    db.add(shortlist)
    db.flush()
    record_audit(
        db,
        action="shortlist.created",
        resource_type="shortlist",
        resource_id=shortlist.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
        details={"ngo_ids": payload.ngo_ids},
    )
    db.commit()
    return _shortlist_out(shortlist)


@router.get("/{opp_id}", response_model=OpportunityOut)
def get_opportunity(opp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OpportunityOut:
    opp = db.get(Opportunity, opp_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)
    return _opportunity_out(opp)


@router.post("/{opp_id}/publish", response_model=OpportunityOut)
def publish_opportunity(opp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OpportunityOut:
    opp = db.get(Opportunity, opp_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    if opp.status == "PUBLISHED":
        return _opportunity_out(opp)

    opp.status = "PUBLISHED"
    opp.published_at = datetime.now(UTC)
    db.flush()
    record_audit(
        db,
        action="opportunity.published",
        resource_type="opportunity",
        resource_id=opp.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
    )
    db.commit()
    return _opportunity_out(opp)


@router.get("/{opp_id}/fit-scores", response_model=list[FitScoreOut])
def get_fit_scores(opp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FitScoreOut]:
    opp = db.get(Opportunity, opp_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    scores = db.scalars(
        select(FitScore)
        .where(FitScore.opportunity_id == opp_id)
        .order_by(FitScore.score.desc())
    ).all()

    result = []
    for score in scores:
        ngo = db.get(Organization, score.ngo_id)
        result.append(
            FitScoreOut(
                ngo_id=score.ngo_id,
                ngo_name=ngo.name if ngo else "Unknown",
                sectors=ngo.ngo_profiles[0].sectors if ngo and hasattr(ngo, 'ngo_profiles') else [],
                score=score.score,
                explanation=score.explanation,
                confidence=score.confidence,
            )
        )
    return result


def _opportunity_out(opp: Opportunity) -> OpportunityOut:
    return OpportunityOut(
        id=opp.id,
        org_id=opp.org_id,
        title=opp.title,
        description=opp.description,
        sectors=opp.sectors,
        geographies=opp.geographies,
        budget_min=opp.budget_min,
        budget_max=opp.budget_max,
        deadline=opp.deadline,
        requirements_text=opp.requirements_text,
        status=opp.status,
        published_at=opp.published_at,
        created_at=opp.created_at,
        updated_at=opp.updated_at,
    )


def _shortlist_out(sl: Shortlist) -> ShortlistOut:
    return ShortlistOut(
        id=sl.id,
        shortlist_id=sl.shortlist_id,
        opportunity_id=sl.opportunity_id,
        revision_num=sl.revision_num,
        ngo_ids=sl.ngo_ids,
        is_current=sl.is_current,
        selected_by_user_id=sl.selected_by_user_id,
        selected_at=sl.selected_at,
    )
