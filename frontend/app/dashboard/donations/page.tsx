"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Payment, Me } from "@/lib/types";

type PageState = "loading" | "error" | "ready";

interface PaymentWithReceipt extends Payment {
  receipt_url?: string;
}

export default function DonationHistoryPage() {
  const router = useRouter();
  const [state, setState] = useState<PageState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [payments, setPayments] = useState<PaymentWithReceipt[]>([]);

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

        // In a real app, would fetch user's payments
        // For now, show empty state
        setPayments([]);
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

  const completedPayments = payments.filter((p) => p.status === "COMPLETED");
  const totalDonated = completedPayments.reduce((sum, p) => sum + p.amount_minor, 0);

  if (state === "error") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-navy">Donation History</h1>
        <p role="alert" className="text-status-rejected">{error}</p>
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-navy">Donation History</h1>
        <p className="text-muted">Loading your donations...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-navy">Donation History</h1>
        <p className="mt-2 text-muted">
          View and manage all your donations
        </p>
      </div>

      {/* Summary Cards */}
      {payments.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-lg border-2 border-line bg-white p-6">
            <p className="text-sm text-muted">Total Donations</p>
            <p className="mt-2 text-3xl font-bold text-teal">
              ₹{(totalDonated / 100).toLocaleString()}
            </p>
          </div>
          <div className="rounded-lg border-2 border-line bg-white p-6">
            <p className="text-sm text-muted">Completed Donations</p>
            <p className="mt-2 text-3xl font-bold text-navy">
              {completedPayments.length}
            </p>
          </div>
          <div className="rounded-lg border-2 border-line bg-white p-6">
            <p className="text-sm text-muted">Pending Donations</p>
            <p className="mt-2 text-3xl font-bold text-yellow-600">
              {payments.filter((p) => p.status === "PENDING").length}
            </p>
          </div>
        </div>
      )}

      {/* Donations List */}
      {payments.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-line bg-paper p-8 text-center">
          <div className="mb-4 text-4xl">🎁</div>
          <h2 className="mb-2 font-semibold text-navy">No Donations Yet</h2>
          <p className="mb-6 text-muted">
            Start making a difference by supporting campaigns
          </p>
          <Link
            href="/campaigns"
            className="inline-block rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper hover:bg-teal/90"
          >
            Browse Campaigns
          </Link>
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border-2 border-line bg-white">
          <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-6 md:gap-0 md:border-b md:border-line">
            <div className="text-xs font-semibold text-muted">Campaign</div>
            <div className="text-xs font-semibold text-muted">Amount</div>
            <div className="text-xs font-semibold text-muted">Date</div>
            <div className="text-xs font-semibold text-muted">Status</div>
            <div className="text-xs font-semibold text-muted">Transaction</div>
            <div className="text-xs font-semibold text-muted">Receipt</div>
          </div>

          {payments.map((payment) => (
            <div
              key={payment.id}
              className="grid grid-cols-1 gap-4 border-b border-line p-4 md:grid-cols-6 md:gap-0 md:border-b-0"
            >
              <div className="flex flex-col justify-center">
                <p className="text-sm font-medium text-navy">Campaign</p>
                <p className="truncate text-xs text-muted">{payment.campaign_id}</p>
              </div>
              <div className="flex flex-col justify-center">
                <p className="text-sm font-medium text-navy">
                  ₹{(payment.amount_minor / 100).toLocaleString()}
                </p>
              </div>
              <div className="flex flex-col justify-center">
                <p className="text-sm text-navy">
                  {new Date(payment.created_at).toLocaleDateString("en-IN")}
                </p>
              </div>
              <div className="flex flex-col justify-center">
                <span
                  className={`inline-flex w-fit rounded-full px-2 py-1 text-xs font-medium ${
                    payment.status === "COMPLETED"
                      ? "bg-teal/10 text-teal"
                      : payment.status === "PENDING"
                        ? "bg-yellow-100 text-yellow-700"
                        : payment.status === "FAILED"
                          ? "bg-status-rejected/10 text-status-rejected"
                          : "bg-gray-100 text-gray-700"
                  }`}
                >
                  {payment.status}
                </span>
              </div>
              <div className="flex flex-col justify-center">
                <p className="truncate font-mono text-xs text-muted">
                  {payment.gateway_payment_id?.slice(0, 12) || "—"}
                </p>
              </div>
              <div className="flex flex-col justify-center">
                {payment.status === "COMPLETED" && payment.receipt_url ? (
                  <Link
                    href={payment.receipt_url}
                    className="text-xs font-medium text-teal hover:underline"
                  >
                    View Receipt
                  </Link>
                ) : payment.status === "COMPLETED" ? (
                  <button className="text-xs font-medium text-teal hover:underline">
                    Get Receipt
                  </button>
                ) : (
                  <span className="text-xs text-muted">—</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick Links */}
      <div className="rounded-lg border-2 border-line bg-paper p-6">
        <h3 className="mb-4 font-semibold text-navy">Quick Links</h3>
        <div className="flex flex-col gap-2">
          <Link href="/campaigns" className="text-sm text-teal hover:underline">
            → Browse more campaigns to donate
          </Link>
          <Link
            href="/dashboard/recurring-donations"
            className="text-sm text-teal hover:underline"
          >
            → Manage recurring donations
          </Link>
          <Link href="/dashboard" className="text-sm text-teal hover:underline">
            → Back to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
