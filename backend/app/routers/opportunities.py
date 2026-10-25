from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fit import MODEL_VERSION, rank_candidates
from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.domain.compliance import missing_required_documents
from app.models import (
    NgoProfile,
    Opportunity,
    Organization,
    OrgType,
    Proposal,
    Role,
    User,
    Membership,
    EligibilityResult,
    FitScore,
    Shortlist,
)
from app.schemas import (
    OpportunityIn,
    OpportunityOut,
    FitScoreOut,
    ShortlistedOpportunityOut,
    ShortlistIn,
    ShortlistOut,
)
from app.services.notifications import notify_on_shortlisted

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
    """List opportunities.

    Requesting PUBLISHED opportunities returns them across every CSR organisation —
    that's the discovery feed NGOs browse to submit proposals against, not just the
    caller's own org. Any other request (drafts, or no filter) stays scoped to the
    CSR organisations this user is a member of, so a user who belongs to no CSR
    organisation gets an empty list rather than another organisation's draft data.
    """
    if status_filter == "PUBLISHED":
        query = select(Opportunity).where(Opportunity.status == status_filter)
        opps = db.scalars(query.order_by(Opportunity.created_at.desc())).all()
        return [_opportunity_out(o) for o in opps]

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

    # Refuse an NGO that could never follow through: the same deterministic gate that
    # `submit_proposal` applies. Without this the CSR shortlists an organisation, it is
    # told it was selected, and it then hits a 403 it cannot clear.
    ngo_ids = list(dict.fromkeys(payload.ngo_ids))
    blocked: dict[str, list[str]] = {}
    for ngo_id in ngo_ids:
        org = db.get(Organization, ngo_id)
        if org is None or org.org_type is not OrgType.NGO:
            blocked[ngo_id] = ["Not an NGO organisation"]
            continue
        missing = missing_required_documents(db, ngo_id)
        if missing:
            blocked[ngo_id] = [f"Missing approved document: {d.value}" for d in sorted(missing, key=lambda x: x.value)]
    if blocked:
        detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in blocked.items())
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"These organisations cannot be shortlisted yet -- {detail}",
        )

    # Get the highest revision number for this opportunity and calculate next revision
    from sqlalchemy import func
    max_revision = db.scalar(
        select(func.max(Shortlist.revision_num))
        .where(Shortlist.opportunity_id == opp.id)
    ) or 0
    next_revision = max_revision + 1

    # Mark any existing current shortlist as not current, remembering who was already on
    # it so a revision does not re-notify organisations that were selected before.
    current_shortlists = db.scalars(
        select(Shortlist)
        .where(Shortlist.opportunity_id == opp.id, Shortlist.is_current == True)
    ).all()
    previously: set[str] = set()
    for sl in current_shortlists:
        previously.update(sl.ngo_ids or [])
        sl.is_current = False

    shortlist = Shortlist(
        shortlist_id=opp.id,
        opportunity_id=opp.id,
        revision_num=next_revision,
        ngo_ids=ngo_ids,
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
        details={"ngo_ids": ngo_ids, "newly_added": sorted(set(ngo_ids) - previously)},
    )

    # The point of a shortlist is that the NGO finds out. Same transaction as the audit row.
    notify_on_shortlisted(db, opp, ngo_ids, user.id, previously_shortlisted=frozenset(previously))

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


def _compute_fit_scores(db: Session, opp: Opportunity, user: User) -> list[FitScore]:
    """Recompute and persist the candidate ranking for one opportunity.

    Replaces any previous run: a stale ranking is worse than none, because the CSR cannot
    tell by looking that it predates the NGO's latest profile or document approvals.
    """
    candidates, ineligible = rank_candidates(db, opp)

    for row in db.scalars(select(FitScore).where(FitScore.opportunity_id == opp.id)).all():
        db.delete(row)
    for row in db.scalars(select(EligibilityResult).where(EligibilityResult.opportunity_id == opp.id)).all():
        db.delete(row)
    db.flush()

    stored: list[FitScore] = []
    for c in candidates:
        fit = FitScore(
            opportunity_id=opp.id,
            ngo_id=c.ngo_id,
            score=c.score,
            explanation=c.explanation,
            confidence=c.confidence,
            model_version=MODEL_VERSION if c.generated_by == "rules" else f"{MODEL_VERSION}+{c.generated_by}",
        )
        db.add(fit)
        stored.append(fit)
        db.add(
            EligibilityResult(
                opportunity_id=opp.id, ngo_id=c.ngo_id, passed=True, reason="Meets all eligibility requirements"
            )
        )
    for ngo_id, reasons in ineligible:
        db.add(
            EligibilityResult(
                opportunity_id=opp.id, ngo_id=ngo_id, passed=False, reason="; ".join(reasons) or "Not eligible"
            )
        )
    db.flush()

    record_audit(
        db,
        action="opportunity.fit_scores_computed",
        resource_type="opportunity",
        resource_id=opp.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
        details={
            "model_version": MODEL_VERSION,
            "eligible": len(candidates),
            "ineligible": len(ineligible),
        },
    )
    return stored


def _fit_out(db: Session, scores: list[FitScore]) -> list[FitScoreOut]:
    out = []
    for score in scores:
        ngo = db.get(Organization, score.ngo_id)
        profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == score.ngo_id))
        out.append(
            FitScoreOut(
                ngo_id=score.ngo_id,
                ngo_name=ngo.name if ngo else "Unknown",
                sectors=list(profile.sectors or []) if profile else [],
                score=score.score,
                explanation=score.explanation,
                confidence=score.confidence,
            )
        )
    return out


@router.get("/{opp_id}/fit-scores", response_model=list[FitScoreOut])
def get_fit_scores(opp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FitScoreOut]:
    """Ranked candidate NGOs for this opportunity.

    Computes on first request and caches the result, because nothing else in the system
    triggers a ranking run. Use POST /fit-scores/compute to force a refresh after NGO
    profiles or document approvals have changed.
    """
    opp = db.get(Opportunity, opp_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    scores = db.scalars(
        select(FitScore)
        .where(FitScore.opportunity_id == opp_id)
        .order_by(FitScore.score.desc())
    ).all()

    if not scores:
        scores = _compute_fit_scores(db, opp, user)
        db.commit()
        scores = db.scalars(
            select(FitScore).where(FitScore.opportunity_id == opp_id).order_by(FitScore.score.desc())
        ).all()

    return _fit_out(db, list(scores))


@router.post("/{opp_id}/fit-scores/compute", response_model=list[FitScoreOut])
def compute_fit_scores(opp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FitScoreOut]:
    """Force a fresh ranking run."""
    opp = db.get(Opportunity, opp_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    _compute_fit_scores(db, opp, user)
    db.commit()
    scores = db.scalars(
        select(FitScore).where(FitScore.opportunity_id == opp_id).order_by(FitScore.score.desc())
    ).all()
    return _fit_out(db, list(scores))


ngo_router = APIRouter(prefix="/ngo", tags=["ngo-opportunities"])


@ngo_router.get("/opportunities", response_model=list[ShortlistedOpportunityOut])
def list_shortlisted_opportunities(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShortlistedOpportunityOut]:
    """Opportunities this NGO has been selected for, and where each one stands.

    The published-opportunity feed answers "what exists"; this answers "who picked me",
    which is what an NGO acts on. Only current shortlist revisions count, so an NGO
    dropped in a later revision stops seeing the opportunity here.
    """
    ngo_org = db.scalar(
        select(Organization)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        return []

    shortlists = db.scalars(select(Shortlist).where(Shortlist.is_current == True)).all()
    missing = missing_required_documents(db, ngo_org.id)
    blockers = [f"Missing approved document: {d.value}" for d in sorted(missing, key=lambda x: x.value)]

    results: list[ShortlistedOpportunityOut] = []
    for sl in shortlists:
        if ngo_org.id not in (sl.ngo_ids or []):
            continue
        opp = db.get(Opportunity, sl.opportunity_id)
        if opp is None:
            continue
        csr_org = db.get(Organization, opp.org_id)
        proposal = db.scalar(
            select(Proposal).where(
                Proposal.opportunity_id == opp.id,
                Proposal.ngo_id == ngo_org.id,
                Proposal.is_current == True,
            )
        )
        results.append(
            ShortlistedOpportunityOut(
                opportunity=_opportunity_out(opp),
                csr_org_id=opp.org_id,
                csr_org_name=csr_org.name if csr_org else "Unknown",
                shortlisted_at=sl.selected_at,
                proposal_id=proposal.id if proposal else None,
                proposal_status=proposal.status if proposal else None,
                can_submit_proposal=not blockers and proposal is None,
                blockers=blockers,
            )
        )

    results.sort(key=lambda r: r.shortlisted_at, reverse=True)
    return results


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
