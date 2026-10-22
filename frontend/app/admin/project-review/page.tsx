"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AdminNav } from "@/components/admin/AdminNav";
import { Notice } from "@/components/Notice";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { AdminProjectQueueItem } from "@/lib/types";

type Decision = "PUBLISHED" | "CHANGES_REQUESTED";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function ProjectReviewPage() {
  const router = useRouter();
  const [queue, setQueue] = useState<AdminProjectQueueItem[] | null>(null);
  const [denied, setDenied] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [choice, setChoice] = useState<Record<string, Decision>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});

  async function loadQueue() {
    try {
      setQueue(await api<AdminProjectQueueItem[]>("/admin/projects/queue"));
      setLoadError(null);
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
      setLoadError(err instanceof Error ? err.message : "Could not load the review queue.");
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }
    loadQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function onDecide(e: FormEvent, item: AdminProjectQueueItem) {
    e.preventDefault();
    const decision = choice[item.id];
    const reason = (reasons[item.id] ?? "").trim();
    setNotice(null);
    if (!decision) {
      setRowError((r) => ({ ...r, [item.id]: "Choose Publish or Request changes." }));
      return;
    }
    if (decision === "CHANGES_REQUESTED" && !reason) {
      setRowError((r) => ({ ...r, [item.id]: "Write what needs to change. The NGO will see it." }));
      return;
    }
    setBusy(item.id);
    setRowError((r) => ({ ...r, [item.id]: "" }));
    try {
      await api(`/admin/projects/${item.id}/decisions`, {
        method: "POST",
        body: JSON.stringify({ decision, reason: decision === "CHANGES_REQUESTED" ? reason : undefined }),
      });
      setNotice(`Recorded: ${item.title} (${decision === "PUBLISHED" ? "published" : "changes requested"}).`);
      await loadQueue();
    } catch (err) {
      setRowError((r) => ({ ...r, [item.id]: err instanceof Error ? err.message : "Decision failed." }));
    } finally {
      setBusy(null);
    }
  }

  if (denied) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Access denied</h1>
        <p className="text-muted">Project review is for platform reviewers. Your account does not have that access.</p>
        <Link href="/dashboard" className="text-teal hover:underline">
          Back to your workspace
        </Link>
      </div>
    );
  }
  if (loadError) return <Notice kind="error">{loadError}</Notice>;
  if (!queue) return <p className="text-muted">Loading review queue…</p>;

  return (
    <div className="space-y-8">
      <AdminNav />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Project review</h1>
        <p className="max-w-2xl text-sm text-muted">
          A project only goes live once you publish it here. Requesting changes sends it back to the NGO with your
          note; they can edit and submit again. Projects from organizations you belong to are not shown.
        </p>
        <Link href="/admin/projects" className="text-sm text-teal hover:underline">
          All projects
        </Link>
      </header>

      {notice && <Notice kind="success">{notice}</Notice>}

      {queue.length === 0 ? (
        <p className="rounded border border-dashed border-line bg-white p-6 text-muted">No projects are waiting for review.</p>
      ) : (
        <ul className="space-y-6" aria-label="Projects awaiting review">
          {queue.map((item) => (
            <li key={item.id} className="space-y-4 rounded-sm border-2 border-line bg-white p-5">
              <div>
                <p className="font-medium text-navy">
                  {item.org_name} · {item.title}
                </p>
                <p className="text-sm text-muted">{item.summary}</p>
                <p className="text-xs text-muted">Submitted {formatDate(item.created_at)}</p>
              </div>

              <form onSubmit={(e) => onDecide(e, item)} className="space-y-3" aria-label={`Decision for ${item.title}`}>
                <fieldset className="flex flex-wrap gap-6">
                  <legend className="mb-2 text-sm font-medium">Decision</legend>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="radio" name={`decision-${item.id}`} value="PUBLISHED"
                      checked={choice[item.id] === "PUBLISHED"}
                      onChange={() => setChoice((c) => ({ ...c, [item.id]: "PUBLISHED" }))} />
                    Publish
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="radio" name={`decision-${item.id}`} value="CHANGES_REQUESTED"
                      checked={choice[item.id] === "CHANGES_REQUESTED"}
                      onChange={() => setChoice((c) => ({ ...c, [item.id]: "CHANGES_REQUESTED" }))} />
                    Request changes
                  </label>
                </fieldset>
                <label className="block">
                  <span className="text-sm font-medium">Note (required to request changes; shown to the NGO)</span>
                  <textarea rows={2} maxLength={2000} value={reasons[item.id] ?? ""}
                    onChange={(e) => setReasons((r) => ({ ...r, [item.id]: e.target.value }))}
                    className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
                </label>
                <button type="submit" disabled={busy === item.id}
                  className="rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
                  {busy === item.id ? "Recording…" : "Record decision"}
                </button>
                {rowError[item.id] && <Notice kind="error">{rowError[item.id]}</Notice>}
              </form>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
