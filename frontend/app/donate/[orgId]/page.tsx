"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { Notice } from "@/components/Notice";
import { api, ApiError, clearToken } from "@/lib/api";
import type { Donation, PublicNgo } from "@/lib/types";

const EMPTY_BILLING = { line1: "", line2: "", city: "", state: "", postal_code: "", country: "India" };

function DonateForm() {
  const { orgId } = useParams<{ orgId: string }>()!;
  const params = useSearchParams();
  const projectId = params?.get("project") ?? null;

  const [ngo, setNgo] = useState<PublicNgo | null | "not-found">(null);
  const [donorName, setDonorName] = useState("");
  const [donorEmail, setDonorEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState("");
  const [billing, setBilling] = useState(EMPTY_BILLING);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<Donation | null>(null);

  useEffect(() => {
    api<PublicNgo>(`/public/ngos/${orgId}`)
      .then(setNgo)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNgo("not-found");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load this NGO.");
      });
  }, [orgId]);

  function updateBilling<K extends keyof typeof EMPTY_BILLING>(key: K, value: string) {
    setBilling((b) => ({ ...b, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = JSON.stringify({
      donor_name: donorName,
      donor_email: donorEmail,
      amount,
      billing_address: { ...billing, line2: billing.line2.trim() || null },
      project_id: projectId || null,
      message: message.trim() || null,
    });
    try {
      const donation = await api<Donation>(`/public/ngos/${orgId}/donations`, { method: "POST", body });
      setReceipt(donation);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // A stale or expired session should never block a donation -- donating never requires
        // being signed in. Drop the dead session and submit again as a guest.
        clearToken();
        try {
          const donation = await api<Donation>(`/public/ngos/${orgId}/donations`, { method: "POST", body });
          setReceipt(donation);
        } catch (retryErr) {
          setError(retryErr instanceof Error ? retryErr.message : "Could not record this donation. Try again.");
        }
      } else {
        setError(err instanceof Error ? err.message : "Could not record this donation. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (ngo === "not-found") {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">This NGO is not available for donations</h1>
        <p className="text-muted">It may not exist, or has not been verified and published yet.</p>
        <Link href="/" className="text-teal hover:underline">
          Back to browsing
        </Link>
      </div>
    );
  }
  if (!ngo) return <p className="text-muted">Loading…</p>;

  if (receipt) {
    return (
      <div className="mx-auto max-w-lg space-y-6">
        <Notice kind="success">Thank you, {receipt.donor_name}. This is now on the ledger -- {ngo.name} and Imparency can both see it.</Notice>
        <dl className="stub-card">
          <div className="space-y-2 p-5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">To</dt>
              <dd className="font-medium text-navy">{ngo.name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Amount</dt>
              <dd className="font-mono font-medium text-navy">
                {new Intl.NumberFormat("en-IN", { style: "currency", currency: receipt.currency }).format(receipt.amount_minor / 100)}
              </dd>
            </div>
            <div className="flex justify-between gap-6">
              <dt className="shrink-0 text-muted">Billing address</dt>
              <dd className="text-right">
                {receipt.billing_address.line1}
                {receipt.billing_address.line2 ? `, ${receipt.billing_address.line2}` : ""}, {receipt.billing_address.city},{" "}
                {receipt.billing_address.state} {receipt.billing_address.postal_code}, {receipt.billing_address.country}
              </dd>
            </div>
          </div>
          <div className="stub-tear flex items-center justify-between p-5 text-xs">
            <dt className="text-muted">Receipt ID</dt>
            <dd className="font-mono">{receipt.id}</dd>
          </div>
        </dl>
        <Link href="/" className="inline-block font-medium text-teal hover:underline">
          Back to browsing
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="space-y-1">
        <p className="text-sm font-medium text-status-approved">Verified by Imparency</p>
        <h1 className="text-2xl font-semibold text-navy">Donate to {ngo.name}</h1>
        <p className="text-muted">{ngo.profile.mission}</p>
      </header>

      <form onSubmit={onSubmit} className="space-y-5">
        <label className="block">
          <span className="text-sm font-medium">Your name</span>
          <input required maxLength={200} value={donorName} onChange={(e) => setDonorName(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Email (for your receipt)</span>
          <input type="email" required value={donorEmail} onChange={(e) => setDonorEmail(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Amount (INR)</span>
          <input type="number" required min="1" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2 font-mono" />
        </label>

        <fieldset className="space-y-4">
          <legend className="text-sm font-medium">Billing address</legend>
          <label className="block">
            <span className="text-sm">Address line 1</span>
            <input required maxLength={200} value={billing.line1} onChange={(e) => updateBilling("line1", e.target.value)}
              className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
          </label>
          <label className="block">
            <span className="text-sm">Address line 2 (optional)</span>
            <input maxLength={200} value={billing.line2} onChange={(e) => updateBilling("line2", e.target.value)}
              className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-sm">City</span>
              <input required maxLength={100} value={billing.city} onChange={(e) => updateBilling("city", e.target.value)}
                className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
            </label>
            <label className="block">
              <span className="text-sm">State</span>
              <input required maxLength={100} value={billing.state} onChange={(e) => updateBilling("state", e.target.value)}
                className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
            </label>
            <label className="block">
              <span className="text-sm">Postal code</span>
              <input required maxLength={20} value={billing.postal_code} onChange={(e) => updateBilling("postal_code", e.target.value)}
                className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
            </label>
            <label className="block">
              <span className="text-sm">Country</span>
              <input required maxLength={100} value={billing.country} onChange={(e) => updateBilling("country", e.target.value)}
                className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
            </label>
          </div>
        </fieldset>

        <label className="block">
          <span className="text-sm font-medium">Message to the NGO (optional)</span>
          <textarea rows={2} maxLength={500} value={message} onChange={(e) => setMessage(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>

        {error && (
          <p role="alert" className="text-sm text-status-rejected">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}
          className="w-full rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
          {busy ? "Recording donation…" : "Donate"}
        </button>
        <p className="text-sm text-muted">
          No account is needed. If you are signed in, this donation is also added to your donation history.
        </p>
      </form>
    </div>
  );
}

export default function DonatePage() {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <DonateForm />
    </Suspense>
  );
}
