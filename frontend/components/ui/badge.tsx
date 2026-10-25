import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export type BadgeTone = "pending" | "approved" | "rejected" | "neutral";

const TONE: Record<BadgeTone, string> = {
  pending: "border-status-pending/40 text-status-pending bg-status-pending/10",
  approved: "border-status-approved/40 text-status-approved bg-status-approved/10",
  rejected: "border-status-rejected/40 text-status-rejected bg-status-rejected/10",
  neutral: "border-line text-muted bg-navy/5",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

/** Small status pill. Always paired with the word itself -- colour is never the only signal. */
export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 font-mono text-[0.7rem] uppercase tracking-wide",
        TONE[tone],
        className,
      )}
      {...props}
    />
  );
}

export default Badge;
