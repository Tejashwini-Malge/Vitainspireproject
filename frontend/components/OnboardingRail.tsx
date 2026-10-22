"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, getToken } from "@/lib/api";
import type { Me, OnboardingStatus, Org } from "@/lib/types";

// A persistent guide to "what's left to do" for a signed-in CSR or NGO workspace. Hidden on
// admin pages (staff have their own queues, not an org onboarding checklist) and for anyone
// without an org-scoped workspace (individual donors, anonymous visitors).
export function OnboardingRail() {
  const pathname = usePathname();
  const [open, setOpen] = useState(true);
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [orgName, setOrgName] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const hidden = pathname?.startsWith("/admin") ?? false;

  useEffect(() => {
    if (hidden || !getToken()) {
      setStatus(null);
      return;
    }
    let cancelled = false;
    Promise.all([api<Me>("/auth/me"), api<Org[]>("/orgs")])
      .then(([, orgs]) => {
        const org = orgs.find((o) => o.org_type === "NGO" || o.org_type === "CSR");
        if (!org) return null;
        setOrgName(org.name);
        return api<OnboardingStatus>(`/orgs/${org.id}/onboarding/status`);
      })
      .then((s) => {
        if (!cancelled && s) setStatus(s);
      })
      .catch((err) => {
        // Not a critical feature: a failed fetch (401, network, no membership) just hides the rail.
        if (!cancelled) setFailed(!(err instanceof ApiError && err.status === 401));
      });
    return () => {
      cancelled = true;
    };
  }, [hidden, pathname]);

  if (hidden || failed || !status || status.steps.length === 0 || status.completion_pct === 100) return null;

  return (
    <aside
      className={`fixed right-4 top-24 z-40 w-72 rounded-sm border-2 border-navy bg-paper shadow-lg transition-all ${
        open ? "" : "w-auto"
      }`}
      aria-label="Onboarding guide"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 border-b-2 border-navy px-3 py-2 text-left"
      >
        <span className="font-display text-sm font-semibold text-navy">
          {open ? `Getting set up${orgName ? ` · ${orgName}` : ""}` : `${status.completion_pct}%`}
        </span>
        <span className="text-xs text-muted">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="space-y-3 p-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={status.completion_pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-teal transition-all" style={{ width: `${status.completion_pct}%` }} />
          </div>
          <ul className="space-y-2 text-sm">
            {status.steps.map((step) => (
              <li key={step.key} className="flex items-start gap-2">
                <span
                  className={`mt-0.5 flex h-4 w-4 flex-none items-center justify-center rounded-full border text-[10px] leading-none ${
                    step.done ? "border-status-approved bg-status-approved text-paper" : "border-line text-transparent"
                  }`}
                >
                  ✓
                </span>
                {step.done ? (
                  <span className="text-muted line-through">{step.label}</span>
                ) : (
                  <Link href={step.cta_href} className="text-navy hover:text-teal hover:underline">
                    {step.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
