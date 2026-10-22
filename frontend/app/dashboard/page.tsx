"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import { VerificationBadge } from "@/components/VerificationBadge";
import type { Donation, Me, Org, PanVerificationStatus } from "@/lib/types";

function formatMoney(amountMinor: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amountMinor / 100);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function Dashboard() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [orgs, setOrgs] = useState<Org[] | null>(null);
  const [donations, setDonations] = useState<Donation[] | null>(null);
  const [panStatus, setPanStatus] = useState<PanVerificationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    Promise.all([
      api<Me>("/auth/me"),
      api<Org[]>("/orgs"),
      api<Donation[]>("/me/donations"),
      api<PanVerificationStatus>("/me/pan-verification/status"),
    ])
      .then(([m, o, d, p]) => {
        setMe(m);
        setOrgs(o);
        setDonations(d);
        setPanStatus(p);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load your workspace.");
      });
  }, [router]);

  if (error) {
    return (
      <p role="alert" className="text-status-rejected">
        {error}
      </p>
    );
  }
  if (!me || !orgs) return <p className="text-muted">Loading your workspace…</p>;

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-semibold text-navy">Welcome, {me.full_name}</h1>
        <p className="text-muted">{me.email}</p>
      </header>

      <section aria-labelledby="pan-heading" className="space-y-2 rounded-sm border-2 border-line bg-white p-5">
        <h2 id="pan-heading" className="text-lg font-semibold text-navy">
          PAN verification
        </h2>
        {panStatus?.verified ? (
          <p className="text-sm text-status-approved">
            Verified ({panStatus.pan_number}). Tax certificates for your donations will be emailed to you.
          </p>
        ) : panStatus?.status === "PENDING_REVIEW" ? (
          <p className="text-sm text-muted">Your PAN submission is awaiting review.</p>
        ) : panStatus?.status === "REJECTED" ? (
          <p className="text-sm text-status-rejected">Your last PAN submission was not accepted. Submit again with a corrected file.</p>
        ) : (
          <p className="text-sm text-muted">Verify your PAN to receive a tax (80G) certificate by email for your donations.</p>
        )}
        <Link href="/dashboard/pan-verification" className="text-sm font-medium text-teal hover:underline">
          {panStatus?.verified ? "View verification" : "Verify your PAN"}
        </Link>
      </section>

      <section aria-labelledby="orgs-heading" className="space-y-4">
        <h2 id="orgs-heading" className="text-lg font-semibold text-navy">
          Your organizations
        </h2>
        {orgs.length === 0 ? (
          <p className="text-muted">
            You do not belong to any organization yet.{" "}
            <Link href="/register/ngo" className="font-medium text-teal hover:underline">
              Register an NGO
            </Link>{" "}
            or{" "}
            <Link href="/register/donor" className="font-medium text-teal hover:underline">
              register as a donor or CSR team
            </Link>
            .
          </p>
        ) : (
          <ul className="divide-y-2 divide-line rounded-sm border-2 border-line bg-white">
            {orgs.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div>
                  <Link href={`/orgs/${o.id}`} className="font-medium text-navy hover:underline">
                    {o.name}
                  </Link>
                  <span className="ml-2 text-sm text-muted">{o.org_type}</span>
                </div>
                <VerificationBadge status={o.verification_status} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* CSR Actions */}
      {orgs && orgs.some(o => o.org_type === 'CSR') && (
        <section className="space-y-4 border-t border-line pt-8">
          <h2 className="text-lg font-semibold text-navy">CSR Actions</h2>
          <div className="flex gap-4 flex-wrap">
            <Link
              href="/csr/opportunities"
              className="inline-block rounded bg-teal text-white px-6 py-3 font-medium hover:bg-teal/90"
            >
              📋 Manage Opportunities
            </Link>
            <Link
              href="/csr/proposals"
              className="inline-block rounded bg-blue-600 text-white px-6 py-3 font-medium hover:bg-blue-700"
            >
              📄 Review Proposals
            </Link>
          </div>
        </section>
      )}

      {/* NGO Actions */}
      {orgs && orgs.some(o => o.org_type === 'NGO') && (
        <section className="space-y-4 border-t border-line pt-8">
          <h2 className="text-lg font-semibold text-navy">NGO Actions</h2>
          <div className="flex gap-4 flex-wrap">
            <Link
              href="/ngo/proposals"
              className="inline-block rounded bg-green-600 text-white px-6 py-3 font-medium hover:bg-green-700"
            >
              ✍️ My Proposals
            </Link>
            <Link
              href="/ngo/proposals/create"
              className="inline-block rounded bg-green-500 text-white px-6 py-3 font-medium hover:bg-green-600"
            >
              ➕ Submit Proposal
            </Link>
          </div>
        </section>
      )}

      <section aria-labelledby="donations-heading" className="space-y-4 border-t border-line pt-8">
        <h2 id="donations-heading" className="text-lg font-semibold text-navy">
          Your donations
        </h2>
        {!donations || donations.length === 0 ? (
          <p className="text-muted">
            No donations yet.{" "}
            <Link href="/" className="font-medium text-teal hover:underline">
              Browse NGOs
            </Link>{" "}
            to make one.
          </p>
        ) : (
          <ul className="divide-y-2 divide-line rounded-sm border-2 border-line bg-white">
            {donations.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <span className="text-sm text-muted">{formatDate(d.created_at)}</span>
                <span className="font-medium">{formatMoney(d.amount_minor, d.currency)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {me.is_platform_admin && (
        <p className="border-t border-line pt-6">
          <Link href="/admin" className="font-medium text-teal hover:underline">
            Open the verification queue
          </Link>
          <span className="mx-3 text-line">|</span>
          <Link href="/admin/documents" className="font-medium text-teal hover:underline">
            Open document review
          </Link>
        </p>
      )}
    </div>
  );
}
