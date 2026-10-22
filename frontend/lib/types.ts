export type OrgType = "NGO" | "CSR" | "INDIVIDUAL";
export type VerificationStatus = "PENDING" | "APPROVED" | "REJECTED";
export type Role = "OWNER" | "ADMIN" | "MEMBER";

export interface Me {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
}

export interface Org {
  id: string;
  name: string;
  org_type: OrgType;
  verification_status: VerificationStatus;
  verification_reason: string | null;
}

export interface Member {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
}

export type ProfileStatus = "DRAFT" | "PUBLISHED";
export type DocumentType = "PAN" | "REGISTRATION" | "SECTION_12A" | "SECTION_80G" | "FCRA" | "OTHER";
export type ReviewStatus = "PENDING_REVIEW" | "APPROVED" | "REJECTED";

export interface Profile {
  org_id: string;
  status: ProfileStatus;
  mission: string;
  about: string | null;
  vision: string | null;
  description: string | null;
  organization_title: string | null;
  sectors: string[];
  geographies: string[];
  founded_year: number | null;
  website: string | null;
  registration_number: string | null;
  section_80g_number: string | null;
  published_at: string | null;
  updated_at: string;
}

export interface Decision {
  id: string;
  decision: ReviewStatus;
  reason: string;
  previous_status: ReviewStatus;
  decided_at: string;
}

export interface OrgDocument {
  id: string;
  org_id: string;
  doc_type: DocumentType;
  title: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  valid_until_stated: string | null;
  review_status: ReviewStatus;
  uploaded_at: string;
  latest_decision: Decision | null;
}

export interface AdminQueueItem {
  id: string;
  org_id: string;
  org_name: string;
  doc_type: DocumentType;
  title: string;
  original_filename: string;
  size_bytes: number;
  uploaded_at: string;
  valid_until_stated: string | null;
}

export interface PublicNgo {
  id: string;
  name: string;
  verified_at: string | null;
  profile: Profile;
  reviewed_documents: { doc_type: DocumentType; reviewed_at: string }[];
  disclaimer: string;
}

export type ProjectStatus = "DRAFT" | "PENDING_REVIEW" | "PUBLISHED" | "CHANGES_REQUESTED";

export interface Project {
  id: string;
  org_id: string;
  title: string;
  summary: string;
  description: string | null;
  /** The campaign funding this project; budget, milestones and beneficiaries live there. */
  campaign_id: string | null;
  status: ProjectStatus;
  /** Admin's note on a CHANGES_REQUESTED decision. Null otherwise. */
  review_feedback: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublicProject {
  id: string;
  org_id: string;
  org_name: string;
  org_sectors: string[];
  title: string;
  summary: string;
  description: string | null;
  published_at: string | null;
}

export interface BillingAddress {
  line1: string;
  line2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  country: string;
}

export interface Donation {
  id: string;
  org_id: string;
  project_id: string | null;
  donor_name: string;
  donor_email: string;
  billing_address: BillingAddress;
  amount_minor: number;
  currency: string;
  message: string | null;
  created_at: string;
}

export interface VerificationAssist {
  org_id: string;
  summary: string;
  flags: string[];
  sources: string[];
  generated_by: string;
  disclaimer: string;
}

export interface PanVerification {
  id: string;
  user_id: string;
  pan_number: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  review_status: ReviewStatus;
  uploaded_at: string;
  latest_decision: Decision | null;
}

export interface PanVerificationStatus {
  verified: boolean;
  status: ReviewStatus | null;
  pan_number: string | null;
}

export interface AdminIndividualDonorRow {
  user_id: string;
  email: string;
  full_name: string;
  created_at: string;
  pan_status: ReviewStatus | null;
  total_donated_minor: number;
  donation_count: number;
  ngo_count: number;
}

export interface AdminPaymentRow {
  id: string;
  campaign_id: string;
  campaign_title: string | null;
  ngo_name: string | null;
  donor_name: string;
  donor_email: string;
  amount_minor: number;
  currency: string;
  status: string;
  is_recurring: boolean;
  gateway_payment_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AdminPanQueueItem {
  id: string;
  user_id: string;
  user_email: string;
  user_full_name: string;
  pan_number: string;
  original_filename: string;
  size_bytes: number;
  uploaded_at: string;
}

export const DOC_TYPE_LABEL: Record<DocumentType, string> = {
  PAN: "PAN card",
  REGISTRATION: "Registration certificate",
  SECTION_12A: "Section 12A registration",
  SECTION_80G: "Section 80G certificate",
  FCRA: "FCRA registration",
  OTHER: "Other document",
};

// ============================================================================
// Admin Analytics Types
// ============================================================================

export interface EmailEngagement {
  total_sent: number;
  total_pending: number;
  total_failed: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
  avg_retry_count: number;
  oldest_pending_hours: number | null;
}

export interface QueueMetrics {
  queue_depth: number;
  pending_count: number;
  failed_count: number;
  avg_processing_time_seconds: number | null;
  last_processed_at: string | null;
}

export interface FundraisingTrend {
  period: string;
  total_donations: number;
  donation_count: number;
  average_donation: number;
  total_campaigns: number;
  active_campaigns: number;
}

export interface CampaignPerformance {
  campaign_id: string;
  ngo_id: string;
  ngo_name: string;
  title: string;
  status: string;
  views: number;
  donation_count: number;
  amount_raised: number;
  conversion_rate: number;
  created_at: string;
  published_at: string | null;
}

export interface NgoMetrics {
  ngo_id: string;
  org_name: string;
  org_type: string;
  campaigns_total: number;
  campaigns_live: number;
  total_raised: number;
  total_donors: number;
  verified: boolean;
  verified_at: string | null;
}

export interface DonorSegment {
  segment_name: string;
  donor_count: number;
  total_donated: number;
  average_donation: number;
  active_donors: number;
  repeat_donation_rate: number;
}

export interface AdminDashboard {
  timestamp: string;
  total_ngos: number;
  verified_ngos: number;
  total_campaigns: number;
  live_campaigns: number;
  total_fundraising: number;
  total_donors: number;
  email_queue_health: QueueMetrics;
  engagement: EmailEngagement;
  top_campaigns: CampaignPerformance[];
  donor_segments: DonorSegment[];
}

// ============================================================================
// Payment Types (Phase 5)
// ============================================================================

export interface PaymentInitiate {
  payment_id: string;
  order_id: string;
  amount_minor: number;
  currency: string;
  customer_name: string;
  customer_email: string;
  key_id: string;
}

export interface Payment {
  id: string;
  campaign_id: string;
  donor_name: string;
  donor_email: string;
  amount_minor: number;
  currency: string;
  status: string;
  payment_method: string;
  gateway_order_id: string | null;
  gateway_payment_id: string | null;
  is_recurring: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface RecurringDonation {
  id: string;
  campaign_id: string;
  donor_name: string;
  donor_email: string;
  amount_minor: number;
  currency: string;
  frequency: string;
  status: string;
  next_billing_date: string;
  total_payments: number;
  total_amount_paid: number;
  created_at: string;
}

export interface TaxReceipt {
  id: string;
  receipt_number: string;
  donor_name: string;
  donor_email: string;
  amount_minor: number;
  currency: string;
  donor_pan: string | null;
  ngo_name: string;
  ngo_80g_number: string | null;
  ngo_registration_number: string | null;
  receipt_date: string;
  pdf_url: string | null;
  email_sent_at: string | null;
  created_at: string;
}

export interface SocialShareOut {
  platform: string;
  share_url: string;
  preview_text: string;
}

/** Mirrors backend CampaignOut (app/schemas.py). */
export interface Campaign {
  id: string;
  ngo_id: string;
  ngo_name: string;
  ngo_sectors: string[];
  ngo_geographies: string[];
  title: string;
  description: string;
  mission: string;
  beneficiary_count: number | null;
  beneficiary_description: string;
  impact_statement: string;
  budget_total: number;
  currency: string;
  budget_breakdown: Record<string, unknown> | null;
  duration_months: number;
  status: string;
  hero_image_url: string | null;
  images: string[];
  view_count: number;
  donation_count: number;
  amount_raised: number;
  verification_status: string;
  verified_at: string | null;
  rejection_reason: string | null;
  admin_notes: string | null;
  created_at: string;
  published_at: string | null;
}

/** Mirrors backend NotificationPreferencesOut (app/schemas.py). */
export interface NotificationPreferencesOut {
  id: string;
  user_id: string;
  donation_received: string;
  milestone_reached: string;
  campaign_published: string;
  ngo_verified: string;
  donor_digest: string;
  marketing_emails: boolean;
  unsubscribed_at: string | null;
  updated_at: string;
}

/** Mirrors backend InboxThreadOut (app/schemas.py). Covers every channel. */
export interface InboxThread {
  thread_id: string;
  kind: "PROPOSAL" | "ADMIN_ORG" | "DONOR_ADMIN" | "ORG_ORG" | "DONOR_NGO";
  title: string;
  counterparty_name: string;
  my_side: "NGO" | "CSR" | "ORG" | "DONOR" | "ADMIN";
  status: string;
  total_messages: number;
  unread_count: number;
  last_message_preview: string | null;
  last_message_at: string | null;
  last_sender_side: string | null;
  proposal_id: string | null;
  opportunity_id: string | null;
  conversation_id: string | null;
}

/** Mirrors backend ConversationOut. */
export interface Conversation {
  id: string;
  kind: "ADMIN_ORG" | "DONOR_ADMIN" | "ORG_ORG" | "DONOR_NGO";
  subject: string;
  org_id: string | null;
  counterparty_org_id: string | null;
  donor_user_id: string | null;
  status: string;
  created_at: string;
  closed_at: string | null;
  my_side: "ADMIN" | "ORG" | "DONOR";
}

/** Mirrors backend ConversationMessageOut. */
export interface ConversationMessage {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  sender_side: "ADMIN" | "ORG" | "DONOR";
  content: string;
  created_at: string;
  read_at: string | null;
}

/** Mirrors backend AdminOrgRowOut. */
export interface AdminOrgRow {
  id: string;
  name: string;
  org_type: OrgType;
  verification_status: VerificationStatus;
  verification_reason: string | null;
  verified_at: string | null;
  created_at: string;
  member_count: number;
  project_count: number;
  campaign_count: number;
  total_raised_minor: number;
}

/** Mirrors backend AdminProjectRowOut. */
export interface AdminProjectRow {
  id: string;
  title: string;
  summary: string;
  status: ProjectStatus;
  org_id: string;
  org_name: string;
  org_verification_status: VerificationStatus;
  campaign_id: string | null;
  published_at: string | null;
  created_at: string;
}

export interface AdminProjectQueueItem {
  id: string;
  org_id: string;
  org_name: string;
  title: string;
  summary: string;
  created_at: string;
}

export type ProposalStatus = "SUBMITTED" | "PENDING_CSR" | "ADMIN_REJECTED" | "APPROVED" | "CHANGES_REQUESTED";

export interface Proposal {
  id: string;
  proposal_id: string;
  opportunity_id: string;
  ngo_id: string;
  version_num: number;
  is_current: boolean;
  problem_statement: string;
  solution: string;
  budget_requested: number;
  timeline: string;
  expected_outcomes: string;
  status: ProposalStatus;
  created_at: string;
  updated_at: string;
}

export interface AdminProposalQueueItem {
  id: string;
  proposal_id: string;
  version_num: number;
  ngo_id: string;
  ngo_name: string;
  opportunity_id: string;
  opportunity_title: string;
  budget_requested: number;
  problem_statement: string;
  solution: string;
  created_at: string;
}

export interface OnboardingStep {
  key: string;
  label: string;
  done: boolean;
  cta_href: string;
}

export interface OnboardingStatus {
  org_type: OrgType;
  steps: OnboardingStep[];
  next_step: OnboardingStep | null;
  completion_pct: number;
}

export interface FeedItem {
  kind: "campaign" | "project";
  id: string;
  org_id: string;
  org_name: string;
  org_sectors: string[];
  org_geographies: string[];
  title: string;
  summary: string;
  hero_image_url: string | null;
  budget_total: number | null;
  amount_raised: number | null;
  published_at: string | null;
  score: number;
  distance_km: number | null;
  lat: number | null;
  lon: number | null;
}
