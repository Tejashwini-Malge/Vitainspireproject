"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { AdminDashboard, Me } from "@/lib/types";
import { AdminNav } from "@/components/admin/AdminNav";
import { StatCard } from "@/components/admin/StatCard";
import { MetricCard } from "@/components/admin/MetricCard";
import { CampaignTable } from "@/components/admin/CampaignTable";
import { DonorSegmentChart } from "@/components/admin/DonorSegmentChart";

type PageState = "loading" | "error" | "ready";

export default function AnalyticsPage() {
  const router = useRouter();
  const [state, setState] = useState<PageState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }

    async function loadData() {
      try {
        setState("loading");

        // Verify admin access
        await api<Me>("/auth/me");

        // Load dashboard data
        const data = await api<AdminDashboard>("/admin/analytics/dashboard");
        setDashboard(data);
        setState("ready");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/admin/login");
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          setError("Access denied. You must be a platform admin.");
          setState("error");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
        setState("error");
      }
    }

    loadData();
  }, [router]);

  if (state === "error") {
    return (
      <div className="space-y-4">
        <AdminNav />
        <h1 className="text-2xl font-semibold text-navy">Analytics Dashboard</h1>
        <p role="alert" className="text-status-rejected">{error}</p>
      </div>
    );
  }

  if (state === "loading" || !dashboard) {
    return (
      <div className="space-y-4">
        <AdminNav />
        <h1 className="text-2xl font-semibold text-navy">Analytics Dashboard</h1>
        <p className="text-muted">Loading dashboard…</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <AdminNav />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Analytics Dashboard</h1>
      </header>

      {/* Key Metrics Grid */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-navy">Platform Overview</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <StatCard
            label="Total NGOs"
            value={dashboard.total_ngos}
            subtitle={`${dashboard.verified_ngos} verified`}
            color="teal"
          />
          <StatCard
            label="Active Campaigns"
            value={dashboard.live_campaigns}
            subtitle={`of ${dashboard.total_campaigns} total`}
            color="green"
          />
          <StatCard
            label="Total Fundraising"
            value={`₹${(dashboard.total_fundraising / 100000).toFixed(1)}L`}
            subtitle={`${dashboard.total_donors} donors`}
            color="blue"
          />
        </div>
      </section>

      {/* Email & Queue Health */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-navy">Email & Queue Health</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <MetricCard
            title="Email Engagement"
            metrics={[
              { label: "Open Rate", value: `${dashboard.engagement.open_rate}%` },
              { label: "Click Rate", value: `${dashboard.engagement.click_rate}%` },
              { label: "Bounce Rate", value: `${dashboard.engagement.bounce_rate}%` },
              { label: "Pending", value: dashboard.engagement.total_pending },
              { label: "Failed", value: dashboard.engagement.total_failed },
            ]}
          />
          <MetricCard
            title="Queue Metrics"
            metrics={[
              { label: "Queue Depth", value: dashboard.email_queue_health.queue_depth },
              { label: "Pending", value: dashboard.email_queue_health.pending_count },
              { label: "Failed", value: dashboard.email_queue_health.failed_count },
              {
                label: "Avg Processing",
                value: dashboard.email_queue_health.avg_processing_time_seconds
                  ? `${dashboard.email_queue_health.avg_processing_time_seconds}s`
                  : "—",
              },
            ]}
          />
        </div>
      </section>

      {/* Top Campaigns */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-navy">Top Campaigns by Fundraising</h2>
        <CampaignTable campaigns={dashboard.top_campaigns} />
      </section>

      {/* Donor Segments */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-navy">Donor Segments</h2>
        <DonorSegmentChart segments={dashboard.donor_segments} />
      </section>

      {/* Last Updated */}
      <footer className="border-t border-line pt-4 text-sm text-muted">
        Last updated: {new Date(dashboard.timestamp).toLocaleString()}
      </footer>
    </div>
  );
}
