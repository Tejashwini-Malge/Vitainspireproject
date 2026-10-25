"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Notice } from "@/components/Notice";
import { OrgNav } from "@/components/OrgNav";
import { VerificationBadge } from "@/components/VerificationBadge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Donation, Me, Org } from "@/lib/types";

function formatMoney(amountMinor: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amountMinor / 100);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function OrgDonationsPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>()!;
  const [org, setOrg] = useState<Org | null>(null);
  const [donations, setDonations] = useState<Donation[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [, o, d] = await Promise.all([
        api<Me>("/auth/me"),
        api<Org>(`/orgs/${id}`),
        api<Donation[]>(`/orgs/${id}/donations`),
      ]);
      setOrg(o);
      setDonations(d);
      setLoadError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        return;
      }
      setLoadError(err instanceof Error ? err.message : "Could not load donations.");
    }
  }, [id, router]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [load, router]);

  if (notFound) {
    return <p className="text-muted">This organization was not found, or you are not a member of it.</p>;
  }
  if (loadError) return <Notice kind="error">{loadError}</Notice>;
  if (!org || !donations) return <p className="text-muted">Loading donations…</p>;

  const total = donations.reduce((sum, d) => sum + d.amount_minor, 0);

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <PageHeader
          eyebrow={org.org_type}
          title={org.name}
          description={<VerificationBadge status={org.verification_status} />}
        />
        <OrgNav orgId={id} showNgoTabs={org.org_type === "NGO"} />
      </div>

      {org.org_type !== "NGO" ? (
        <p className="text-muted">Donations are received by NGO organizations.</p>
      ) : donations.length === 0 ? (
        <EmptyState title="No donations have been received yet" />
      ) : (
        <section className="space-y-4">
          <p className="text-lg">
            <span className="font-semibold text-navy">{formatMoney(total, donations[0].currency)}</span>{" "}
            <span className="text-muted">received across {donations.length} donation{donations.length === 1 ? "" : "s"}</span>
          </p>
          <Card className="divide-y divide-line">
            {donations.map((d) => (
              <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <div>
                  <p className="font-medium text-navy">{d.donor_name}</p>
                  <p className="text-sm text-muted">{formatDate(d.created_at)}</p>
                  {d.message && <p className="mt-1 text-sm italic text-muted">&ldquo;{d.message}&rdquo;</p>}
                </div>
                <span className="font-medium">{formatMoney(d.amount_minor, d.currency)}</span>
              </div>
            ))}
          </Card>
        </section>
      )}
    </div>
  );
}
