"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Notice } from "@/components/Notice";
import { VerificationBadge } from "@/components/VerificationBadge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
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
      <EmptyState
        title="This NGO is not available for donations"
        description="It may not exist, or has not been verified and published yet."
        action={
          <Link href="/" className="font-medium text-teal hover:underline">
            Back to browsing
          </Link>
        }
      />
    );
  }
  if (!ngo) return <p className="text-muted">Loading…</p>;

  if (receipt) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="mx-auto max-w-lg space-y-6"
      >
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
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="mx-auto max-w-lg space-y-6"
    >
      <header className="space-y-2">
        <VerificationBadge status="APPROVED" />
        <h1 className="text-2xl font-semibold text-navy">Donate to {ngo.name}</h1>
        <p className="text-muted">{ngo.profile.mission}</p>
      </header>

      <Card className="p-6 sm:p-8">
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-navy">Your name</span>
              <Input
                required
                maxLength={200}
                value={donorName}
                onChange={(e) => setDonorName(e.target.value)}
                className="mt-1"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-navy">Email (for your receipt)</span>
              <Input
                type="email"
                required
                value={donorEmail}
                onChange={(e) => setDonorEmail(e.target.value)}
                className="mt-1"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-navy">Amount (INR)</span>
              <Input
                type="number"
                required
                min="1"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="mt-1 font-mono"
              />
            </label>
          </div>

          <fieldset className="space-y-4 rounded-sm border border-line bg-navy/[0.03] p-4">
            <legend className="px-1 text-sm font-medium text-navy">Billing address</legend>
            <label className="block">
              <span className="text-sm text-ink">Address line 1</span>
              <Input
                required
                maxLength={200}
                value={billing.line1}
                onChange={(e) => updateBilling("line1", e.target.value)}
                className="mt-1"
              />
            </label>
            <label className="block">
              <span className="text-sm text-ink">Address line 2 (optional)</span>
              <Input
                maxLength={200}
                value={billing.line2}
                onChange={(e) => updateBilling("line2", e.target.value)}
                className="mt-1"
              />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="text-sm text-ink">City</span>
                <Input
                  required
                  maxLength={100}
                  value={billing.city}
                  onChange={(e) => updateBilling("city", e.target.value)}
                  className="mt-1"
                />
              </label>
              <label className="block">
                <span className="text-sm text-ink">State</span>
                <Input
                  required
                  maxLength={100}
                  value={billing.state}
                  onChange={(e) => updateBilling("state", e.target.value)}
                  className="mt-1"
                />
              </label>
              <label className="block">
                <span className="text-sm text-ink">Postal code</span>
                <Input
                  required
                  maxLength={20}
                  value={billing.postal_code}
                  onChange={(e) => updateBilling("postal_code", e.target.value)}
                  className="mt-1"
                />
              </label>
              <label className="block">
                <span className="text-sm text-ink">Country</span>
                <Input
                  required
                  maxLength={100}
                  value={billing.country}
                  onChange={(e) => updateBilling("country", e.target.value)}
                  className="mt-1"
                />
              </label>
            </div>
          </fieldset>

          <label className="block">
            <span className="text-sm font-medium text-navy">Message to the NGO (optional)</span>
            <Textarea
              rows={2}
              maxLength={500}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="mt-1"
            />
          </label>

          {error && (
            <p role="alert" className="text-sm text-status-rejected">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy} className="w-full" size="lg">
            {busy ? "Recording donation…" : "Donate"}
          </Button>
          <p className="text-center text-sm text-muted">
            No account is needed. If you are signed in, this donation is also added to your donation history.
          </p>
        </form>
      </Card>
    </motion.div>
  );
}

export default function DonatePage() {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <DonateForm />
    </Suspense>
  );
}
