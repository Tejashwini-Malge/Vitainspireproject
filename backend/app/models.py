import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class OrgType(str, enum.Enum):
    NGO = "NGO"
    CSR = "CSR"
    INDIVIDUAL = "INDIVIDUAL"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Role(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    # Platform staff only. Granted in the database by an operator, never through the API.
    is_platform_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    org_type: Mapped[OrgType] = mapped_column(Enum(OrgType, name="org_type"))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"), default=VerificationStatus.PENDING
    )
    verification_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_membership_org_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    """Append-only. Written in the same transaction as the action it records."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(36))
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ProfileStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class DocumentType(str, enum.Enum):
    PAN = "PAN"
    REGISTRATION = "REGISTRATION"
    SECTION_12A = "SECTION_12A"
    SECTION_80G = "SECTION_80G"
    FCRA = "FCRA"
    OTHER = "OTHER"


class ReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class NgoProfile(Base):
    """Organization-provided content. Self-described until a public profile is published."""

    __tablename__ = "ngo_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True)
    mission: Mapped[str] = mapped_column(String(1000), default="")
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sectors: Mapped[list] = mapped_column(JSON, default=list)
    geographies: Mapped[list] = mapped_column(JSON, default=list)
    # Each entry in `geographies`, geocoded: [{"query": str, "lat": float, "lon": float}, ...].
    # An entry that failed to geocode is simply absent here, not a blocker to saving the profile.
    geography_points: Mapped[list] = mapped_column(JSON, default=list)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Self-declared by the NGO. Printed on a donor's 80G tax certificate as "as stated";
    # admin verifies the underlying SECTION_80G/REGISTRATION documents separately, not this text.
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section_80g_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ProfileStatus] = mapped_column(Enum(ProfileStatus, name="profile_status"), default=ProfileStatus.DRAFT)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """Private compliance document. The file never leaves storage except through an authorized download."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("storage_key", name="uq_documents_storage_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, name="document_type"))
    title: Mapped[str] = mapped_column(String(200))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(64))
    # Self-declared by the uploader. Shown as "as stated", never as verified.
    valid_until_stated: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), default=ReviewStatus.PENDING_REVIEW
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentReviewDecision(Base):
    """Immutable review history. Rows are never updated or deleted (enforced by a database trigger)."""

    __tablename__ = "document_review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, name="review_decision"))
    reason: Mapped[str] = mapped_column(Text)
    previous_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, name="review_status", create_type=False))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PanVerification(Base):
    """A user's self-uploaded PAN proof, pending admin review.

    Scoped to the user, not an organization: individual donors have no org to hang a
    compliance document off of, and a CSR member's own identity is distinct from their
    org's compliance documents (see Document above). A rejected submission is corrected
    by uploading again, not by editing this row, so multiple rows per user are expected.
    """

    __tablename__ = "pan_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # Self-declared by the uploader. Shown as "as stated", confirmed only once APPROVED.
    pan_number: Mapped[str] = mapped_column(String(10))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status", create_type=False), default=ReviewStatus.PENDING_REVIEW
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("storage_key", name="uq_pan_verifications_storage_key"),)


class PanVerificationDecision(Base):
    """Immutable review history for PAN verification. Rows are never updated or deleted (enforced by a database trigger)."""

    __tablename__ = "pan_verification_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pan_verification_id: Mapped[str] = mapped_column(ForeignKey("pan_verifications.id"), index=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, name="review_decision", create_type=False))
    reason: Mapped[str] = mapped_column(Text)
    previous_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus, name="review_status", create_type=False))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ProjectStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    PUBLISHED = "PUBLISHED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class Project(Base):
    """An NGO's fundable project. Shown in the public feed only once PUBLISHED.

    Going live requires an explicit admin approval (submit-for-review -> approve),
    not just org-level verification: an admin-verified NGO can still submit a project
    that is not yet fit to publish.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The campaign that funds this project. Budget, budget breakdown, beneficiaries,
    # impact statement, duration and milestones live on Campaign, not here, so that
    # detail has one home rather than two diverging copies.
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    # Not a native Postgres enum (native_enum=False): a plain, extensible string column,
    # consistent with how Campaign.status is modelled.
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False, length=20), default=ProjectStatus.DRAFT
    )
    # The admin's note on a CHANGES_REQUESTED decision. Shown to the NGO; cleared on the next submission.
    review_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Donation(Base):
    """A single donation. Append-only (enforced by a database trigger); no balances are computed here."""

    __tablename__ = "donations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    # Set only when the donor was signed in at the time of donation. Never inferred from email.
    donor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    donor_name: Mapped[str] = mapped_column(String(200))
    donor_email: Mapped[str] = mapped_column(String(320))
    billing_address: Mapped[dict] = mapped_column(JSON)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Opportunity(Base):
    """CSR funding RFP."""

    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    sectors: Mapped[list] = mapped_column(JSON, default=list)
    geographies: Mapped[list] = mapped_column(JSON, default=list)
    budget_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline: Mapped[date] = mapped_column(Date)
    requirements_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EligibilityRule(Base):
    """Deterministic business logic for eligibility."""

    __tablename__ = "eligibility_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    rule_type: Mapped[str] = mapped_column(String(50))
    condition_json: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EligibilityResult(Base):
    """Output of eligibility check."""

    __tablename__ = "eligibility_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    ngo_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    passed: Mapped[bool] = mapped_column(default=False)
    rule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FitScore(Base):
    """AI-generated fit ranking."""

    __tablename__ = "fit_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    ngo_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(20))
    model_version: Mapped[str] = mapped_column(String(50))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Shortlist(Base):
    """CSR's shortlist selection (versioned with revisions)."""

    __tablename__ = "shortlists"
    __table_args__ = (UniqueConstraint("opportunity_id", "revision_num", name="uq_shortlist_opportunity_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shortlist_id: Mapped[str] = mapped_column(String(36), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    revision_num: Mapped[int] = mapped_column(Integer, default=1)
    ngo_ids: Mapped[list] = mapped_column(JSON)
    is_current: Mapped[bool] = mapped_column(default=True)
    selected_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Proposal(Base):
    """NGO proposal (versioned)."""

    __tablename__ = "proposals"
    __table_args__ = (UniqueConstraint("proposal_id", "version_num", name="uq_proposal_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(String(36), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    ngo_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(default=True)
    problem_statement: Mapped[str] = mapped_column(Text)
    solution: Mapped[str] = mapped_column(Text)
    budget_requested: Mapped[int] = mapped_column(Integer)
    timeline: Mapped[str] = mapped_column(String(500))
    expected_outcomes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalRequest(Base):
    """Generic approval state machine."""

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_type: Mapped[str] = mapped_column(String(50))
    subject_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(20))
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Commitment(Base):
    """Intent to fund (before ledger entry)."""

    __tablename__ = "commitments"
    __table_args__ = (UniqueConstraint("proposal_id", name="uq_commitment_proposal_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FinanceLedger(Base):
    """Append-only ledger of confirmed financial transactions."""

    __tablename__ = "finance_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    ngo_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    recorded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MatchingJob(Base):
    """Background job for async matching."""

    __tablename__ = "matching_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    fit_scores_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProposalMessage(Base):
    """Async two-way messaging between CSR and NGO on a proposal."""

    __tablename__ = "proposal_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProposalTimeline(Base):
    """Tracks activity and deadlines on a proposal."""

    __tablename__ = "proposal_timelines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reply_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waiting_on: Mapped[str | None] = mapped_column(String(10), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProposalEscalation(Base):
    """Tracks escalations when no reply for extended period."""

    __tablename__ = "proposal_escalations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    reason: Mapped[str] = mapped_column(String(100))
    escalated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    """Notifications for proposal messages and status changes."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    notification_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Campaign(Base):
    """NGO fundraising campaign. Requires admin approval before going LIVE."""

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ngo_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    mission: Mapped[str] = mapped_column(String(500))
    beneficiary_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beneficiary_description: Mapped[str] = mapped_column(Text)
    impact_statement: Mapped[str] = mapped_column(Text)
    budget_total: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    budget_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_months: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    hero_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    images: Mapped[list] = mapped_column(JSON, default=list)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    donation_count: Mapped[int] = mapped_column(Integer, default=0)
    amount_raised: Mapped[int] = mapped_column(Integer, default=0)
    is_ai_reviewed: Mapped[bool] = mapped_column(default=False)
    ai_review_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_flags: Mapped[list] = mapped_column(JSON, default=list)
    verification_status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    verified_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_update_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CampaignMilestone(Base):
    """Trackable milestone within a campaign."""

    __tablename__ = "campaign_milestones"
    __table_args__ = (UniqueConstraint("campaign_id", "sequence_num", name="uq_milestone_campaign_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    sequence_num: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date] = mapped_column(Date)
    target_amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DonationType(Base):
    """Types of donations available for a campaign (cash, books, blood, etc)."""

    __tablename__ = "donation_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    quantity_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    value_in_rupees: Mapped[int] = mapped_column(Integer)
    is_available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CampaignDonation(Base):
    """Append-only donation records for campaigns."""

    __tablename__ = "campaign_donations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    donation_type_id: Mapped[str] = mapped_column(ForeignKey("donation_types.id"))
    donor_name: Mapped[str] = mapped_column(String(200))
    donor_email: Mapped[str] = mapped_column(String(200))
    donor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    payment_gateway_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CampaignReview(Base):
    """AI + Admin review of campaign before approval."""

    __tablename__ = "campaign_reviews"
    __table_args__ = (UniqueConstraint("campaign_id", name="uq_review_campaign_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), unique=True, index=True)
    ai_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_flags: Mapped[list] = mapped_column(JSON, default=list)
    ai_recommendation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trustworthiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_decision: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_changes_requested: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# Phase 3: Email Notifications & Preferences
# ============================================================================


class NotificationFrequency(str, enum.Enum):
    """How often a user wants to receive a particular type of notification."""
    INSTANT = "INSTANT"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    NEVER = "NEVER"


class EmailQueueStatus(str, enum.Enum):
    """Status of an email in the queue."""
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


class EmailQueue(Base):
    """Queue of emails to be sent via background job."""

    __tablename__ = "email_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    recipient_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    html_body: Mapped[str] = mapped_column(Text)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str] = mapped_column(String(100))
    template_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationPreferences(Base):
    """User preferences for email notifications."""

    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    donation_received: Mapped[str] = mapped_column(String(20), default="INSTANT")
    milestone_reached: Mapped[str] = mapped_column(String(20), default="INSTANT")
    campaign_published: Mapped[str] = mapped_column(String(20), default="INSTANT")
    ngo_verified: Mapped[str] = mapped_column(String(20), default="INSTANT")
    donor_digest: Mapped[str] = mapped_column(String(20), default="WEEKLY")
    marketing_emails: Mapped[bool] = mapped_column(default=False)
    unsubscribe_token: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailTemplate(Base):
    """Email templates for different event types."""

    __tablename__ = "email_templates"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_email_templates_name_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    subject_template: Mapped[str] = mapped_column(String(255))
    html_template: Mapped[str] = mapped_column(Text)
    text_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SentEmail(Base):
    """Append-only audit trail of sent emails."""

    __tablename__ = "sent_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email_queue_id: Mapped[str | None] = mapped_column(ForeignKey("email_queue.id"), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(255))
    recipient_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    opened: Mapped[bool] = mapped_column(default=False)
    clicked: Mapped[bool] = mapped_column(default=False)
    bounced: Mapped[bool] = mapped_column(default=False)
    delivery_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ============================================================================
# Phase 5: Payment & Recurring Donations
# ============================================================================


class PaymentStatus(str, enum.Enum):
    """Status of a payment transaction."""
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(Base):
    """Append-only payment records for donations (one-time and recurring)."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    donor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    donor_name: Mapped[str] = mapped_column(String(200))
    donor_email: Mapped[str] = mapped_column(String(320), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)  # Amount in paise (1 rupee = 100 paise)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default="INITIATED", index=True)
    payment_method: Mapped[str] = mapped_column(String(30), default="RAZORPAY")  # RAZORPAY, BANK_TRANSFER, etc.
    gateway_order_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    gateway_payment_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    gateway_signature: Mapped[str | None] = mapped_column(String(256), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(default=False)
    recurring_plan_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecurringDonation(Base):
    """Subscription for recurring donations."""

    __tablename__ = "recurring_donations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    donor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    donor_name: Mapped[str] = mapped_column(String(200))
    donor_email: Mapped[str] = mapped_column(String(320), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    frequency: Mapped[str] = mapped_column(String(20))  # MONTHLY, QUARTERLY, YEARLY
    gateway_subscription_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE, PAUSED, CANCELLED
    next_billing_date: Mapped[date] = mapped_column(Date)
    total_payments: Mapped[int] = mapped_column(Integer, default=0)
    total_amount_paid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaxReceipt(Base):
    """Tax receipt for donation (80G compliance in India)."""

    __tablename__ = "tax_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), unique=True)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    donor_name: Mapped[str] = mapped_column(String(200))
    donor_email: Mapped[str] = mapped_column(String(320))
    donor_pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    ngo_name: Mapped[str] = mapped_column(String(200))
    ngo_80g_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ngo_registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receipt_date: Mapped[date] = mapped_column(Date)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# Smart Admin Intelligence Features
# ============================================================================


class RiskScore(Base):
    """AI-generated risk score for NGOs and donors. Cached and recomputed periodically."""

    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    score_type: Mapped[str] = mapped_column(String(20))  # "NGO" or "DONOR"
    score_value: Mapped[int] = mapped_column(Integer)  # 0-100
    factors: Mapped[dict] = mapped_column(JSON)  # {"verification": 30, "completion_rate": 20, ...}
    confidence: Mapped[str] = mapped_column(String(20))  # "LOW", "MEDIUM", "HIGH"
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AnomalyFlag(Base):
    """Real-time anomaly detection flags for suspicious activity."""

    __tablename__ = "anomaly_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    flag_type: Mapped[str] = mapped_column(String(50))  # "DUPLICATE_ACCOUNT", "UNUSUAL_DONATION", etc.
    severity: Mapped[str] = mapped_column(String(20))  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    details: Mapped[dict] = mapped_column(JSON)  # Context-specific data
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SmartAlert(Base):
    """Proactive admin alerts for actionable items."""

    __tablename__ = "smart_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    alert_type: Mapped[str] = mapped_column(String(50))  # "INACTIVE_NGO", "CHURN_RISK", etc.
    subject_org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    subject_project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    message: Mapped[str] = mapped_column(String(500))
    priority: Mapped[str] = mapped_column(String(20))  # "LOW", "MEDIUM", "HIGH", "URGENT"
    recommended_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ChurnPrediction(Base):
    """Predictive churn risk for donors and NGOs."""

    __tablename__ = "churn_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    org_type: Mapped[str] = mapped_column(String(20))  # "DONOR" or "NGO"
    churn_risk_score: Mapped[int] = mapped_column(Integer)  # 0-100: % likelihood inactive in 90 days
    factors: Mapped[dict] = mapped_column(JSON)  # Engagement trend, behavior changes, cohort comparison
    intervention_suggested: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CampaignPrediction(Base):
    """Campaign success probability forecast."""

    __tablename__ = "campaign_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    success_probability: Mapped[float] = mapped_column(Integer)  # Stored as 0-100 (multiply by 100 to use)
    reasoning: Mapped[dict] = mapped_column(JSON)  # Historical rate, sector demand, comparables
    confidence: Mapped[str] = mapped_column(String(20))  # "LOW", "MEDIUM", "HIGH"
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ============================================================================
# Direct conversations: admin <-> organisation, and donor <-> admin
# ============================================================================


class ConversationKind(str, enum.Enum):
    """Who is on each side. Proposal threads are not here: they belong to a proposal
    and live in proposal_messages, keyed by that proposal rather than by participants."""

    ADMIN_ORG = "ADMIN_ORG"      # platform staff <-> an NGO or CSR organisation
    DONOR_ADMIN = "DONOR_ADMIN"  # a donor <-> platform staff
    ORG_ORG = "ORG_ORG"          # an NGO <-> a CSR organisation, general enquiry (not tied to a proposal)
    DONOR_NGO = "DONOR_NGO"      # an individual donor <-> an NGO, general enquiry


class Conversation(Base):
    """A direct thread between two counterparties.

    Which columns are set, and what they mean, is determined by kind:
    - ADMIN_ORG: org_id is the organisation; the other side is implicitly platform staff.
    - DONOR_ADMIN: donor_user_id is the donor; the other side is implicitly platform staff.
    - ORG_ORG: org_id and counterparty_org_id are the two organisations (an NGO and a CSR).
    - DONOR_NGO: org_id is the NGO, donor_user_id is the donor.
    Access is derived from these columns, never stored as a participant list, so a
    conversation cannot drift out of step with who is actually entitled to read it.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Not a native Postgres enum (native_enum=False): a plain, extensible string column.
    kind: Mapped[ConversationKind] = mapped_column(
        Enum(ConversationKind, name="conversation_kind", native_enum=False, length=20), index=True
    )
    subject: Mapped[str] = mapped_column(String(300))
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    counterparty_org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    donor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    opened_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)  # OPEN, CLOSED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationMessage(Base):
    """One message in a direct conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # Which side the sender spoke as: ADMIN, ORG or DONOR. Stored rather than derived so
    # the record of who said what survives a later change of staff status or membership.
    sender_side: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
