"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminNav } from "@/components/admin/AdminNav";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { AdminIndividualDonorRow, ReviewStatus } from "@/lib/types";

const PAN_FILTERS: { value: ReviewStatus | "NONE" | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "APPROVED", label: "Verified" },
  { value: "PENDING_REVIEW", label: "Awaiting review" },
  { value: "REJECTED", label: "Not accepted" },
  { value: "NONE", label: "Not submitted" },
];

function rupees(minor: number): string {
  return `₹${Math.round(minor / 100).toLocaleString("en-IN")}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function panLabel(status: ReviewStatus | null): string {
  if (status === "APPROVED") return "Verified";
  if (status === "PENDING_REVIEW") return "Awaiting review";
  if (status === "REJECTED") return "Not accepted";
  return "Not submitted";
}

function panColor(status: ReviewStatus | null): string {
  if (status === "APPROVED") return "text-status-approved";
  if (status === "REJECTED") return "text-status-rejected";
  return "text-status-pending";
}

export default function AdminIndividualDonorsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<AdminIndividualDonorRow[] | null>(null);
  const [denied, setDenied] = useState(false);
  const [error, setError] = useState("");
  const [panFilter, setPanFilter] = useState<ReviewStatus | "NONE" | "ALL">("ALL");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api<AdminIndividualDonorRow[]>("/admin/individual-donors"));
      setError("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        router.replace("/admin/login");
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setDenied(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not load the directory.");
      setRows([]);
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }
    load();
  }, [load, router]);

  if (denied) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Access denied</h1>
        <p className="text-muted">This page is for platform reviewers. Your account does not have that access.</p>
        <Link href="/dashboard" className="text-teal hover:underline">
          Back to your workspace
        </Link>
      </div>
    );
  }

  const visible = (rows ?? [])
    .filter((r) => (panFilter === "ALL" ? true : panFilter === "NONE" ? r.pan_status === null : r.pan_status === panFilter))
    .filter((r) => r.full_name.toLowerCase().includes(search.trim().toLowerCase()) || r.email.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <div className="max-w-6xl space-y-6">
      <AdminNav />
      <header>
        <h1 className="text-2xl font-semibold text-navy">Individual donors</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          People giving as themselves, not through an organization. CSR and corporate funders are on the{" "}
          <Link href="/admin/donors" className="text-teal hover:underline">
            CSR / funding organisations
          </Link>{" "}
          page.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm">
          PAN status{" "}
          <select value={panFilter} onChange={(e) => setPanFilter(e.target.value as typeof panFilter)}
            className="ml-1 rounded-sm border-2 border-line bg-white px-2 py-1">
            {PAN_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name or email…"
          className="rounded-sm border-2 border-line bg-white px-3 py-1 text-sm" />
        <span className="text-sm text-muted">{rows === null ? "" : `${visible.length} of ${rows.length}`}</span>
      </div>

      {error && <p role="alert" className="text-status-rejected">{error}</p>}

      {rows === null ? (
        <p className="text-muted">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="rounded border border-dashed border-line bg-white p-6 text-center text-muted">
          {search.trim() || panFilter !== "ALL" ? "No donor matches these filters." : "No individual donors have registered yet."}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-2 border-line bg-white text-sm">
            <thead className="bg-paper text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Donor</th>
                <th className="px-3 py-2 font-medium">PAN status</th>
                <th className="px-3 py-2 text-right font-medium">Donations</th>
                <th className="px-3 py-2 text-right font-medium">Total given</th>
                <th className="px-3 py-2 text-right font-medium">NGOs supported</th>
                <th className="px-3 py-2 font-medium">Registered</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.user_id} className="border-t border-line">
                  <td className="px-3 py-2">
                    <p className="font-medium text-navy">{r.full_name}</p>
                    <p className="text-muted">{r.email}</p>
                  </td>
                  <td className={`px-3 py-2 font-medium ${panColor(r.pan_status)}`}>{panLabel(r.pan_status)}</td>
                  <td className="px-3 py-2 text-right">{r.donation_count}</td>
                  <td className="px-3 py-2 text-right">{rupees(r.total_donated_minor)}</td>
                  <td className="px-3 py-2 text-right">{r.ngo_count}</td>
                  <td className="px-3 py-2 text-muted">{formatDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
