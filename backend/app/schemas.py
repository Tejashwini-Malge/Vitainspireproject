from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import DocumentType, OrgType, ProfileStatus, ProjectStatus, ReviewStatus, Role, VerificationStatus


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_platform_admin: bool


class OrgCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    org_type: OrgType


class OrgOut(BaseModel):
    id: str
    name: str
    org_type: OrgType
    verification_status: VerificationStatus
    verification_reason: str | None
    verified_at: datetime | None = None


class MemberAddIn(BaseModel):
    email: EmailStr
    role: Role


class MemberOut(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: Role


class VerificationDecisionIn(BaseModel):
    decision: VerificationStatus
    reason: str | None = Field(default=None, max_length=1000)


class ProfileIn(BaseModel):
    mission: str = Field(min_length=1, max_length=1000)
    about: str | None = Field(default=None, max_length=4000)
    vision: str | None = Field(default=None, max_length=4000)
    description: str | None = Field(default=None, max_length=4000)
    organization_title: str | None = Field(default=None, max_length=300)
    sectors: list[str] = Field(default_factory=list, max_length=10)
    geographies: list[str] = Field(default_factory=list, max_length=10)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    website: str | None = Field(default=None, max_length=300)
    registration_number: str | None = Field(default=None, max_length=100)
    section_80g_number: str | None = Field(default=None, max_length=100)

    @field_validator("sectors", "geographies")
    @classmethod
    def _clean_list(cls, values: list[str], info) -> list[str]:
        cleaned = [v.strip() for v in values if v.strip()]
        if any(len(v) > 80 for v in cleaned):
            raise ValueError(f"Each entry in {info.field_name} must be 80 characters or fewer")
        return cleaned

    @field_validator("website")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        value = value.strip()
        if not value.startswith("https://") or " " in value or len(value) < 12:
            raise ValueError("Website must be a full https:// address")
        return value

    @field_validator("mission")
    @classmethod
    def _strip_mission(cls, value: str) -> str:
        return value.strip()

    @field_validator("about", "registration_number", "section_80g_number")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ProfileOut(BaseModel):
    org_id: str
    status: ProfileStatus
    mission: str
    about: str | None
    vision: str | None
    description: str | None
    organization_title: str | None
    sectors: list[str]
    geographies: list[str]
    founded_year: int | None
    website: str | None
    registration_number: str | None
    section_80g_number: str | None
    published_at: datetime | None
    updated_at: datetime


class ReviewedDocumentOut(BaseModel):
    doc_type: DocumentType
    reviewed_at: datetime


class PublicNgoOut(BaseModel):
    """Only fields the organization chose to publish, plus verification facts. No private documents."""

    id: str
    name: str
    verified_at: datetime | None
    profile: ProfileOut
    reviewed_documents: list[ReviewedDocumentOut]
    disclaimer: str


class DecisionOut(BaseModel):
    id: str
    decision: ReviewStatus
    reason: str
    previous_status: ReviewStatus
    decided_at: datetime


class AdminDecisionOut(DecisionOut):
    document_id: str
    reviewer_user_id: str


class DocumentOut(BaseModel):
    id: str
    org_id: str
    doc_type: DocumentType
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    valid_until_stated: date | None
    review_status: ReviewStatus
    uploaded_at: datetime
    latest_decision: DecisionOut | None


class AdminQueueItemOut(BaseModel):
    id: str
    org_id: str
    org_name: str
    doc_type: DocumentType
    title: str
    original_filename: str
    size_bytes: int
    uploaded_at: datetime
    valid_until_stated: date | None


class ReviewDecisionIn(BaseModel):
    decision: ReviewStatus
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("A reason is required for every review decision")
        return stripped


class PanVerificationOut(BaseModel):
    id: str
    user_id: str
    pan_number: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    review_status: ReviewStatus
    uploaded_at: datetime
    latest_decision: DecisionOut | None


class AdminPanQueueItemOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_full_name: str
    pan_number: str
    original_filename: str
    size_bytes: int
    uploaded_at: datetime


class AdminPanDecisionOut(DecisionOut):
    pan_verification_id: str
    reviewer_user_id: str


class PanVerificationStatusOut(BaseModel):
    verified: bool
    status: ReviewStatus | None
    pan_number: str | None


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    # Budget, beneficiaries, impact and milestones belong to the funding campaign.
    # A project references one instead of restating it.
    campaign_id: str | None = Field(default=None, max_length=36)

    @field_validator("title", "summary", "description")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ProjectOut(BaseModel):
    id: str
    org_id: str
    title: str
    summary: str
    description: str | None
    campaign_id: str | None
    status: ProjectStatus
    review_feedback: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminProjectQueueItemOut(BaseModel):
    """One project awaiting admin review."""

    id: str
    org_id: str
    org_name: str
    title: str
    summary: str
    created_at: datetime


class ProjectReviewDecisionIn(BaseModel):
    decision: str  # PUBLISHED or CHANGES_REQUESTED
    reason: str | None = Field(default=None, max_length=2000)


class AdminProposalQueueItemOut(BaseModel):
    """One proposal awaiting the admin pre-screen, before a CSR ever sees it."""

    id: str
    proposal_id: str
    version_num: int
    ngo_id: str
    ngo_name: str
    opportunity_id: str
    opportunity_title: str
    budget_requested: int
    problem_statement: str
    solution: str
    created_at: datetime


class ProposalAdminDecisionIn(BaseModel):
    decision: str  # PENDING_CSR (cleared to the CSR) or ADMIN_REJECTED
    reason: str | None = Field(default=None, max_length=2000)


class PublicProjectOut(BaseModel):
    id: str
    org_id: str
    org_name: str
    org_sectors: list[str]
    title: str
    summary: str
    description: str | None
    published_at: datetime | None


class FeedItemOut(BaseModel):
    """One card in the discovery feed -- a LIVE campaign or a PUBLISHED standalone project."""

    kind: str  # "campaign" | "project"
    id: str
    org_id: str
    org_name: str
    org_sectors: list[str]
    org_geographies: list[str]
    title: str
    summary: str
    hero_image_url: str | None = None
    budget_total: int | None = None
    amount_raised: int | None = None
    published_at: datetime | None
    score: int
    distance_km: float | None = None
    lat: float | None = None
    lon: float | None = None


class GeocodeOut(BaseModel):
    query: str
    lat: float
    lon: float
    display_name: str


class BillingAddressIn(BaseModel):
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=1, max_length=100)

    @field_validator("line1", "line2", "city", "state", "postal_code", "country")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class DonationIn(BaseModel):
    donor_name: str = Field(min_length=1, max_length=200)
    donor_email: EmailStr
    billing_address: BillingAddressIn
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, description="Amount in whole currency units, e.g. rupees")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    project_id: str | None = Field(default=None)
    message: str | None = Field(default=None, max_length=500)

    @field_validator("donor_name", "message")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()


class DonationOut(BaseModel):
    id: str
    org_id: str
    project_id: str | None
    donor_name: str
    donor_email: str
    billing_address: BillingAddressIn
    amount_minor: int
    currency: str
    message: str | None
    created_at: datetime


class VerificationAssistOut(BaseModel):
    """An AI-drafted proposal for the reviewer. Never a decision; the admin still approves or rejects."""

    org_id: str
    summary: str
    flags: list[str]
    sources: list[str]
    generated_by: str
    disclaimer: str = "AI-drafted proposal. Verify against the source documents before deciding."


class OpportunityIn(BaseModel):
    title: str = Field(min_length=5, max_length=300)
    description: str = Field(min_length=10, max_length=5000)
    sectors: list[str] = Field(default_factory=list, max_length=10)
    geographies: list[str] = Field(default_factory=list, max_length=10)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    deadline: date
    requirements_text: str = Field(min_length=10)


class OpportunityOut(BaseModel):
    id: str
    org_id: str
    title: str
    description: str
    sectors: list[str]
    geographies: list[str]
    budget_min: int | None
    budget_max: int | None
    deadline: date
    requirements_text: str
    status: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FitScoreOut(BaseModel):
    ngo_id: str
    ngo_name: str
    sectors: list[str]
    score: int
    explanation: str
    confidence: str


class ShortlistIn(BaseModel):
    opportunity_id: str
    ngo_ids: list[str] = Field(min_length=1)


class ShortlistedOpportunityOut(BaseModel):
    """An opportunity the caller's NGO has been shortlisted for, with where it stands."""

    opportunity: OpportunityOut
    csr_org_id: str
    csr_org_name: str
    shortlisted_at: datetime
    proposal_id: str | None = None
    proposal_status: str | None = None
    can_submit_proposal: bool
    blockers: list[str] = Field(default_factory=list)


class ShortlistOut(BaseModel):
    id: str
    shortlist_id: str
    opportunity_id: str
    revision_num: int
    ngo_ids: list[str]
    is_current: bool
    selected_by_user_id: str
    selected_at: datetime


class ProposalIn(BaseModel):
    opportunity_id: str
    problem_statement: str = Field(min_length=10, max_length=2000)
    solution: str = Field(min_length=10, max_length=2000)
    budget_requested: int = Field(gt=0)
    timeline: str = Field(min_length=5, max_length=500)
    expected_outcomes: str = Field(min_length=10, max_length=1000)


class ProposalOut(BaseModel):
    id: str
    proposal_id: str
    opportunity_id: str
    ngo_id: str
    version_num: int
    is_current: bool
    problem_statement: str
    solution: str
    budget_requested: int
    timeline: str
    expected_outcomes: str
    status: str
    created_at: datetime
    updated_at: datetime


class ApprovalRequestIn(BaseModel):
    decision: str  # APPROVED, REJECTED, CHANGES_REQUESTED
    feedback: str | None = Field(default=None, max_length=1000)
    # The CSR's approve/request-changes screens post this spelling; accept both rather
    # than silently dropping the reviewer's words.
    approver_feedback: str | None = Field(default=None, max_length=1000)

    @property
    def feedback_text(self) -> str | None:
        return self.feedback or self.approver_feedback


class ProposalApprovalIn(BaseModel):
    """What the CSR approves, which after a negotiation may differ from what was asked.

    `amount_minor` is the committed amount in integer minor units. Omit it to commit the
    full requested budget.
    """

    decision: str | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    approver_feedback: str | None = Field(default=None, max_length=1000)


class DeliveryMilestoneIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=2000)
    target_date: date
    amount_minor: int = Field(default=0, ge=0)


class DeliveryMilestoneSetIn(BaseModel):
    """The NGO's full milestone plan. Replaces any plan not yet under way."""

    milestones: list[DeliveryMilestoneIn] = Field(min_length=1, max_length=50)


class DeliveryMilestoneUpdateIn(BaseModel):
    status: str | None = None  # IN_PROGRESS, COMPLETED
    evidence_url: str | None = Field(default=None, max_length=600)


class DeliveryMilestoneOut(BaseModel):
    id: str
    proposal_id: str
    commitment_id: str
    ngo_id: str
    opportunity_id: str
    sequence_num: int
    title: str
    description: str
    target_date: date
    amount_minor: int
    status: str
    evidence_url: str | None
    completed_at: datetime | None
    verified_at: datetime | None
    verified_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class DeliveryProgressOut(BaseModel):
    """Roll-up the CSR sees for an approved proposal."""

    proposal_id: str
    committed_amount_minor: int
    milestone_count: int
    completed_count: int
    verified_count: int
    percent_verified: int
    next_due: DeliveryMilestoneOut | None = None
    overdue_count: int
    milestones: list[DeliveryMilestoneOut]


class FinanceLedgerOut(BaseModel):
    id: str
    opportunity_id: str
    ngo_id: str
    amount_minor: int
    transaction_type: str
    recorded_at: datetime


class WebsiteExtractIn(BaseModel):
    website_url: str


class WebsiteExtractOut(BaseModel):
    """Extracted data from a website."""
    title: str | None = None
    description: str | None = None
    about: str | None = None
    mission: str | None = None
    mission_statements: list[str] = []
    vision: str | None = None
    founded_year: int | None = None
    sectors: list[str] = []


class ProposalMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class ProposalMessageOut(BaseModel):
    id: str
    proposal_id: str
    sender_id: str
    sender_type: str
    content: str
    created_at: datetime
    read_at: datetime | None = None


class ProposalTimelineOut(BaseModel):
    proposal_id: str
    last_activity_at: datetime
    reply_deadline: datetime | None = None
    waiting_on: str | None = None
    days_since_activity: int
    is_overdue: bool


class ProposalEscalationOut(BaseModel):
    id: str
    proposal_id: str
    reason: str
    escalated_at: datetime
    admin_notes: str | None = None
    status: str
    resolved_at: datetime | None = None


class NotificationOut(BaseModel):
    id: str
    recipient_user_id: str
    # Null on a SHORTLISTED notification, which precedes any proposal.
    proposal_id: str | None = None
    opportunity_id: str | None = None
    notification_type: str
    title: str
    message: str
    actor_user_id: str | None = None
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class NotificationSummaryOut(BaseModel):
    unread_count: int
    total_count: int
    recent_notifications: list[NotificationOut]


class CampaignMilestoneIn(BaseModel):
    title: str = Field(min_length=5, max_length=300)
    description: str = Field(min_length=10, max_length=2000)
    target_date: date
    target_amount: int = Field(gt=0)


class CampaignMilestoneOut(BaseModel):
    id: str
    sequence_num: int
    title: str
    description: str
    target_date: date
    target_amount: int
    status: str
    completed_at: datetime | None = None
    evidence_url: str | None = None


class DonationTypeIn(BaseModel):
    type: str = Field(min_length=3, max_length=30)
    label: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=1000)
    quantity_unit: str | None = Field(default=None, max_length=50)
    value_in_rupees: int = Field(gt=0)


class DonationTypeOut(BaseModel):
    id: str
    type: str
    label: str
    description: str
    quantity_unit: str | None = None
    value_in_rupees: int
    is_available: bool


class CampaignIn(BaseModel):
    title: str = Field(min_length=10, max_length=300)
    description: str = Field(min_length=50, max_length=5000)
    mission: str = Field(min_length=5, max_length=500)
    beneficiary_count: int | None = Field(default=None, ge=1)
    beneficiary_description: str = Field(min_length=20, max_length=2000)
    impact_statement: str = Field(min_length=20, max_length=2000)
    budget_total: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    budget_breakdown: dict | None = None
    duration_months: int = Field(gt=0, le=60)
    hero_image_url: str | None = Field(default=None, max_length=500)

    @field_validator("budget_breakdown")
    @classmethod
    def _validate_breakdown(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("budget_breakdown must be a dictionary")
        return v


class CampaignOut(BaseModel):
    id: str
    ngo_id: str
    ngo_name: str
    ngo_sectors: list[str]
    ngo_geographies: list[str]
    title: str
    description: str
    mission: str
    beneficiary_count: int | None = None
    beneficiary_description: str
    impact_statement: str
    budget_total: int
    currency: str
    budget_breakdown: dict | None = None
    duration_months: int
    status: str
    hero_image_url: str | None = None
    images: list[str]
    view_count: int
    donation_count: int
    amount_raised: int
    verification_status: str
    verified_at: datetime | None = None
    rejection_reason: str | None = None
    admin_notes: str | None = None
    created_at: datetime
    published_at: datetime | None = None


class CampaignReviewOut(BaseModel):
    id: str
    campaign_id: str
    ai_review_at: datetime | None = None
    ai_recommendation: str | None = None
    trustworthiness_score: int | None = None
    ai_flags: list[str]
    ai_analysis: dict | None = None
    admin_decision: str | None = None
    admin_notes: str | None = None
    admin_changes_requested: str | None = None


class CampaignApprovalIn(BaseModel):
    decision: str  # APPROVED, REJECTED, NEEDS_CHANGES
    reason: str | None = Field(default=None, max_length=2000)


class CampaignDonationIn(BaseModel):
    donation_type_id: str
    donor_name: str = Field(min_length=2, max_length=200)
    donor_email: EmailStr
    amount: int = Field(gt=0)
    message: str | None = Field(default=None, max_length=500)
    is_anonymous: bool = False


class CampaignDonationOut(BaseModel):
    id: str
    campaign_id: str
    donor_name: str
    donor_email: str
    amount: int
    currency: str
    message: str | None = None
    is_anonymous: bool
    status: str
    created_at: datetime
    completed_at: datetime | None = None


# ============================================================================
# Phase 3: Email Notifications & Preferences
# ============================================================================


class NotificationPreferencesIn(BaseModel):
    """User preferences for email notifications."""
    donation_received: str = Field(default="INSTANT", pattern="^(INSTANT|DAILY|WEEKLY|NEVER)$")
    milestone_reached: str = Field(default="INSTANT", pattern="^(INSTANT|DAILY|WEEKLY|NEVER)$")
    campaign_published: str = Field(default="INSTANT", pattern="^(INSTANT|DAILY|WEEKLY|NEVER)$")
    ngo_verified: str = Field(default="INSTANT", pattern="^(INSTANT|DAILY|WEEKLY|NEVER)$")
    donor_digest: str = Field(default="WEEKLY", pattern="^(INSTANT|DAILY|WEEKLY|NEVER)$")
    marketing_emails: bool = Field(default=False)


class NotificationPreferencesOut(BaseModel):
    """User's current notification preferences."""
    id: str
    user_id: str
    donation_received: str
    milestone_reached: str
    campaign_published: str
    ngo_verified: str
    donor_digest: str
    marketing_emails: bool
    unsubscribed_at: datetime | None
    updated_at: datetime


class EmailQueueItemOut(BaseModel):
    """Email in queue for sending."""
    id: str
    recipient_email: str
    event_type: str
    subject: str
    status: str
    retry_count: int
    created_at: datetime
    sent_at: datetime | None


class SentEmailOut(BaseModel):
    """Record of a sent email."""
    id: str
    recipient_email: str
    event_type: str
    subject: str
    sent_at: datetime
    opened: bool
    bounced: bool


class UnsubscribeIn(BaseModel):
    """Request to unsubscribe from emails."""
    token: str = Field(min_length=50, max_length=100)


# ============================================================================
# Phase 4: Admin Analytics & Dashboard
# ============================================================================


class FundraisingTrendOut(BaseModel):
    """Fundraising metrics over time."""
    period: str  # e.g., "2024-10"
    total_donations: int
    donation_count: int
    average_donation: int
    total_campaigns: int
    active_campaigns: int


class CampaignPerformanceOut(BaseModel):
    """Individual campaign performance metrics."""
    campaign_id: str
    ngo_id: str
    ngo_name: str
    title: str
    status: str
    views: int
    donation_count: int
    amount_raised: int
    conversion_rate: float
    created_at: datetime
    published_at: datetime | None


class EmailEngagementOut(BaseModel):
    """Email engagement and queue metrics."""
    total_sent: int
    total_pending: int
    total_failed: int
    open_rate: float
    click_rate: float
    bounce_rate: float
    avg_retry_count: float
    oldest_pending_hours: int | None


class QueueMetricsOut(BaseModel):
    """Email queue processing metrics."""
    queue_depth: int
    pending_count: int
    failed_count: int
    avg_processing_time_seconds: float | None
    last_processed_at: datetime | None


class NgoPerfMetricsOut(BaseModel):
    """NGO performance summary."""
    ngo_id: str
    org_name: str
    org_type: str
    campaigns_total: int
    campaigns_live: int
    total_raised: int
    total_donors: int
    verified: bool
    verified_at: datetime | None


class DonorSegmentOut(BaseModel):
    """Donor segmentation analytics."""
    segment_name: str
    donor_count: int
    total_donated: int
    average_donation: int
    active_donors: int
    repeat_donation_rate: float


class AdminDashboardOut(BaseModel):
    """Complete admin dashboard snapshot."""
    timestamp: datetime
    total_ngos: int
    verified_ngos: int
    total_campaigns: int
    live_campaigns: int
    total_fundraising: int
    total_donors: int
    email_queue_health: QueueMetricsOut
    engagement: EmailEngagementOut
    top_campaigns: list[CampaignPerformanceOut]
    donor_segments: list[DonorSegmentOut]


# ============================================================================
# Phase 5: Payment & Recurring Donations
# ============================================================================


class PaymentInitiateIn(BaseModel):
    """Request to initiate a payment for a donation."""
    campaign_id: str
    donor_name: str
    donor_email: EmailStr
    amount_minor: int = Field(gt=0)  # Amount in paise
    is_recurring: bool = Field(default=False)
    recurring_frequency: str | None = Field(default=None, pattern="^(MONTHLY|QUARTERLY|YEARLY)$")


class PaymentInitiateOut(BaseModel):
    """Response with payment details for frontend."""
    payment_id: str
    order_id: str
    amount_minor: int
    currency: str
    customer_name: str
    customer_email: str
    key_id: str  # Razorpay key for frontend


class PaymentVerifyIn(BaseModel):
    """Verify payment signature from Razorpay."""
    payment_id: str
    order_id: str
    signature: str


class PaymentOut(BaseModel):
    """Payment record details."""
    id: str
    campaign_id: str
    donor_name: str
    donor_email: str
    amount_minor: int
    currency: str
    status: str
    payment_method: str
    gateway_order_id: str | None
    gateway_payment_id: str | None
    is_recurring: bool
    created_at: datetime
    completed_at: datetime | None


class RecurringDonationIn(BaseModel):
    """Create a recurring donation."""
    campaign_id: str
    donor_name: str
    donor_email: EmailStr
    amount_minor: int = Field(gt=0)
    frequency: str = Field(pattern="^(MONTHLY|QUARTERLY|YEARLY)$")


class RecurringDonationOut(BaseModel):
    """Recurring donation record."""
    id: str
    campaign_id: str
    donor_name: str
    donor_email: str
    amount_minor: int
    currency: str
    frequency: str
    status: str
    next_billing_date: str
    total_payments: int
    total_amount_paid: int
    created_at: datetime


class PaymentWebhookIn(BaseModel):
    """Razorpay webhook payload for payment events."""
    event: str
    payload: dict = Field(default_factory=dict)


class TaxReceiptOut(BaseModel):
    """Tax receipt details (80G compliant)."""
    id: str
    receipt_number: str
    donor_name: str
    donor_email: str
    amount_minor: int
    currency: str
    donor_pan: str | None = None
    ngo_name: str
    ngo_80g_number: str | None
    # An 80G receipt is only usable for a deduction if it identifies the registered entity.
    ngo_registration_number: str | None = None
    receipt_date: str
    pdf_url: str | None
    email_sent_at: str | None
    created_at: str


class TaxReceiptGenerateIn(BaseModel):
    """Request to generate tax receipt."""
    payment_id: str
    donor_pan: str | None = Field(default=None, max_length=20)


class SocialShareIn(BaseModel):
    """Request to generate social share link."""
    campaign_id: str
    platform: str = Field(pattern="^(WHATSAPP|TWITTER|LINKEDIN|EMAIL|FACEBOOK)$")
    donor_name: str | None = Field(default=None, max_length=200)
    donation_amount: int | None = Field(default=None, gt=0)


class SocialShareOut(BaseModel):
    """Social share link response."""
    platform: str
    share_url: str
    preview_text: str


class SuggestedField(BaseModel):
    """One pre-filled value, with enough context for a human to accept or rewrite it."""

    value: str
    source_url: str
    # Campaign fields carry minimum lengths. Telling the NGO up front which suggestions
    # are too short avoids a 422 wall after they have already filled the rest in.
    meets_minimum: bool
    minimum_length: int


class CampaignSuggestionOut(BaseModel):
    """A draft proposed from the organisation's own website. Nothing is saved.

    Fields the extractor could not find are listed in needs_your_input rather than
    invented, so no text is presented as the NGO's words unless it came from their site.
    """

    source_url: str
    fetched_at: datetime
    title: SuggestedField | None = None
    description: SuggestedField | None = None
    mission: SuggestedField | None = None
    needs_your_input: list[str] = []
    disclaimer: str


class DocumentFindingOut(BaseModel):
    """One extracted fact and the page it was found on."""

    label: str
    value: str
    page: int


class DocumentAssistOut(BaseModel):
    """A reviewer-facing draft for one document. Decides nothing; cites everything."""

    document_id: str
    org_id: str
    summary: str
    findings: list[DocumentFindingOut]
    flags: list[str]
    sources: list[str]
    page_count: int
    text_extractable: bool
    generated_by: str
    disclaimer: str


class InboxThreadOut(BaseModel):
    """One conversation, summarised for a list view.

    Covers every channel: proposal threads between an NGO and a funder, and direct
    threads with platform staff. `kind` says which, and the id fields that do not
    apply to that kind are null.
    """

    thread_id: str
    kind: str  # "PROPOSAL", "ADMIN_ORG" or "DONOR_ADMIN"
    title: str
    counterparty_name: str
    my_side: str  # "NGO", "CSR", "ORG", "DONOR" or "ADMIN"
    status: str
    total_messages: int
    unread_count: int
    last_message_preview: str | None
    last_message_at: datetime | None
    last_sender_side: str | None
    # Set only for the kind they belong to, so a client can build the right link.
    proposal_id: str | None = None
    opportunity_id: str | None = None
    conversation_id: str | None = None


class ConversationOpenIn(BaseModel):
    """Start a direct thread.

    org_id is set when a platform admin opens a thread with an organisation; an
    organisation member or a donor reaching staff omits both org_id and
    target_org_id (the counterparty is staff, implicitly). target_org_id is set
    instead when the counterparty is a specific organisation rather than staff: an
    NGO or CSR member reaching another organisation directly, or a donor reaching a
    specific NGO. Exactly one of org_id / target_org_id may be set.
    """

    subject: str = Field(min_length=3, max_length=300)
    message: str = Field(min_length=1, max_length=5000)
    org_id: str | None = Field(default=None, max_length=36)
    target_org_id: str | None = Field(default=None, max_length=36)


class ConversationMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class ConversationMessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: str
    sender_side: str
    content: str
    created_at: datetime
    read_at: datetime | None


class ConversationOut(BaseModel):
    id: str
    kind: str
    subject: str
    org_id: str | None
    counterparty_org_id: str | None
    donor_user_id: str | None
    status: str
    created_at: datetime
    closed_at: datetime | None
    my_side: str


class AdminOrgRowOut(BaseModel):
    """One organisation in the admin directory, with the counts a reviewer scans for."""

    id: str
    name: str
    org_type: str
    verification_status: str
    verification_reason: str | None
    verified_at: datetime | None
    created_at: datetime
    member_count: int
    project_count: int
    campaign_count: int
    total_raised_minor: int


class AdminProjectRowOut(BaseModel):
    """One project in the admin directory, with the organisation it belongs to."""

    id: str
    title: str
    summary: str
    status: str
    org_id: str
    org_name: str
    org_verification_status: str
    campaign_id: str | None
    published_at: datetime | None
    created_at: datetime


class AdminIndividualDonorRowOut(BaseModel):
    """One individual donor (a user who belongs to no organization) in the admin directory."""

    user_id: str
    email: str
    full_name: str
    created_at: datetime
    pan_status: ReviewStatus | None
    total_donated_minor: int
    donation_count: int
    ngo_count: int


class AdminPaymentRowOut(BaseModel):
    """One payment-gateway transaction (the mock-Razorpay flow), for the admin payments view."""

    id: str
    campaign_id: str
    campaign_title: str | None
    ngo_name: str | None
    donor_name: str
    donor_email: str
    amount_minor: int
    currency: str
    status: str
    is_recurring: bool
    gateway_payment_id: str | None
    created_at: datetime
    completed_at: datetime | None


class OnboardingStepOut(BaseModel):
    key: str
    label: str
    done: bool
    cta_href: str


class OnboardingStatusOut(BaseModel):
    org_type: str
    steps: list[OnboardingStepOut]
    next_step: OnboardingStepOut | None
    completion_pct: int
