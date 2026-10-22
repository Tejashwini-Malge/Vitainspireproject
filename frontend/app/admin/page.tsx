"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminNav } from "@/components/admin/AdminNav";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import { VerificationBadge } from "@/components/VerificationBadge";
import type { Me, Org, VerificationAssist } from "@/lib/types";

type Denied = { kind: "denied" } | { kind: "error"; message: string } | null;

export default function AdminPage() {
  const router = useRouter();
  const [queue, setQueue] = useState<Org[] | null>(null);
  const [denied, setDenied] = useState<Denied>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [assist, setAssist] = useState<Record<string, VerificationAssist | "loading" | "error">>({});

  async function loadQueue() {
    try {
      setQueue(await api<Org[]>("/admin/verification-queue"));
      setDenied(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        router.replace("/admin/login");
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setDenied({ kind: "denied" });
        return;
      }
      setDenied({ kind: "error", message: err instanceof Error ? err.message : "Could not load the queue." });
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }
    api<Me>("/auth/me")
      .then(() => loadQueue())
      .catch(() => router.replace("/admin/login"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function loadAssist(orgId: string) {
    setAssist((a) => ({ ...a, [orgId]: "loading" }));
    try {
      const result = await api<VerificationAssist>(`/admin/organizations/${orgId}/ai-assist`);
      setAssist((a) => ({ ...a, [orgId]: result }));
    } catch {
      setAssist((a) => ({ ...a, [orgId]: "error" }));
    }
  }

  async function decide(org: Org, decision: "APPROVED" | "REJECTED") {
    const reason = (reasons[org.id] ?? "").trim();
    if (decision === "REJECTED" && !reason) {
      setRowError((r) => ({ ...r, [org.id]: "Write the reason the organization is not verified. It is shown to them." }));
      return;
    }
    setBusyId(org.id);
    setRowError((r) => ({ ...r, [org.id]: "" }));
    try {
      await api(`/admin/organizations/${org.id}/verification`, {
        method: "POST",
        body: JSON.stringify({ decision, reason: decision === "REJECTED" ? reason : undefined }),
      });
      await loadQueue();
    } catch (err) {
      setRowError((r) => ({ ...r, [org.id]: err instanceof Error ? err.message : "Decision failed." }));
    } finally {
      setBusyId(null);
    }
  }

  if (denied?.kind === "denied") {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Access denied</h1>
        <p className="text-muted">The verification queue is for platform reviewers. Your account does not have that access.</p>
        <Link href="/dashboard" className="text-teal hover:underline">
          Back to your workspace
        </Link>
      </div>
    );
  }
  if (denied?.kind === "error") return <p role="alert" className="text-status-rejected">{denied.message}</p>;
  if (!queue) return <p className="text-muted">Loading verification queue…</p>;

  return (
    <div className="space-y-8">
      <AdminNav />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Admin Dashboard</h1>
      </header>
      {queue.length === 0 ? (
        <p className="text-muted">No organizations are waiting for verification.</p>
      ) : (
        <ul className="space-y-6">
          {queue.map((org) => (
            <li key={org.id} className="space-y-3 rounded-sm border-2 border-line bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-navy">{org.name}</p>
                  <p className="text-sm text-muted">{org.org_type}</p>
                </div>
                <VerificationBadge status={org.verification_status} />
              </div>

              <AssistPanel state={assist[org.id]} onLoad={() => loadAssist(org.id)} />

              <label className="block">
                <span className="text-sm font-medium">Reason (required to reject; shown to the organization)</span>
                <textarea
                  rows={2}
                  value={reasons[org.id] ?? ""}
                  onChange={(e) => setReasons((r) => ({ ...r, [org.id]: e.target.value }))}
                  className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2"
                />
              </label>
              <div className="flex gap-3">
                <button type="button" disabled={busyId === org.id} onClick={() => decide(org, "APPROVED")}
                  className="rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
                  Approve
                </button>
                <button type="button" disabled={busyId === org.id} onClick={() => decide(org, "REJECTED")}
                  className="rounded-sm border-2 border-status-rejected px-4 py-2 font-display font-medium text-status-rejected disabled:opacity-60">
                  Reject
                </button>
              </div>
              {rowError[org.id] && (
                <p role="alert" className="text-sm text-status-rejected">
                  {rowError[org.id]}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AssistPanel({
  state,
  onLoad,
}: {
  state: VerificationAssist | "loading" | "error" | undefined;
  onLoad: () => void;
}) {
  if (state === undefined) {
    return (
      <button type="button" onClick={onLoad} className="text-sm font-medium text-teal hover:underline">
        Draft a reviewer summary (AI-assisted)
      </button>
    );
  }
  if (state === "loading") return <p className="text-sm text-muted">Drafting summary…</p>;
  if (state === "error") return <p className="text-sm text-status-rejected">Could not draft a summary.</p>;

  return (
    <div className="space-y-2 rounded-sm border-2 border-dashed border-line bg-paper p-4 text-sm">
      <p>{state.summary}</p>
      {state.flags.length > 0 && (
        <ul className="list-disc space-y-1 pl-5">
          {state.flags.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">
        {state.disclaimer} Sources: {state.sources.join(", ")}.
      </p>
    </div>
  );
}
