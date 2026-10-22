import type { VerificationStatus } from "@/lib/types";

const LABEL: Record<VerificationStatus, string> = {
  PENDING: "Pending verification",
  APPROVED: "Verified",
  REJECTED: "Not verified",
};

const COLOR: Record<VerificationStatus, string> = {
  PENDING: "text-status-pending",
  APPROVED: "text-status-approved",
  REJECTED: "text-status-rejected",
};

// Status is always stated in words, never by colour alone. APPROVED gets the ink-stamp
// treatment because it is the one state a person actually signed off on; the others are
// plain text, because nobody has stamped anything yet.
export function VerificationBadge({ status }: { status: VerificationStatus }) {
  if (status === "APPROVED") {
    return <span className={`ink-stamp ${COLOR[status]}`}>{LABEL[status]}</span>;
  }
  return <span className={`text-sm font-medium ${COLOR[status]}`}>{LABEL[status]}</span>;
}
