import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import get_current_user, require_membership
from app.services.notifications import (
    notify_on_new_message,
    notify_on_milestone_update,
    notify_on_proposal_approved,
    notify_on_changes_requested,
)
from app.domain.compliance import require_compliance_documents
from app.models import (
    ApprovalRequest,
    Commitment,
    DeliveryMilestone,
    Document,
    DocumentReviewDecision,
    DocumentType,
    FinanceLedger,
    Membership,
    NgoProfile,
    Opportunity,
    Organization,
    OrgType,
    Proposal,
    ProposalMessage,
    ProposalTimeline,
    ProposalEscalation,
    ReviewStatus,
    Role,
    Shortlist,
    User,
)
from app.schemas import (
    ApprovalRequestIn,
    DeliveryMilestoneOut,
    DeliveryMilestoneSetIn,
    DeliveryMilestoneUpdateIn,
    DeliveryProgressOut,
    ProposalApprovalIn,
    ProposalIn,
    ProposalOut,
    ProposalMessageIn,
    ProposalMessageOut,
    ProposalTimelineOut,
)

router = APIRouter(tags=["proposals"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


def _family_version_ids(db: Session, proposal: Proposal) -> list[str]:
    """Every `proposals.id` sharing this proposal's stable `proposal_id` family key.

    `proposals` is versioned: each revision inserts a new row with a new primary key but
    the same `proposal_id`. Anything that belongs to the negotiation as a whole rather
    than to one draft -- the message thread, the milestones -- has to span the family.
    """
    return list(
        db.scalars(select(Proposal.id).where(Proposal.proposal_id == proposal.proposal_id)).all()
    )


# NGO routes
@router.post("/ngo/proposals", response_model=ProposalOut, status_code=status.HTTP_201_CREATED)
def submit_proposal(
    payload: ProposalIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    # Get user's NGO org
    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User must be a member of an NGO organization")

    require_membership(db, user, ngo_org.id, allowed_roles=MANAGE)

    require_compliance_documents(db, ngo_org.id, "submitting a proposal")

    # Check if NGO is shortlisted
    shortlist = db.scalar(
        select(Shortlist)
        .where(
            Shortlist.opportunity_id == payload.opportunity_id,
            Shortlist.is_current == True,
        )
    )
    if shortlist is None or ngo_org.id not in shortlist.ngo_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NGO is not shortlisted for this opportunity")

    # Check if proposal already exists (for this opportunity/ngo)
    existing = db.scalar(
        select(Proposal)
        .where(
            Proposal.opportunity_id == payload.opportunity_id,
            Proposal.ngo_id == ngo_org.id,
            Proposal.is_current == True,
        )
    )

    proposal_id = existing.proposal_id if existing else str(uuid.uuid4())
    version_num = (existing.version_num + 1) if existing else 1

    if existing:
        existing.is_current = False

    proposal = Proposal(
        proposal_id=proposal_id,
        opportunity_id=payload.opportunity_id,
        ngo_id=ngo_org.id,
        version_num=version_num,
        is_current=True,
        problem_statement=payload.problem_statement,
        solution=payload.solution,
        budget_requested=payload.budget_requested,
        timeline=payload.timeline,
        expected_outcomes=payload.expected_outcomes,
        status="SUBMITTED",
    )
    db.add(proposal)
    db.flush()

    # Admin pre-screens every proposal before the CSR ever sees it: see POST
    # /admin/proposals/{id}/decisions. Only once admin clears it does the proposal
    # become visible to the CSR for their own approval (the "PROPOSAL" request below).
    admin_review = ApprovalRequest(
        subject_type="PROPOSAL_ADMIN_REVIEW",
        subject_id=proposal.id,
        state="PENDING",
        requested_by_user_id=user.id,
    )
    db.add(admin_review)

    # Approval request for the CSR's own later review, once admin has cleared it.
    approval = ApprovalRequest(
        subject_type="PROPOSAL",
        subject_id=proposal.id,
        state="PENDING",
        requested_by_user_id=user.id,
    )
    db.add(approval)
    db.flush()

    record_audit(
        db,
        action="proposal.submitted",
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=user.id,
        org_id=ngo_org.id,
        details={"version_num": version_num},
    )
    db.commit()
    return _proposal_out(proposal)


@router.get("/ngo/proposals", response_model=list[ProposalOut])
def list_ngo_proposals(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProposalOut]:
    ngo_org = db.scalar(
        select(Organization)
        .join(__import__("app.models", fromlist=["Membership"]).Membership)
        .where(__import__("app.models", fromlist=["Membership"]).Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        return []

    proposals = db.scalars(
        select(Proposal)
        .where(Proposal.ngo_id == ngo_org.id, Proposal.is_current == True)
        .order_by(Proposal.created_at.desc())
    ).all()
    return [_proposal_out(p) for p in proposals]


@router.get("/ngo/proposals/{proposal_id}", response_model=ProposalOut)
def get_ngo_proposal(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProposalOut:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    require_membership(db, user, proposal.ngo_id)
    return _proposal_out(proposal)


# CSR routes
@router.get("/csr/proposals", response_model=list[ProposalOut])
def list_csr_proposals(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProposalOut]:
    # Get user's CSR orgs
    csr_orgs = db.scalars(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.CSR)
    ).all()

    if not csr_orgs:
        return []

    csr_org_ids = [org.id for org in csr_orgs]

    # Get all opportunities for these CSR orgs
    opps = db.scalars(
        select(Opportunity).where(Opportunity.org_id.in_(csr_org_ids))
    ).all()
    opp_ids = [opp.id for opp in opps]

    if not opp_ids:
        return []

    # Get proposals for these opportunities
    proposals = db.scalars(
        select(Proposal)
        # SUBMITTED means "awaiting admin pre-screen" and is deliberately excluded: the
        # CSR never sees a proposal until admin has cleared it to PENDING_CSR.
        .where(Proposal.opportunity_id.in_(opp_ids), Proposal.is_current == True, Proposal.status.in_(["PENDING_CSR", "CHANGES_REQUESTED"]))
        .order_by(Proposal.created_at.desc())
    ).all()
    return [_proposal_out(p) for p in proposals]


@router.post("/csr/proposals/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(
    proposal_id: str,
    payload: ProposalApprovalIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """Approve a proposal, optionally at a negotiated amount.

    The body is optional and omitting it commits the full requested budget, which is what
    this endpoint always did. Supplying `amount_minor` commits that amount instead -- the
    whole point of letting the two sides negotiate the budget in the message thread is
    that the agreed figure, not the original ask, is what gets committed.
    """
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")

    opp = db.get(Opportunity, proposal.opportunity_id)
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    if proposal.status == "APPROVED":
        return _proposal_out(proposal)
    if proposal.status != "PENDING_CSR":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This proposal is {proposal.status} and is not yet available for your approval",
        )

    requested = proposal.budget_requested
    amount_minor = payload.amount_minor if payload and payload.amount_minor is not None else requested
    # Deterministic guard: approving above the ask is not a negotiation outcome, it is a
    # data-entry error, and the ledger is append-only so it cannot be quietly undone.
    if amount_minor > requested:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Committed amount {amount_minor} exceeds the requested budget {requested}. "
            "Ask the NGO to submit a revision at the higher figure instead.",
        )

    proposal.status = "APPROVED"
    db.flush()

    # Create Commitment
    commitment = Commitment(
        proposal_id=proposal.id,
        amount_minor=amount_minor,
        status="PENDING",
    )
    db.add(commitment)
    db.flush()

    # Create FinanceLedger entry (finalized immediately for pilot)
    idempotency_key = f"commitment_{commitment.id}"
    ledger = FinanceLedger(
        opportunity_id=proposal.opportunity_id,
        ngo_id=proposal.ngo_id,
        amount_minor=amount_minor,
        transaction_type="COMMITMENT",
        idempotency_key=idempotency_key,
        recorded_by_user_id=user.id,
    )
    db.add(ledger)
    db.flush()

    commitment.status = "CONFIRMED"
    commitment.confirmed_at = datetime.now(UTC)
    db.flush()

    # Update approval request
    approval = db.scalar(
        select(ApprovalRequest).where(ApprovalRequest.subject_id == proposal.id, ApprovalRequest.subject_type == "PROPOSAL")
    )
    if approval:
        approval.state = "APPROVED"
        approval.approver_user_id = user.id
        approval.approved_at = datetime.now(UTC)

    record_audit(
        db,
        action="proposal.approved",
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
        details={
            "commitment_id": commitment.id,
            "ledger_id": ledger.id,
            "amount_minor": amount_minor,
            "budget_requested": requested,
            "negotiated": amount_minor != requested,
            "approver_feedback": payload.approver_feedback if payload else None,
        },
    )

    # Trigger notifications
    notify_on_proposal_approved(db, proposal, user.id, committed_amount_minor=amount_minor)

    db.commit()
    return _proposal_out(proposal)


@router.post("/csr/proposals/{proposal_id}/request-changes", response_model=ProposalOut)
def request_changes(
    proposal_id: str,
    payload: ApprovalRequestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")

    opp = db.get(Opportunity, proposal.opportunity_id)
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    if proposal.status != "PENDING_CSR":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This proposal is {proposal.status} and is not yet available for your review",
        )

    # Update approval request
    approval = db.scalar(
        select(ApprovalRequest).where(ApprovalRequest.subject_id == proposal.id, ApprovalRequest.subject_type == "PROPOSAL")
    )
    feedback = payload.feedback_text
    if approval:
        approval.state = "CHANGES_REQUESTED"
        approval.approver_user_id = user.id
        approval.approver_feedback = feedback

    # Update proposal status
    proposal.status = "CHANGES_REQUESTED"

    record_audit(
        db,
        action="proposal.changes_requested",
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
        details={"feedback": feedback},
    )

    # The feedback is the substance of the request; carry it into the thread so the
    # negotiation and the formal decision are not two separate conversations.
    if feedback:
        db.add(
            ProposalMessage(
                proposal_id=proposal.id,
                sender_id=user.id,
                sender_type="CSR",
                content=feedback,
            )
        )

    # Trigger notifications
    notify_on_changes_requested(db, proposal, feedback or "", user.id)

    db.commit()
    return _proposal_out(proposal)


# Profile generation endpoints
@router.post("/ngo/generate-about")
def generate_about(
    payload: dict,
    user: User = Depends(get_current_user),
) -> dict:
    """Generate about section based on mission, sectors, and optionally website content."""
    from app.config import settings
    import requests
    from bs4 import BeautifulSoup

    mission = payload.get("mission", "")
    sectors = payload.get("sectors", [])
    website_url = payload.get("website_url")

    if not mission or not sectors:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mission and sectors are required")

    # Try to fetch website content if URL provided
    website_content = ""
    if website_url:
        try:
            # Add https:// if not present
            if not website_url.startswith(("http://", "https://")):
                website_url = f"https://{website_url}"

            response = requests.get(website_url, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # Extract meta description
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    website_content += "Meta description: " + meta_desc.get("content", "") + "\n"

                # Extract all text, limit to first 2000 chars
                text = soup.get_text(separator=" ", strip=True)
                website_content += text[:2000]
        except Exception:
            # Silently fail website fetch
            website_content = ""

    try:
        if not settings.llm_api_key:
            # Fallback if no API key
            return {
                "about": "We are working to create positive change in our community. Our approach combines proven methodologies with local insights. We measure impact and continuously improve our programs."
            }

        # Build prompt with website content if available
        if website_content:
            prompt = f"""Based on this information, generate a concise "about" section for an NGO:

Mission: {mission}
Sectors: {', '.join(sectors)}

Website content (use this to personalize the about section):
{website_content}

Generate 2-3 sentences describing the organization's work, approach, and impact. Use insights from their website if available. Keep it professional and inspiring.
Return ONLY the text, no JSON."""
        else:
            prompt = f"""Based on this mission and sectors, generate a concise "about" section:

Mission: {mission}
Sectors: {', '.join(sectors)}

Generate 2-3 sentences describing the organization's work, approach, and impact. Keep it professional and inspiring.
Return ONLY the text, no JSON."""

        # Use OpenRouter API
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}")

        data = response.json()
        about_text = data["choices"][0]["message"]["content"].strip()

        return {"about": about_text}

    except Exception as e:
        # Fallback on error
        return {
            "about": "We are working to create positive change in our community. Our approach combines proven methodologies with local insights. We measure impact and continuously improve our programs."
        }


@router.post("/ngo/proposals/generate-draft")
def generate_proposal_draft(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Draft proposal text (problem statement, solution, timeline, expected outcomes)
    from the selected opportunity and the NGO's own profile.

    This is a starting point for the NGO to edit, not a submission -- the human still
    reviews and edits every field before "Submit Proposal" is clicked.
    """
    from app.config import settings
    import json as json_lib
    import requests

    opportunity_id = payload.get("opportunity_id")
    if not opportunity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "opportunity_id is required")

    opp = db.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")

    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )
    if ngo_org is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User must be a member of an NGO organization")

    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == ngo_org.id))

    fallback = {
        "problem_statement": f"Communities in {', '.join(opp.geographies) or 'our focus areas'} face challenges related to {', '.join(opp.sectors) or 'the sectors this opportunity addresses'}, limiting access to the support they need.",
        "solution": f"{ngo_org.name} will apply our experience in {', '.join((profile.sectors if profile else []) or opp.sectors)} to deliver targeted, measurable interventions aligned with this opportunity's requirements.",
        "timeline": "12 months",
        "expected_outcomes": "Improved outcomes for the target beneficiaries, tracked against clear milestones and reported transparently to the funder.",
    }

    if not settings.llm_api_key:
        return fallback

    prompt = f"""You are helping an NGO draft a funding proposal in response to a CSR opportunity. Use only the facts given below -- do not invent statistics, partners, or outcomes.

Opportunity title: {opp.title}
Opportunity description: {opp.description}
Opportunity sectors: {', '.join(opp.sectors) or 'not specified'}
Opportunity geographies: {', '.join(opp.geographies) or 'not specified'}
Budget range: {opp.budget_min or 'not specified'} to {opp.budget_max or 'not specified'}
Requirements: {opp.requirements_text}

NGO name: {ngo_org.name}
NGO mission: {(profile.mission if profile else '') or 'not provided'}
NGO sectors: {', '.join(profile.sectors) if profile and profile.sectors else 'not provided'}
NGO about: {(profile.about if profile else '') or 'not provided'}

Return ONLY a JSON object with these exact keys, no markdown, no commentary:
{{
  "problem_statement": "2-4 sentences describing the problem this proposal addresses",
  "solution": "2-4 sentences describing the NGO's proposed approach",
  "timeline": "a short phrase like '12 months'",
  "expected_outcomes": "2-4 sentences describing measurable expected outcomes"
}}"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}")

        text = response.json()["choices"][0]["message"]["content"].strip()
        # Models sometimes wrap JSON in a markdown fence despite instructions.
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        draft = json_lib.loads(text)

        return {
            "problem_statement": draft.get("problem_statement") or fallback["problem_statement"],
            "solution": draft.get("solution") or fallback["solution"],
            "timeline": draft.get("timeline") or fallback["timeline"],
            "expected_outcomes": draft.get("expected_outcomes") or fallback["expected_outcomes"],
        }
    except Exception:
        return fallback


# Delivery milestone routes
#
# These are what turns an approved proposal into work the CSR can watch. The NGO owns the
# plan and the progress; the CSR owns verification. Neither side can write the other's
# half, and the amounts are checked against the confirmed commitment rather than trusted.


def _milestone_out(m: DeliveryMilestone) -> DeliveryMilestoneOut:
    return DeliveryMilestoneOut(
        id=m.id,
        proposal_id=m.proposal_id,
        commitment_id=m.commitment_id,
        ngo_id=m.ngo_id,
        opportunity_id=m.opportunity_id,
        sequence_num=m.sequence_num,
        title=m.title,
        description=m.description,
        target_date=m.target_date,
        amount_minor=m.amount_minor,
        status=m.status,
        evidence_url=m.evidence_url,
        completed_at=m.completed_at,
        verified_at=m.verified_at,
        verified_by_user_id=m.verified_by_user_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _approved_commitment(db: Session, proposal: Proposal) -> Commitment:
    """The confirmed commitment for this proposal family, or a 409 explaining why not."""
    commitment = db.scalar(
        select(Commitment).where(Commitment.proposal_id.in_(_family_version_ids(db, proposal)))
    )
    if commitment is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This proposal has not been approved yet, so there is nothing to deliver against.",
        )
    return commitment


def _party_for_proposal(db: Session, user: User, proposal: Proposal) -> str:
    """Return 'NGO' or 'CSR' for a user entitled to see this proposal, else 404/403."""
    opp = db.get(Opportunity, proposal.opportunity_id)
    try:
        require_membership(db, user, proposal.ngo_id)
        return "NGO"
    except HTTPException:
        require_membership(db, user, opp.org_id)
        return "CSR"


@router.get("/proposals/{proposal_id}/milestones", response_model=DeliveryProgressOut)
def get_delivery_progress(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryProgressOut:
    """The delivery plan and its progress. Both the NGO and the funding CSR read this."""
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    _party_for_proposal(db, user, proposal)
    commitment = _approved_commitment(db, proposal)

    milestones = db.scalars(
        select(DeliveryMilestone)
        .where(DeliveryMilestone.proposal_id == proposal.proposal_id)
        .order_by(DeliveryMilestone.sequence_num.asc())
    ).all()

    today = datetime.now(UTC).date()
    completed = [m for m in milestones if m.status in ("COMPLETED", "VERIFIED")]
    verified = [m for m in milestones if m.status == "VERIFIED"]
    overdue = [m for m in milestones if m.status not in ("COMPLETED", "VERIFIED") and m.target_date < today]
    upcoming = [m for m in milestones if m.status not in ("COMPLETED", "VERIFIED")]

    return DeliveryProgressOut(
        proposal_id=proposal.proposal_id,
        committed_amount_minor=commitment.amount_minor,
        milestone_count=len(milestones),
        completed_count=len(completed),
        verified_count=len(verified),
        percent_verified=round(100 * len(verified) / len(milestones)) if milestones else 0,
        next_due=_milestone_out(min(upcoming, key=lambda m: m.target_date)) if upcoming else None,
        overdue_count=len(overdue),
        milestones=[_milestone_out(m) for m in milestones],
    )


@router.post(
    "/ngo/proposals/{proposal_id}/milestones",
    response_model=list[DeliveryMilestoneOut],
    status_code=status.HTTP_201_CREATED,
)
def set_delivery_milestones(
    proposal_id: str,
    payload: DeliveryMilestoneSetIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeliveryMilestoneOut]:
    """The NGO declares its delivery plan against an approved proposal.

    Replaces the existing plan, which is only allowed while no milestone has been reported
    complete -- once the CSR has started watching progress, the plan it agreed to cannot
    be rewritten underneath it.
    """
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    require_membership(db, user, proposal.ngo_id, allowed_roles=MANAGE)
    commitment = _approved_commitment(db, proposal)

    existing = db.scalars(
        select(DeliveryMilestone).where(DeliveryMilestone.proposal_id == proposal.proposal_id)
    ).all()
    if any(m.status != "PENDING" for m in existing):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Work has already been reported against this plan. Milestones can no longer be replaced.",
        )

    total = sum(m.amount_minor for m in payload.milestones)
    if total > commitment.amount_minor:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Milestone amounts total {total}, which exceeds the committed "
            f"{commitment.amount_minor}.",
        )

    for m in existing:
        db.delete(m)
    db.flush()

    created: list[DeliveryMilestone] = []
    for i, item in enumerate(payload.milestones, start=1):
        milestone = DeliveryMilestone(
            proposal_id=proposal.proposal_id,
            commitment_id=commitment.id,
            ngo_id=proposal.ngo_id,
            opportunity_id=proposal.opportunity_id,
            sequence_num=i,
            title=item.title.strip(),
            description=item.description.strip(),
            target_date=item.target_date,
            amount_minor=item.amount_minor,
            status="PENDING",
        )
        db.add(milestone)
        created.append(milestone)
    db.flush()

    record_audit(
        db,
        action="delivery.milestones_set",
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=user.id,
        org_id=proposal.ngo_id,
        details={"count": len(created), "total_amount_minor": total},
    )
    db.commit()
    return [_milestone_out(m) for m in created]


@router.patch("/ngo/milestones/{milestone_id}", response_model=DeliveryMilestoneOut)
def update_delivery_milestone(
    milestone_id: str,
    payload: DeliveryMilestoneUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryMilestoneOut:
    """The NGO reports progress. Only the NGO moves a milestone to IN_PROGRESS/COMPLETED."""
    milestone = db.get(DeliveryMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
    require_membership(db, user, milestone.ngo_id, allowed_roles=MANAGE)

    if milestone.status == "VERIFIED":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This milestone has been verified by the funder and is final."
        )

    if payload.evidence_url is not None:
        milestone.evidence_url = payload.evidence_url.strip() or None

    if payload.status is not None:
        if payload.status not in ("PENDING", "IN_PROGRESS", "COMPLETED"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Status must be PENDING, IN_PROGRESS or COMPLETED. Only the funder marks a "
                "milestone VERIFIED.",
            )
        milestone.status = payload.status
        milestone.completed_at = datetime.now(UTC) if payload.status == "COMPLETED" else None

    milestone.updated_at = datetime.now(UTC)
    db.flush()

    proposal = db.scalar(
        select(Proposal).where(
            Proposal.proposal_id == milestone.proposal_id, Proposal.is_current == True
        )
    )
    record_audit(
        db,
        action="delivery.milestone_updated",
        resource_type="delivery_milestone",
        resource_id=milestone.id,
        actor_user_id=user.id,
        org_id=milestone.ngo_id,
        details={"status": milestone.status, "evidence_url": milestone.evidence_url},
    )
    if proposal is not None:
        notify_on_milestone_update(db, proposal, milestone.title, milestone.status, user.id)
    db.commit()
    return _milestone_out(milestone)


@router.post("/csr/milestones/{milestone_id}/verify", response_model=DeliveryMilestoneOut)
def verify_delivery_milestone(
    milestone_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeliveryMilestoneOut:
    """The funding CSR confirms a completed milestone. Terminal state."""
    milestone = db.get(DeliveryMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")

    opp = db.get(Opportunity, milestone.opportunity_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
    require_membership(db, user, opp.org_id, allowed_roles=MANAGE)

    if milestone.status == "VERIFIED":
        return _milestone_out(milestone)
    if milestone.status != "COMPLETED":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This milestone is {milestone.status}. Only a COMPLETED milestone can be verified.",
        )

    milestone.status = "VERIFIED"
    milestone.verified_at = datetime.now(UTC)
    milestone.verified_by_user_id = user.id
    milestone.updated_at = datetime.now(UTC)
    db.flush()

    record_audit(
        db,
        action="delivery.milestone_verified",
        resource_type="delivery_milestone",
        resource_id=milestone.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
        details={"ngo_id": milestone.ngo_id},
    )
    db.commit()
    return _milestone_out(milestone)


# Messaging routes
@router.get("/proposals/{proposal_id}/messages", response_model=list[ProposalMessageOut])
def get_proposal_messages(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProposalMessageOut]:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")

    # Check user has access (member of NGO or CSR org)
    opp = db.get(Opportunity, proposal.opportunity_id)
    try:
        require_membership(db, user, proposal.ngo_id)
    except HTTPException:
        require_membership(db, user, opp.org_id)

    # Read across every version of this proposal, not just the row addressed in the URL.
    # Each revision creates a new `proposals` row, and messages are stored against the row
    # id that was current when they were sent -- so a thread keyed to one row loses the
    # whole negotiation the moment the NGO submits the revision that negotiation asked for.
    messages = db.scalars(
        select(ProposalMessage)
        .where(ProposalMessage.proposal_id.in_(_family_version_ids(db, proposal)))
        .order_by(ProposalMessage.created_at.asc())
    ).all()

    return [
        ProposalMessageOut(
            id=m.id,
            proposal_id=m.proposal_id,
            sender_id=m.sender_id,
            sender_type=m.sender_type,
            content=m.content,
            created_at=m.created_at,
            read_at=m.read_at,
        )
        for m in messages
    ]


@router.post("/proposals/{proposal_id}/messages", response_model=ProposalMessageOut, status_code=status.HTTP_201_CREATED)
def send_proposal_message(
    proposal_id: str,
    payload: ProposalMessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalMessageOut:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")

    opp = db.get(Opportunity, proposal.opportunity_id)

    # Determine sender type and verify access
    ngo_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.NGO)
    )

    csr_org = db.scalar(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id, Organization.org_type == OrgType.CSR)
    )

    if ngo_org and ngo_org.id == proposal.ngo_id:
        sender_type = "NGO"
    elif csr_org and csr_org.id == opp.org_id:
        sender_type = "CSR"
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User not authorized to message on this proposal")

    message = ProposalMessage(
        proposal_id=proposal_id,
        sender_id=user.id,
        sender_type=sender_type,
        content=payload.content,
    )
    db.add(message)
    db.flush()

    # Update timeline
    timeline = db.scalar(
        select(ProposalTimeline).where(ProposalTimeline.proposal_id == proposal_id)
    )
    if not timeline:
        timeline = ProposalTimeline(proposal_id=proposal_id)
        db.add(timeline)

    timeline.last_activity_at = datetime.now(UTC)
    timeline.waiting_on = "CSR" if sender_type == "NGO" else "NGO"
    db.flush()

    record_audit(
        db,
        action="proposal.message_sent",
        resource_type="proposal",
        resource_id=proposal_id,
        actor_user_id=user.id,
        org_id=ngo_org.id if ngo_org else opp.org_id,
        details={"sender_type": sender_type},
    )

    # Trigger notifications
    notify_on_new_message(db, proposal, user.id, sender_type)

    db.commit()

    return ProposalMessageOut(
        id=message.id,
        proposal_id=message.proposal_id,
        sender_id=message.sender_id,
        sender_type=message.sender_type,
        content=message.content,
        created_at=message.created_at,
        read_at=message.read_at,
    )


@router.get("/proposals/{proposal_id}/timeline", response_model=ProposalTimelineOut)
def get_proposal_timeline(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalTimelineOut:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")

    # Check user has access
    opp = db.get(Opportunity, proposal.opportunity_id)
    try:
        require_membership(db, user, proposal.ngo_id)
    except HTTPException:
        require_membership(db, user, opp.org_id)

    timeline = db.scalar(
        select(ProposalTimeline).where(ProposalTimeline.proposal_id == proposal_id)
    )

    if not timeline:
        timeline = ProposalTimeline(proposal_id=proposal_id)
        db.add(timeline)
        db.commit()

    from datetime import timedelta
    now = datetime.now(UTC)
    days_since = (now - timeline.last_activity_at).days

    return ProposalTimelineOut(
        proposal_id=timeline.proposal_id,
        last_activity_at=timeline.last_activity_at,
        reply_deadline=timeline.reply_deadline,
        waiting_on=timeline.waiting_on,
        days_since_activity=days_since,
        is_overdue=(timeline.reply_deadline and now > timeline.reply_deadline) or False,
    )


def _proposal_out(p: Proposal) -> ProposalOut:
    return ProposalOut(
        id=p.id,
        proposal_id=p.proposal_id,
        opportunity_id=p.opportunity_id,
        ngo_id=p.ngo_id,
        version_num=p.version_num,
        is_current=p.is_current,
        problem_statement=p.problem_statement,
        solution=p.solution,
        budget_requested=p.budget_requested,
        timeline=p.timeline,
        expected_outcomes=p.expected_outcomes,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )
