"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { RecurringDonation, Me } from "@/lib/types";

type PageState = "loading" | "error" | "ready";

export default function RecurringDonationsPage() {
  const router = useRouter();
  const [state, setState] = useState<PageState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [donations, setDonations] = useState<RecurringDonation[]>([]);
  const [managingId, setManagingId] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }

    async function loadData() {
      try {
        setState("loading");
        // Verify user is authenticated
        await api<Me>("/auth/me");

        // In a real app, would fetch user's recurring donations
        // For now, show empty state
        setDonations([]);
        setState("ready");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load donations");
        setState("error");
      }
    }

    loadData();
  }, [router]);

  const handlePause = async (donationId: string) => {
    setManagingId(donationId);
    try {
      await api(`/payments/recurring/${donationId}/pause`, { method: "POST" });
      // Refresh list
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to pause donation");
    } finally {
      setManagingId(null);
    }
  };

  const handleResume = async (donationId: string) => {
    setManagingId(donationId);
    try {
      await api(`/payments/recurring/${donationId}/resume`, { method: "POST" });
      // Refresh list
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resume donation");
    } finally {
      setManagingId(null);
    }
  };

  const handleCancel = async (donationId: string) => {
    if (confirm("Are you sure you want to cancel this recurring donation?")) {
      setManagingId(donationId);
      try {
        await api(`/payments/recurring/${donationId}/cancel`, { method: "POST" });
        // Refresh list
        window.location.reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to cancel donation");
      } finally {
        setManagingId(null);
      }
    }
  };

  if (state === "error") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-navy">Recurring Donations</h1>
        <p role="alert" className="text-status-rejected">{error}</p>
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-navy">Recurring Donations</h1>
        <p className="text-muted">Loading your donations...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-navy">Recurring Donations</h1>
        <p className="mt-2 text-muted">
          Manage your monthly, quarterly, or yearly donations
        </p>
      </div>

      {donations.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-line bg-paper p-8 text-center">
          <div className="mb-4 text-4xl">💝</div>
          <h2 className="mb-2 font-semibold text-navy">No Active Donations</h2>
          <p className="mb-6 text-muted">
            You haven't set up any recurring donations yet.
          </p>
          <Link
            href="/campaigns"
            className="inline-block rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper hover:bg-teal/90"
          >
            Browse Campaigns
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {donations.map((donation) => (
            <div
              key={donation.id}
              className="rounded-lg border-2 border-line bg-white p-6"
            >
              <div className="flex items-start justify-between gap-4 md:flex-row">
                <div className="flex-1">
                  <div className="mb-4 flex items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        donation.status === "ACTIVE"
                          ? "bg-teal/10 text-teal"
                          : donation.status === "PAUSED"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {donation.status}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <div>
                      <p className="text-sm text-muted">Campaign</p>
                      <p className="font-medium text-navy">{donation.campaign_id}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                      <div>
                        <p className="text-xs text-muted">Monthly Amount</p>
                        <p className="font-semibold text-teal">
                          ₹{(donation.amount_minor / 100).toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted">Frequency</p>
                        <p className="font-semibold text-navy">
                          {donation.frequency === "MONTHLY"
                            ? "Monthly"
                            : donation.frequency === "QUARTERLY"
                              ? "Quarterly"
                              : "Yearly"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted">Total Donated</p>
                        <p className="font-semibold text-navy">
                          ₹{(donation.total_amount_paid / 100).toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted">Next Billing</p>
                        <p className="font-semibold text-navy">
                          {new Date(donation.next_billing_date).toLocaleDateString(
                            "en-IN"
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-2">
                  {donation.status === "ACTIVE" ? (
                    <>
                      <button
                        onClick={() => handlePause(donation.id)}
                        disabled={managingId === donation.id}
                        className="rounded-sm border-2 border-yellow-500 px-3 py-1 text-sm font-medium text-yellow-600 hover:bg-yellow-50 disabled:opacity-60"
                      >
                        ⏸ Pause
                      </button>
                      <button
                        onClick={() => handleCancel(donation.id)}
                        disabled={managingId === donation.id}
                        className="rounded-sm border-2 border-status-rejected px-3 py-1 text-sm font-medium text-status-rejected hover:bg-status-rejected/5 disabled:opacity-60"
                      >
                        ✕ Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => handleResume(donation.id)}
                        disabled={managingId === donation.id}
                        className="rounded-sm border-2 border-teal px-3 py-1 text-sm font-medium text-teal hover:bg-teal/5 disabled:opacity-60"
                      >
                        ▶ Resume
                      </button>
                      <button
                        onClick={() => handleCancel(donation.id)}
                        disabled={managingId === donation.id}
                        className="rounded-sm border-2 border-status-rejected px-3 py-1 text-sm font-medium text-status-rejected hover:bg-status-rejected/5 disabled:opacity-60"
                      >
                        ✕ Cancel
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Donation History */}
              <div className="mt-4 border-t border-line pt-4">
                <p className="text-xs font-medium text-muted">
                  Total payments: {donation.total_payments}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-sm border-2 border-status-rejected bg-status-rejected/5 p-4">
          <p className="text-sm text-status-rejected">{error}</p>
        </div>
      )}
    </div>
  );
}
