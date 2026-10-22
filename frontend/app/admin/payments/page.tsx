"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminNav } from "@/components/admin/AdminNav";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { AdminPaymentRow } from "@/lib/types";

type PageState = "loading" | "error" | "denied" | "ready";

function statusBadgeClass(status: string): string {
  if (status === "COMPLETED") return "bg-teal/10 text-teal";
  if (status === "INITIATED") return "bg-yellow-100 text-yellow-700";
  return "bg-status-rejected/10 text-status-rejected";
}

export default function AdminPaymentsPage() {
  const router = useRouter();
  const [state, setState] = useState<PageState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [payments, setPayments] = useState<AdminPaymentRow[]>([]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }

    async function loadData() {
      try {
        setState("loading");
        const rows = await api<AdminPaymentRow[]>("/admin/payments");
        setPayments(rows);
        setState("ready");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/admin/login");
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          setState("denied");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load payments");
        setState("error");
      }
    }

    loadData();
  }, [router]);

  if (state === "denied") {
    return (
      <div className="space-y-4">
        <AdminNav />
        <h1 className="text-2xl font-semibold text-navy">Payment Transactions</h1>
        <p role="alert" className="text-status-rejected">Access denied. Admin access required.</p>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="space-y-4">
        <AdminNav />
        <h1 className="text-2xl font-semibold text-navy">Payment Transactions</h1>
        <p role="alert" className="text-status-rejected">{error}</p>
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div className="space-y-4">
        <AdminNav />
        <h1 className="text-2xl font-semibold text-navy">Payment Transactions</h1>
        <p className="text-muted">Loading payments...</p>
      </div>
    );
  }

  const completedPayments = payments.filter((p) => p.status === "COMPLETED");
  const initiatedPayments = payments.filter((p) => p.status === "INITIATED");
  const failedPayments = payments.filter((p) => p.status === "FAILED");
  const totalProcessed = completedPayments.reduce((sum, p) => sum + p.amount_minor, 0);
  const recurringCount = payments.filter((p) => p.is_recurring).length;

  return (
    <div className="space-y-8">
      <AdminNav />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Payment Transactions</h1>
        <p className="max-w-2xl text-sm text-muted">
          Transactions through the payment-gateway flow only. Direct NGO donations and campaign pledges are
          recorded separately and are not shown here.
        </p>
      </header>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-lg border-2 border-teal bg-teal/5 p-6">
          <p className="text-sm font-medium text-muted">Total Processed</p>
          <p className="mt-2 text-3xl font-bold text-teal">
            ₹{(totalProcessed / 100000).toFixed(1)}L
          </p>
          <p className="mt-1 text-xs text-muted">{completedPayments.length} transactions</p>
        </div>

        <div className="rounded-lg border-2 border-green-500 bg-green-50 p-6">
          <p className="text-sm font-medium text-muted">Completed</p>
          <p className="mt-2 text-3xl font-bold text-green-600">
            {completedPayments.length}
          </p>
          <p className="mt-1 text-xs text-muted">
            {((completedPayments.length / (payments.length || 1)) * 100).toFixed(0)}%
          </p>
        </div>

        <div className="rounded-lg border-2 border-yellow-500 bg-yellow-50 p-6">
          <p className="text-sm font-medium text-muted">Initiated</p>
          <p className="mt-2 text-3xl font-bold text-yellow-600">
            {initiatedPayments.length}
          </p>
        </div>

        <div className="rounded-lg border-2 border-red-500 bg-red-50 p-6">
          <p className="text-sm font-medium text-muted">Failed</p>
          <p className="mt-2 text-3xl font-bold text-red-600">
            {failedPayments.length}
          </p>
        </div>
      </div>

      {/* Recurring Donations Info */}
      <div className="rounded-lg border-2 border-blue-300 bg-blue-50 p-6">
        <h3 className="font-semibold text-blue-900">Recurring Donations</h3>
        <p className="mt-2 text-sm text-blue-800">
          {recurringCount} active recurring donation subscriptions generating
          consistent monthly revenue
        </p>
      </div>

      {/* Payments Table */}
      {payments.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-line bg-paper p-8 text-center">
          <p className="text-muted">No payment records yet</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border-2 border-line bg-white">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line bg-paper">
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Donor</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Campaign / NGO</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Amount</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Status</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Type</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Date</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Transaction ID</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((payment) => (
                <tr key={payment.id} className="border-b border-line hover:bg-paper">
                  <td className="px-4 py-3 text-sm">
                    <p className="font-medium text-navy">{payment.donor_name}</p>
                    <p className="text-xs text-muted">{payment.donor_email}</p>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <p className="text-navy">{payment.campaign_title ?? "—"}</p>
                    <p className="text-xs text-muted">{payment.ngo_name ?? ""}</p>
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-navy">
                    ₹{(payment.amount_minor / 100).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusBadgeClass(payment.status)}`}>
                      {payment.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-navy">
                    {payment.is_recurring ? "Recurring" : "One-time"}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">
                    {new Date(payment.created_at).toLocaleDateString("en-IN")}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted">
                    {payment.gateway_payment_id ? `${payment.gateway_payment_id.slice(0, 12)}...` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
