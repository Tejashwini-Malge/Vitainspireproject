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
    notify_on_proposal_approved,
    notify_on_changes_requested,
)
from app.domain.compliance import require_compliance_documents
from app.models import (
    ApprovalRequest,
    Commitment,
    Document,
    DocumentReviewDecision,
    DocumentType,
    FinanceLedger,
    Membership,
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
from app.schemas import ApprovalRequestIn, ProposalIn, ProposalOut, ProposalMessageIn, ProposalMessageOut, ProposalTimelineOut

router = APIRouter(tags=["proposals"])

MANAGE = frozenset({Role.OWNER, Role.ADMIN})


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
def approve_proposal(proposal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProposalOut:
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

    proposal.status = "APPROVED"
    db.flush()

    # Create Commitment
    commitment = Commitment(
        proposal_id=proposal.id,
        amount_minor=proposal.budget_requested,
        status="PENDING",
    )
    db.add(commitment)
    db.flush()

    # Create FinanceLedger entry (finalized immediately for pilot)
    idempotency_key = f"commitment_{commitment.id}"
    ledger = FinanceLedger(
        opportunity_id=proposal.opportunity_id,
        ngo_id=proposal.ngo_id,
        amount_minor=proposal.budget_requested,
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
        details={"commitment_id": commitment.id, "ledger_id": ledger.id},
    )

    # Trigger notifications
    notify_on_proposal_approved(db, proposal, user.id)

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
    if approval:
        approval.state = "CHANGES_REQUESTED"
        approval.approver_user_id = user.id
        approval.approver_feedback = payload.feedback

    # Update proposal status
    proposal.status = "CHANGES_REQUESTED"

    record_audit(
        db,
        action="proposal.changes_requested",
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=user.id,
        org_id=opp.org_id,
        details={"feedback": payload.feedback},
    )

    # Trigger notifications
    notify_on_changes_requested(db, proposal, payload.feedback or "", user.id)

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

    messages = db.scalars(
        select(ProposalMessage)
        .where(ProposalMessage.proposal_id == proposal_id)
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
