"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AdminNav } from "@/components/admin/AdminNav";
import { Notice } from "@/components/Notice";
import { api, ApiError, clearToken, downloadFile, getToken } from "@/lib/api";
import { DOC_TYPE_LABEL, type AdminQueueItem, type ReviewStatus } from "@/lib/types";

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentReviewPage() {
  const router = useRouter();
  const [queue, setQueue] = useState<AdminQueueItem[] | null>(null);
  const [denied, setDenied] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [choice, setChoice] = useState<Record<string, ReviewStatus>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});

  async function loadQueue() {
    try {
      setQueue(await api<AdminQueueItem[]>("/admin/documents/queue"));
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

  async function onDecide(e: FormEvent, item: AdminQueueItem) {
    e.preventDefault();
    const decision = choice[item.id];
    const reason = (reasons[item.id] ?? "").trim();
    setNotice(null);
    if (!decision) {
      setRowError((r) => ({ ...r, [item.id]: "Choose Approve or Not accepted." }));
      return;
    }
    if (!reason) {
      setRowError((r) => ({ ...r, [item.id]: "Write a reason. The organization will see it." }));
      return;
    }
    setBusy(item.id);
    setRowError((r) => ({ ...r, [item.id]: "" }));
    try {
      await api(`/admin/documents/${item.id}/decisions`, {
        method: "POST",
        body: JSON.stringify({ decision, reason }),
      });
      setNotice(`Recorded: ${item.title} (${decision === "APPROVED" ? "approved" : "not accepted"}). The decision cannot be changed later.`);
      await loadQueue();
    } catch (err) {
      setRowError((r) => ({ ...r, [item.id]: err instanceof Error ? err.message : "Decision failed." }));
    } finally {
      setBusy(null);
    }
  }

  async function onDownload(item: AdminQueueItem) {
    setBusy(item.id);
    setRowError((r) => ({ ...r, [item.id]: "" }));
    try {
      await downloadFile(`/admin/documents/${item.id}/download`, item.original_filename);
    } catch (err) {
      setRowError((r) => ({ ...r, [item.id]: err instanceof Error ? err.message : "Download failed." }));
    } finally {
      setBusy(null);
    }
  }

  if (denied) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Access denied</h1>
        <p className="text-muted">Document review is for platform reviewers. Your account does not have that access.</p>
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
        <h1 className="text-2xl font-semibold text-navy">Document review</h1>
        <p className="max-w-2xl text-sm text-muted">
          Open each file, check it against what the organization has stated, then record a decision with a reason. A
          decision is final: a rejected file is replaced by a new upload, never edited. Documents from organizations you
          belong to are not shown.
        </p>
      </header>

      {notice && <Notice kind="success">{notice}</Notice>}

      {queue.length === 0 ? (
        <p className="rounded border border-dashed border-line bg-white p-6 text-muted">No documents are waiting for review.</p>
      ) : (
        <ul className="space-y-6" aria-label="Documents awaiting review">
          {queue.map((item) => (
            <li key={item.id} className="space-y-4 rounded-sm border-2 border-line bg-white p-5">
              <div>
                <p className="font-medium text-navy">
                  {item.org_name} · {DOC_TYPE_LABEL[item.doc_type]}
                </p>
                <p className="text-sm text-muted">
                  {item.title} · {item.original_filename} · {formatSize(item.size_bytes)}
                </p>
                {item.valid_until_stated && (
                  <p className="text-sm text-muted">Expiry stated by the organization: {item.valid_until_stated} (unverified)</p>
                )}
              </div>
              <button type="button" onClick={() => onDownload(item)} disabled={busy === item.id}
                className="rounded-sm border-2 border-navy px-3 py-1.5 text-sm font-display font-medium text-navy disabled:opacity-60">
                Download to review
              </button>

              <form onSubmit={(e) => onDecide(e, item)} className="space-y-3" aria-label={`Decision for ${item.title}`}>
                <fieldset className="flex flex-wrap gap-6">
                  <legend className="mb-2 text-sm font-medium">Decision</legend>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="radio" name={`decision-${item.id}`} value="APPROVED"
                      checked={choice[item.id] === "APPROVED"}
                      onChange={() => setChoice((c) => ({ ...c, [item.id]: "APPROVED" }))} />
                    Approve
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="radio" name={`decision-${item.id}`} value="REJECTED"
                      checked={choice[item.id] === "REJECTED"}
                      onChange={() => setChoice((c) => ({ ...c, [item.id]: "REJECTED" }))} />
                    Not accepted
                  </label>
                </fieldset>
                <label className="block">
                  <span className="text-sm font-medium">Reason (required; shown to the organization)</span>
                  <textarea rows={2} maxLength={1000} value={reasons[item.id] ?? ""}
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
