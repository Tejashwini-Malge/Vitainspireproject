"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { RecurringDonation, Me } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";

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
        <PageHeader title="Recurring Donations" />
        <p role="alert" className="text-status-rejected">{error}</p>
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div className="space-y-4">
        <PageHeader title="Recurring Donations" />
        <p className="text-muted">Loading your donations...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Recurring Donations" description="Manage your monthly, quarterly, or yearly donations" />

      {donations.length === 0 ? (
        <EmptyState
          title="No active donations"
          description="You haven't set up any recurring donations yet."
          action={<Button onClick={() => router.push("/campaigns")}>Browse Campaigns</Button>}
        />
      ) : (
        <div className="space-y-4">
          {donations.map((donation) => (
            <Card key={donation.id} className="p-6">
              <div className="flex items-start justify-between gap-4 md:flex-row">
                <div className="flex-1">
                  <div className="mb-4 flex items-center gap-2">
                    <Badge tone={donation.status === "ACTIVE" ? "approved" : donation.status === "PAUSED" ? "pending" : "neutral"}>
                      {donation.status}
                    </Badge>
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
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handlePause(donation.id)}
                        disabled={managingId === donation.id}
                        className="border-status-pending text-status-pending hover:bg-status-pending hover:text-paper"
                      >
                        Pause
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleCancel(donation.id)}
                        disabled={managingId === donation.id}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleResume(donation.id)}
                        disabled={managingId === donation.id}
                        className="border-teal text-teal hover:bg-teal hover:text-paper"
                      >
                        Resume
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleCancel(donation.id)}
                        disabled={managingId === donation.id}
                      >
                        Cancel
                      </Button>
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
            </Card>
          ))}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/5 p-4">
          <p className="text-sm text-status-rejected">{error}</p>
        </div>
      )}
    </div>
  );
}
