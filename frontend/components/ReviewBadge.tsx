import type { ReviewStatus } from "@/lib/types";

const LABEL: Record<ReviewStatus, string> = {
  PENDING_REVIEW: "Awaiting review",
  APPROVED: "Approved",
  REJECTED: "Not accepted",
};

const COLOR: Record<ReviewStatus, string> = {
  PENDING_REVIEW: "text-status-pending",
  APPROVED: "text-status-approved",
  REJECTED: "text-status-rejected",
};

// Status is always stated in words, never by colour alone.
export function ReviewBadge({ status }: { status: ReviewStatus }) {
  return <span className={`text-sm font-medium ${COLOR[status]}`}>{LABEL[status]}</span>;
}
