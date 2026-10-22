from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from app.ai.assist import draft_verification_assist
from app.ai.document_assist import draft_document_assist
from app.audit import record_audit
from app.db import get_db
from app.deps import is_member, require_platform_admin
from app.domain.review import ReviewError, decide
from app.models import (
    ApprovalRequest, Document, DocumentReviewDecision, NgoProfile, Opportunity, Organization, OrgType,
    PanVerification, PanVerificationDecision, Proposal, ReviewStatus, User, VerificationStatus,
    Campaign, CampaignDonation, Donation, EmailQueue, Membership, Payment, SentEmail, Project, ProjectStatus
)
from app.routers.documents import _decision_out, file_response
from app.routers.pan_verification import _decision_out as _pan_decision_out
from app.routers.projects import _project_out
from app.routers.proposals import _proposal_out
from app.schemas import (
    AdminDecisionOut, AdminPanDecisionOut, AdminPanQueueItemOut, AdminQueueItemOut, OrgOut, ReviewDecisionIn,
    VerificationAssistOut, VerificationDecisionIn,
    FundraisingTrendOut, CampaignPerformanceOut, EmailEngagementOut, QueueMetricsOut, NgoPerfMetricsOut,
    DonorSegmentOut, AdminDashboardOut, DocumentAssistOut, DocumentFindingOut,
    AdminIndividualDonorRowOut, AdminOrgRowOut, AdminPaymentRowOut, AdminProjectQueueItemOut, AdminProjectRowOut,
    AdminProposalQueueItemOut, ProjectOut, ProjectReviewDecisionIn, ProposalAdminDecisionIn, ProposalOut
)
from app.storage_dep import get_storage

router = APIRouter(prefix="/admin", tags=["admin"])


def _org_out(org: Organization) -> OrgOut:
    return OrgOut(
        id=org.id,
        name=org.name,
        org_type=org.org_type,
        verification_status=org.verification_status,
        verification_reason=org.verification_reason,
        verified_at=org.verified_at,
    )


@router.get("/verification-queue", response_model=list[OrgOut])
def verification_queue(
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[OrgOut]:
    orgs = db.scalars(
        select(Organization)
        .where(Organization.verification_status == VerificationStatus.PENDING)
        .order_by(Organization.created_at)
    ).all()
    return [_org_out(o) for o in orgs]


@router.post("/organizations/{org_id}/verification", response_model=OrgOut)
def decide_verification(
    org_id: str,
    payload: VerificationDecisionIn,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> OrgOut:
    if payload.decision == VerificationStatus.PENDING:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Decision must be APPROVED or REJECTED")
    if payload.decision == VerificationStatus.REJECTED and not (payload.reason or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A rejection requires a reason")
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if is_member(db, admin, org_id):
        # Reviewers cannot verify an organization they belong to.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review an organization you belong to")
    if org.verification_status != VerificationStatus.PENDING:
        # A decided organization is changed only through a later, explicit workflow, never silently.
        raise HTTPException(status.HTTP_409_CONFLICT, f"Organization is already {org.verification_status.value}")
    previous = org.verification_status.value
    org.verification_status = payload.decision
    org.verification_reason = (payload.reason or "").strip() or None
    org.verified_at = datetime.now(UTC) if payload.decision == VerificationStatus.APPROVED else None
    record_audit(
        db,
        action="org.verification_decided",
        resource_type="organization",
        resource_id=org.id,
        actor_user_id=admin.id,
        org_id=org.id,
        details={"from": previous, "to": payload.decision.value, "decided_at": datetime.now(UTC).isoformat()},
    )
    db.commit()
    return _org_out(org)


@router.get("/organizations/{org_id}/ai-assist", response_model=VerificationAssistOut)
def ai_assist(
    org_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> VerificationAssistOut:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if is_member(db, admin, org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review an organization you belong to")
    profile = db.scalar(select(NgoProfile).where(NgoProfile.org_id == org_id))
    documents = db.scalars(select(Document).where(Document.org_id == org_id).order_by(Document.uploaded_at)).all()
    draft = draft_verification_assist(org, profile, list(documents))
    return VerificationAssistOut(
        org_id=org_id,
        summary=draft.summary,
        flags=draft.flags,
        sources=draft.sources,
        generated_by=draft.generated_by,
    )


def _document_or_404(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("/documents/queue", response_model=list[AdminQueueItemOut])
def document_queue(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminQueueItemOut]:
    rows = db.execute(
        select(Document, Organization.name)
        .join(Organization, Organization.id == Document.org_id)
        .where(Document.review_status == ReviewStatus.PENDING_REVIEW)
        .order_by(Document.uploaded_at)
    ).all()
    # Documents of the reviewer's own organizations are excluded, so the queue never offers a conflicted action.
    return [
        AdminQueueItemOut(
            id=doc.id,
            org_id=doc.org_id,
            org_name=name,
            doc_type=doc.doc_type,
            title=doc.title,
            original_filename=doc.original_filename,
            size_bytes=doc.size_bytes,
            uploaded_at=doc.uploaded_at,
            valid_until_stated=doc.valid_until_stated,
        )
        for doc, name in rows
        if not is_member(db, admin, doc.org_id)
    ]


@router.post("/documents/{doc_id}/decisions", response_model=AdminDecisionOut, status_code=status.HTTP_201_CREATED)
def decide_document(
    doc_id: str,
    payload: ReviewDecisionIn,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> AdminDecisionOut:
    doc = _document_or_404(db, doc_id)
    if is_member(db, admin, doc.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review a document from an organization you belong to")
    previous = doc.review_status
    try:
        new_status = decide(previous, payload.decision, payload.reason)
    except ReviewError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    reason = payload.reason.strip()

    decision = DocumentReviewDecision(
        document_id=doc.id,
        reviewer_user_id=admin.id,
        decision=new_status,
        reason=reason,
        previous_status=previous,
    )
    db.add(decision)
    doc.review_status = new_status
    db.flush()
    record_audit(
        db,
        action="document.review_decided",
        resource_type="document",
        resource_id=doc.id,
        actor_user_id=admin.id,
        org_id=doc.org_id,
        details={"from": previous.value, "to": new_status.value, "decision_id": decision.id},
    )
    db.commit()
    out = _decision_out(decision)
    return AdminDecisionOut(**out.model_dump(), document_id=doc.id, reviewer_user_id=admin.id)


@router.get("/documents/{doc_id}/download")
def admin_download_document(
    doc_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Response:
    doc = _document_or_404(db, doc_id)
    if is_member(db, admin, doc.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot access documents of an organization you belong to")
    content = get_storage().read(doc.storage_key)
    record_audit(
        db,
        action="document.downloaded_by_reviewer",
        resource_type="document",
        resource_id=doc.id,
        actor_user_id=admin.id,
        org_id=doc.org_id,
    )
    db.commit()
    return file_response(content, doc.content_type, doc.original_filename)


@router.get("/documents/{doc_id}/assist", response_model=DocumentAssistOut)
def document_assist(
    doc_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> DocumentAssistOut:
    """Summarise one document for the reviewer, citing the page behind each finding.

    Read-only and advisory. The review decision stays with POST /documents/{id}/decisions.
    Reading a document is still an access of private material, so it is audited exactly
    like a download.
    """
    doc = _document_or_404(db, doc_id)
    if is_member(db, admin, doc.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot access documents of an organization you belong to")

    content = get_storage().read(doc.storage_key)
    draft = draft_document_assist(doc, content)

    record_audit(
        db,
        action="document.assist_viewed_by_reviewer",
        resource_type="document",
        resource_id=doc.id,
        actor_user_id=admin.id,
        org_id=doc.org_id,
        details={"generated_by": draft.generated_by, "findings": len(draft.findings)},
    )
    db.commit()

    return DocumentAssistOut(
        document_id=doc.id,
        org_id=doc.org_id,
        summary=draft.summary,
        findings=[DocumentFindingOut(label=f.label, value=f.value, page=f.page) for f in draft.findings],
        flags=draft.flags,
        sources=draft.sources,
        page_count=draft.page_count,
        text_extractable=draft.text_extractable,
        generated_by=draft.generated_by,
        disclaimer=(
            "Extracted automatically to speed up your reading. It is not a decision and may "
            "miss or misread things. Open the document before you accept or reject it."
        ),
    )


def _pan_submission_or_404(db: Session, submission_id: str) -> PanVerification:
    sub = db.get(PanVerification, submission_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PAN verification submission not found")
    return sub


@router.get("/pan-verifications/queue", response_model=list[AdminPanQueueItemOut])
def pan_verification_queue(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminPanQueueItemOut]:
    rows = db.execute(
        select(PanVerification, User.email, User.full_name)
        .join(User, User.id == PanVerification.user_id)
        .where(PanVerification.review_status == ReviewStatus.PENDING_REVIEW)
        .order_by(PanVerification.uploaded_at)
    ).all()
    # A submission from the reviewer's own account is excluded, so the queue never offers a conflicted action.
    return [
        AdminPanQueueItemOut(
            id=sub.id,
            user_id=sub.user_id,
            user_email=email,
            user_full_name=full_name,
            pan_number=sub.pan_number,
            original_filename=sub.original_filename,
            size_bytes=sub.size_bytes,
            uploaded_at=sub.uploaded_at,
        )
        for sub, email, full_name in rows
        if sub.user_id != admin.id
    ]


@router.post("/pan-verifications/{submission_id}/decisions", response_model=AdminPanDecisionOut, status_code=status.HTTP_201_CREATED)
def decide_pan_verification(
    submission_id: str,
    payload: ReviewDecisionIn,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> AdminPanDecisionOut:
    sub = _pan_submission_or_404(db, submission_id)
    if sub.user_id == admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review your own PAN verification submission")
    previous = sub.review_status
    try:
        new_status = decide(previous, payload.decision, payload.reason)
    except ReviewError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    reason = payload.reason.strip()

    decision = PanVerificationDecision(
        pan_verification_id=sub.id,
        reviewer_user_id=admin.id,
        decision=new_status,
        reason=reason,
        previous_status=previous,
    )
    db.add(decision)
    sub.review_status = new_status
    db.flush()
    record_audit(
        db,
        action="pan_verification.review_decided",
        resource_type="pan_verification",
        resource_id=sub.id,
        actor_user_id=admin.id,
        details={"from": previous.value, "to": new_status.value, "decision_id": decision.id, "subject_user_id": sub.user_id},
    )
    db.commit()
    out = _pan_decision_out(decision)
    return AdminPanDecisionOut(**out.model_dump(), pan_verification_id=sub.id, reviewer_user_id=admin.id)


@router.get("/pan-verifications/{submission_id}/download")
def admin_download_pan_verification(
    submission_id: str,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Response:
    sub = _pan_submission_or_404(db, submission_id)
    if sub.user_id == admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot access your own PAN verification submission")
    content = get_storage().read(sub.storage_key)
    record_audit(
        db,
        action="pan_verification.downloaded_by_reviewer",
        resource_type="pan_verification",
        resource_id=sub.id,
        actor_user_id=admin.id,
        details={"subject_user_id": sub.user_id},
    )
    db.commit()
    return file_response(content, sub.content_type, sub.original_filename)


# ============================================================================
# Phase 4: Admin Analytics & Dashboard
# ============================================================================


@router.get("/analytics/email-engagement", response_model=EmailEngagementOut)
def email_engagement_metrics(
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> EmailEngagementOut:
    """Get email engagement metrics (open rate, click rate, bounce rate)."""
    # Get email statistics
    sent_emails = db.query(SentEmail)
    total_sent = sent_emails.count()

    email_queue = db.query(EmailQueue)
    pending_count = email_queue.filter(EmailQueue.status == "PENDING").count()
    failed_count = email_queue.filter(EmailQueue.status == "FAILED").count()

    if total_sent == 0:
        return EmailEngagementOut(
            total_sent=0, total_pending=pending_count, total_failed=failed_count,
            open_rate=0.0, click_rate=0.0, bounce_rate=0.0, avg_retry_count=0.0, oldest_pending_hours=None
        )

    opened = sent_emails.filter(SentEmail.opened == True).count()
    clicked = sent_emails.filter(SentEmail.clicked == True).count()
    bounced = sent_emails.filter(SentEmail.bounced == True).count()

    # Get oldest pending email age
    oldest_pending = db.query(func.min(EmailQueue.created_at)).filter(
        EmailQueue.status == "PENDING"
    ).scalar()
    oldest_pending_hours = None
    if oldest_pending:
        oldest_pending_hours = int((datetime.now(UTC) - oldest_pending).total_seconds() / 3600)

    avg_retry = db.query(func.avg(EmailQueue.retry_count)).filter(
        EmailQueue.status.in_(["FAILED", "SENT"])
    ).scalar() or 0.0

    return EmailEngagementOut(
        total_sent=total_sent,
        total_pending=pending_count,
        total_failed=failed_count,
        open_rate=round((opened / total_sent * 100), 2) if total_sent > 0 else 0.0,
        click_rate=round((clicked / total_sent * 100), 2) if total_sent > 0 else 0.0,
        bounce_rate=round((bounced / total_sent * 100), 2) if total_sent > 0 else 0.0,
        avg_retry_count=round(float(avg_retry), 2),
        oldest_pending_hours=oldest_pending_hours,
    )


@router.get("/analytics/queue-metrics", response_model=QueueMetricsOut)
def queue_metrics(
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> QueueMetricsOut:
    """Get email queue processing metrics."""
    queue = db.query(EmailQueue)
    pending = queue.filter(EmailQueue.status == "PENDING").count()
    failed = queue.filter(EmailQueue.status == "FAILED").count()

    # Get average processing time (sent vs created)
    sent_emails_query = db.query(EmailQueue).filter(EmailQueue.status == "SENT")
    avg_processing = db.query(
        func.avg(func.extract('epoch', EmailQueue.sent_at - EmailQueue.created_at))
    ).filter(EmailQueue.status == "SENT", EmailQueue.sent_at.isnot(None)).scalar()

    # Get last processed time
    last_sent = db.query(func.max(EmailQueue.sent_at)).filter(
        EmailQueue.status == "SENT"
    ).scalar()

    return QueueMetricsOut(
        queue_depth=pending,
        pending_count=pending,
        failed_count=failed,
        avg_processing_time_seconds=round(float(avg_processing), 2) if avg_processing else None,
        last_processed_at=last_sent,
    )


@router.get("/analytics/fundraising-trends", response_model=list[FundraisingTrendOut])
def fundraising_trends(
    months: int = 12,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[FundraisingTrendOut]:
    """Get fundraising trends over the past N months."""
    results = []

    # Get campaign donations grouped by month
    for i in range(months - 1, -1, -1):
        month_start = datetime.now(UTC) - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        period = month_start.strftime("%Y-%m")

        donations = db.query(CampaignDonation).filter(
            and_(
                CampaignDonation.created_at >= month_start,
                CampaignDonation.created_at < month_end,
                CampaignDonation.status == "COMPLETED"
            )
        ).all()

        total_donations = sum(d.amount for d in donations)
        donation_count = len(donations)
        average_donation = int(total_donations / donation_count) if donation_count > 0 else 0

        campaigns = db.query(Campaign).filter(
            and_(
                Campaign.created_at >= month_start,
                Campaign.created_at < month_end
            )
        ).all()
        active_campaigns = sum(1 for c in campaigns if c.status == "LIVE")

        results.append(FundraisingTrendOut(
            period=period,
            total_donations=total_donations,
            donation_count=donation_count,
            average_donation=average_donation,
            total_campaigns=len(campaigns),
            active_campaigns=active_campaigns,
        ))

    return results


@router.get("/analytics/campaign-performance", response_model=list[CampaignPerformanceOut])
def campaign_performance(
    limit: int = 20,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[CampaignPerformanceOut]:
    """Get top performing campaigns by donations."""
    campaigns = db.query(Campaign).order_by(Campaign.amount_raised.desc()).limit(limit).all()

    results = []
    for campaign in campaigns:
        org = db.get(Organization, campaign.ngo_id)
        conversion_rate = (campaign.donation_count / campaign.view_count * 100) if campaign.view_count > 0 else 0.0

        results.append(CampaignPerformanceOut(
            campaign_id=campaign.id,
            ngo_id=campaign.ngo_id,
            ngo_name=org.name if org else "Unknown",
            title=campaign.title,
            status=campaign.status,
            views=campaign.view_count,
            donation_count=campaign.donation_count,
            amount_raised=campaign.amount_raised,
            conversion_rate=round(conversion_rate, 2),
            created_at=campaign.created_at,
            published_at=campaign.published_at,
        ))

    return results


@router.get("/analytics/ngo-metrics", response_model=list[NgoPerfMetricsOut])
def ngo_performance(
    limit: int = 20,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[NgoPerfMetricsOut]:
    """Get NGO performance metrics (campaigns, fundraising, etc)."""
    orgs = db.query(Organization).filter(Organization.org_type == "NGO").limit(limit).all()

    results = []
    for org in orgs:
        campaigns = db.query(Campaign).filter(Campaign.ngo_id == org.id).all()
        live_campaigns = sum(1 for c in campaigns if c.status == "LIVE")
        total_raised = sum(c.amount_raised for c in campaigns)

        # Get unique donors
        donors = db.query(CampaignDonation).filter(
            CampaignDonation.campaign_id.in_([c.id for c in campaigns])
        ).distinct(CampaignDonation.donor_email).count()

        results.append(NgoPerfMetricsOut(
            ngo_id=org.id,
            org_name=org.name,
            org_type=org.org_type.value,
            campaigns_total=len(campaigns),
            campaigns_live=live_campaigns,
            total_raised=total_raised,
            total_donors=donors,
            verified=org.verification_status == VerificationStatus.APPROVED,
            verified_at=org.verified_at,
        ))

    return results


@router.get("/analytics/dashboard", response_model=AdminDashboardOut)
def admin_dashboard(
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> AdminDashboardOut:
    """Get complete admin dashboard snapshot."""
    # Overall metrics
    total_ngos = db.query(Organization).filter(Organization.org_type == "NGO").count()
    verified_ngos = db.query(Organization).filter(
        and_(Organization.org_type == "NGO", Organization.verification_status == VerificationStatus.APPROVED)
    ).count()

    campaigns = db.query(Campaign).all()
    live_campaigns = sum(1 for c in campaigns if c.status == "LIVE")
    total_fundraising = sum(c.amount_raised for c in campaigns)

    # Unique donors
    donors = db.query(CampaignDonation).distinct(CampaignDonation.donor_email).count()

    # Get sub-metrics
    engagement = email_engagement_metrics(_admin, db)
    queue = queue_metrics(_admin, db)
    top_campaigns = campaign_performance(limit=5, _admin=_admin, db=db)

    # Donor segments (simple grouping by donation amount)
    segments = []
    for segment_name, min_amount, max_amount in [
        ("Small (₹1-1000)", 0, 100000),
        ("Medium (₹1000-5000)", 100000, 500000),
        ("Large (₹5000+)", 500000, 999999999),
    ]:
        segment_donors = db.query(CampaignDonation).filter(
            and_(
                CampaignDonation.amount >= min_amount,
                CampaignDonation.amount <= max_amount,
                CampaignDonation.status == "COMPLETED"
            )
        ).all()

        if segment_donors:
            total_donated = sum(d.amount for d in segment_donors)
            unique_donors = len(set(d.donor_email for d in segment_donors))
            repeat_donors = len([e for e in set(d.donor_email for d in segment_donors) if
                               sum(1 for d in segment_donors if d.donor_email == e) > 1])

            segments.append(DonorSegmentOut(
                segment_name=segment_name,
                donor_count=unique_donors,
                total_donated=total_donated,
                average_donation=int(total_donated / len(segment_donors)) if segment_donors else 0,
                active_donors=unique_donors,
                repeat_donation_rate=round((repeat_donors / unique_donors * 100), 2) if unique_donors > 0 else 0.0,
            ))

    return AdminDashboardOut(
        timestamp=datetime.now(UTC),
        total_ngos=total_ngos,
        verified_ngos=verified_ngos,
        total_campaigns=len(campaigns),
        live_campaigns=live_campaigns,
        total_fundraising=total_fundraising,
        total_donors=donors,
        email_queue_health=queue,
        engagement=engagement,
        top_campaigns=top_campaigns,
        donor_segments=segments,
    )


# ============================================================================
# Admin directories: organisations and projects
# ============================================================================


@router.get("/organizations", response_model=list[AdminOrgRowOut])
def organization_directory(
    org_type: str | None = None,
    verification_status: str | None = None,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminOrgRowOut]:
    """Every organisation on the platform, with the counts a reviewer scans for.

    One endpoint serves both the NGO directory and the donor/CSR directory: the only
    difference is the org_type filter, and duplicating it would mean two places to fix.

    Counts come from grouped aggregates rather than a query per organisation, so the
    cost does not grow with the size of the platform.
    """
    query = select(Organization)
    if org_type:
        query = query.where(Organization.org_type == org_type)
    if verification_status:
        query = query.where(Organization.verification_status == verification_status)
    orgs = db.scalars(query.order_by(Organization.created_at.desc())).all()
    if not orgs:
        return []

    org_ids = [o.id for o in orgs]

    members = dict(
        db.execute(
            select(Membership.org_id, func.count(Membership.id))
            .where(Membership.org_id.in_(org_ids))
            .group_by(Membership.org_id)
        ).all()
    )
    projects = dict(
        db.execute(
            select(Project.org_id, func.count(Project.id))
            .where(Project.org_id.in_(org_ids))
            .group_by(Project.org_id)
        ).all()
    )
    campaign_rows = db.execute(
        select(Campaign.ngo_id, func.count(Campaign.id), func.coalesce(func.sum(Campaign.amount_raised), 0))
        .where(Campaign.ngo_id.in_(org_ids))
        .group_by(Campaign.ngo_id)
    ).all()
    campaigns = {ngo_id: count for ngo_id, count, _ in campaign_rows}
    raised = {ngo_id: total for ngo_id, _, total in campaign_rows}

    return [
        AdminOrgRowOut(
            id=o.id,
            name=o.name,
            org_type=o.org_type.value,
            verification_status=o.verification_status.value,
            verification_reason=o.verification_reason,
            verified_at=o.verified_at,
            created_at=o.created_at,
            member_count=members.get(o.id, 0),
            project_count=projects.get(o.id, 0),
            campaign_count=campaigns.get(o.id, 0),
            total_raised_minor=raised.get(o.id, 0),
        )
        for o in orgs
    ]


@router.get("/individual-donors", response_model=list[AdminIndividualDonorRowOut])
def individual_donor_directory(
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminIndividualDonorRowOut]:
    """Every donor who gives as an individual rather than through an organization.

    An "individual donor" is a user with no organization membership at all - CSR teams
    and NGO staff always belong to one. This is a separate directory from
    /organizations (NGOs and CSR teams) because the two have nothing in common to
    show in one table: a person has no member count or published projects, and an
    organization has no PAN to verify.
    """
    # A donor's own bookkeeping organisation (org_type INDIVIDUAL, created automatically
    # at registration) does not make them an "organisation" for this directory's purposes;
    # only membership in a real NGO or CSR organisation excludes someone from it.
    real_org_member_ids = (
        select(Membership.user_id)
        .join(Organization, Organization.id == Membership.org_id)
        .where(Organization.org_type.in_((OrgType.NGO, OrgType.CSR)))
        .distinct()
    )
    donors = db.scalars(
        select(User)
        .where(User.id.notin_(real_org_member_ids), User.is_platform_admin.is_(False))
        .order_by(User.created_at.desc())
    ).all()
    if not donors:
        return []

    donor_ids = [d.id for d in donors]

    latest_pan_status: dict[str, ReviewStatus] = {}
    for sub in db.scalars(
        select(PanVerification).where(PanVerification.user_id.in_(donor_ids)).order_by(PanVerification.uploaded_at)
    ):
        latest_pan_status[sub.user_id] = sub.review_status  # last write per user wins: ascending order, so most recent

    campaign_donation_rows = db.execute(
        select(
            CampaignDonation.donor_user_id,
            func.count(CampaignDonation.id),
            func.coalesce(func.sum(CampaignDonation.amount), 0),
        )
        .where(CampaignDonation.donor_user_id.in_(donor_ids), CampaignDonation.status == "COMPLETED")
        .group_by(CampaignDonation.donor_user_id)
    ).all()
    payment_rows = db.execute(
        select(
            Payment.donor_user_id,
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount_minor), 0),
        )
        .where(Payment.donor_user_id.in_(donor_ids), Payment.status == "COMPLETED")
        .group_by(Payment.donor_user_id)
    ).all()

    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    ngo_ids_by_donor: dict[str, set[str]] = {}
    for donor_id, count, total in campaign_donation_rows:
        totals[donor_id] = totals.get(donor_id, 0) + int(total)
        counts[donor_id] = counts.get(donor_id, 0) + count
    for donor_id, count, total in payment_rows:
        totals[donor_id] = totals.get(donor_id, 0) + int(total)
        counts[donor_id] = counts.get(donor_id, 0) + count

    # Distinct NGOs supported, counted once across both donation paths (not summed per path).
    ngo_rows = db.execute(
        select(CampaignDonation.donor_user_id, Campaign.ngo_id)
        .join(Campaign, Campaign.id == CampaignDonation.campaign_id)
        .where(CampaignDonation.donor_user_id.in_(donor_ids), CampaignDonation.status == "COMPLETED")
        .union(
            select(Payment.donor_user_id, Campaign.ngo_id)
            .join(Campaign, Campaign.id == Payment.campaign_id)
            .where(Payment.donor_user_id.in_(donor_ids), Payment.status == "COMPLETED")
        )
    ).all()
    for donor_id, ngo_id in ngo_rows:
        ngo_ids_by_donor.setdefault(donor_id, set()).add(ngo_id)

    return [
        AdminIndividualDonorRowOut(
            user_id=d.id,
            email=d.email,
            full_name=d.full_name,
            created_at=d.created_at,
            pan_status=latest_pan_status.get(d.id),
            total_donated_minor=totals.get(d.id, 0),
            donation_count=counts.get(d.id, 0),
            ngo_count=len(ngo_ids_by_donor.get(d.id, ())),
        )
        for d in donors
    ]


@router.get("/payments", response_model=list[AdminPaymentRowOut])
def payment_directory(
    status_filter: str | None = None,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminPaymentRowOut]:
    """Every payment-gateway transaction, across every campaign.

    This is the mock-gateway flow only (see Payment); it does not include direct
    NGO donations or campaign pledges, which are recorded in separate tables.
    """
    query = select(Payment)
    if status_filter:
        query = query.where(Payment.status == status_filter)
    payments = db.scalars(query.order_by(Payment.created_at.desc())).all()
    if not payments:
        return []

    campaign_ids = {p.campaign_id for p in payments}
    campaigns = {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids)))}
    ngo_ids = {c.ngo_id for c in campaigns.values()}
    ngo_names = dict(db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(ngo_ids))).all())

    return [
        AdminPaymentRowOut(
            id=p.id,
            campaign_id=p.campaign_id,
            campaign_title=campaigns[p.campaign_id].title if p.campaign_id in campaigns else None,
            ngo_name=ngo_names.get(campaigns[p.campaign_id].ngo_id) if p.campaign_id in campaigns else None,
            donor_name=p.donor_name,
            donor_email=p.donor_email,
            amount_minor=p.amount_minor,
            currency=p.currency,
            status=p.status,
            is_recurring=p.is_recurring,
            gateway_payment_id=p.gateway_payment_id,
            created_at=p.created_at,
            completed_at=p.completed_at,
        )
        for p in payments
    ]


@router.get("/projects", response_model=list[AdminProjectRowOut])
def project_directory(
    status_filter: str | None = None,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminProjectRowOut]:
    """Every project across every organisation, with its owner and that owner's standing.

    A project from an unverified organisation is the thing an admin most needs to spot,
    so the organisation's verification status travels with each row.
    """
    query = select(Project, Organization).join(Organization, Organization.id == Project.org_id)
    if status_filter:
        query = query.where(Project.status == status_filter)
    rows = db.execute(query.order_by(Project.created_at.desc())).all()

    return [
        AdminProjectRowOut(
            id=p.id,
            title=p.title,
            summary=p.summary,
            status=p.status.value,
            org_id=org.id,
            org_name=org.name,
            org_verification_status=org.verification_status.value,
            campaign_id=p.campaign_id,
            published_at=p.published_at,
            created_at=p.created_at,
        )
        for p, org in rows
    ]


@router.get("/projects/queue", response_model=list[AdminProjectQueueItemOut])
def project_review_queue(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminProjectQueueItemOut]:
    rows = db.execute(
        select(Project, Organization.name)
        .join(Organization, Organization.id == Project.org_id)
        .where(Project.status == ProjectStatus.PENDING_REVIEW)
        .order_by(Project.updated_at)
    ).all()
    # Projects of the reviewer's own organizations are excluded, so the queue never offers a conflicted action.
    return [
        AdminProjectQueueItemOut(id=p.id, org_id=p.org_id, org_name=name, title=p.title, summary=p.summary, created_at=p.created_at)
        for p, name in rows
        if not is_member(db, admin, p.org_id)
    ]


@router.post("/projects/{project_id}/decisions", response_model=ProjectOut)
def decide_project(
    project_id: str,
    payload: ProjectReviewDecisionIn,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if is_member(db, admin, project.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review a project from an organization you belong to")
    if project.status is not ProjectStatus.PENDING_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This project is {project.status.value}, not awaiting review")
    if payload.decision not in ("PUBLISHED", "CHANGES_REQUESTED"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Decision must be PUBLISHED or CHANGES_REQUESTED")
    if payload.decision == "CHANGES_REQUESTED" and not (payload.reason or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Requesting changes requires a reason")

    previous = project.status
    if payload.decision == "PUBLISHED":
        project.status = ProjectStatus.PUBLISHED
        project.published_at = datetime.now(UTC)
        project.review_feedback = None
    else:
        project.status = ProjectStatus.CHANGES_REQUESTED
        project.review_feedback = (payload.reason or "").strip()
    db.flush()
    record_audit(
        db,
        action="project.review_decided",
        resource_type="project",
        resource_id=project.id,
        actor_user_id=admin.id,
        org_id=project.org_id,
        details={"from": previous.value, "to": project.status.value, "reason": payload.reason},
    )
    db.commit()
    return _project_out(project)


@router.get("/proposals/queue", response_model=list[AdminProposalQueueItemOut])
def proposal_review_queue(
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminProposalQueueItemOut]:
    """Proposals awaiting the admin pre-screen, before any CSR can see them."""
    rows = db.execute(
        select(Proposal, Organization.name, Opportunity.title)
        .join(Organization, Organization.id == Proposal.ngo_id)
        .join(Opportunity, Opportunity.id == Proposal.opportunity_id)
        .where(Proposal.status == "SUBMITTED", Proposal.is_current == True)
        .order_by(Proposal.created_at)
    ).all()
    # Proposals from the reviewer's own organizations are excluded, so the queue never offers a conflicted action.
    return [
        AdminProposalQueueItemOut(
            id=p.id,
            proposal_id=p.proposal_id,
            version_num=p.version_num,
            ngo_id=p.ngo_id,
            ngo_name=ngo_name,
            opportunity_id=p.opportunity_id,
            opportunity_title=opp_title,
            budget_requested=p.budget_requested,
            problem_statement=p.problem_statement,
            solution=p.solution,
            created_at=p.created_at,
        )
        for p, ngo_name, opp_title in rows
        if not is_member(db, admin, p.ngo_id)
    ]


@router.post("/proposals/{proposal_id}/decisions", response_model=ProposalOut)
def decide_proposal_admin_review(
    proposal_id: str,
    payload: ProposalAdminDecisionIn,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if is_member(db, admin, proposal.ngo_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review a proposal from an organization you belong to")
    if proposal.status != "SUBMITTED":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This proposal is {proposal.status}, not awaiting admin review")
    if payload.decision not in ("PENDING_CSR", "ADMIN_REJECTED"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Decision must be PENDING_CSR or ADMIN_REJECTED")
    if payload.decision == "ADMIN_REJECTED" and not (payload.reason or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rejecting a proposal requires a reason")

    previous = proposal.status
    proposal.status = payload.decision
    db.flush()

    admin_review = db.scalar(
        select(ApprovalRequest).where(ApprovalRequest.subject_id == proposal.id, ApprovalRequest.subject_type == "PROPOSAL_ADMIN_REVIEW")
    )
    if admin_review:
        admin_review.state = "APPROVED" if payload.decision == "PENDING_CSR" else "REJECTED"
        admin_review.approver_user_id = admin.id
        admin_review.approver_feedback = payload.reason
        admin_review.approved_at = datetime.now(UTC)

    record_audit(
        db,
        action="proposal.admin_review_decided",
        resource_type="proposal",
        resource_id=proposal.id,
        actor_user_id=admin.id,
        org_id=proposal.ngo_id,
        details={"from": previous, "to": proposal.status, "reason": payload.reason},
    )
    db.commit()
    return _proposal_out(proposal)
