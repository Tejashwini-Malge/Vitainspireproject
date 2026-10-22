"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Notice } from "@/components/Notice";
import { OrgNav } from "@/components/OrgNav";
import { ReviewBadge } from "@/components/ReviewBadge";
import { VerificationBadge } from "@/components/VerificationBadge";
import { api, ApiError, clearToken, downloadFile, getToken } from "@/lib/api";
import { DOC_TYPE_LABEL, type Decision, type DocumentType, type Me, type Member, type Org, type OrgDocument, type Role } from "@/lib/types";

const MANAGERS: Role[] = ["OWNER", "ADMIN"];
const DOC_TYPES = Object.keys(DOC_TYPE_LABEL) as DocumentType[];
const ACCEPT = "application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png";

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function statusCopy(doc: OrgDocument): string {
  if (doc.review_status === "PENDING_REVIEW") return "Imparency has not checked this document yet.";
  if (doc.review_status === "APPROVED") {
    return doc.latest_decision ? `Reviewed and approved on ${formatDate(doc.latest_decision.decided_at)}.` : "Reviewed and approved.";
  }
  return "Not accepted. Read the reviewer's note, then upload a corrected file.";
}

export default function DocumentsPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>()!;
  const [me, setMe] = useState<Me | null>(null);
  const [org, setOrg] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [docs, setDocs] = useState<OrgDocument[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [docType, setDocType] = useState<DocumentType>("REGISTRATION");
  const [title, setTitle] = useState("");
  const [expiry, setExpiry] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadOk, setUploadOk] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const [busyDoc, setBusyDoc] = useState<string | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<Record<string, Decision[] | "loading" | "error">>({});

  const load = useCallback(async () => {
    try {
      const [m, o, mem, d] = await Promise.all([
        api<Me>("/auth/me"),
        api<Org>(`/orgs/${id}`),
        api<Member[]>(`/orgs/${id}/members`),
        api<OrgDocument[]>(`/orgs/${id}/documents`),
      ]);
      setMe(m);
      setOrg(o);
      setMembers(mem);
      setDocs(d);
      setLoadError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        return;
      }
      setLoadError(err instanceof Error ? err.message : "Could not load documents.");
    }
  }, [id, router]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [load, router]);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setUploadError("Choose a PDF, JPEG or PNG file to upload.");
      return;
    }
    setUploading(true);
    setUploadOk(null);
    setUploadError(null);
    try {
      const form = new FormData();
      form.set("doc_type", docType);
      form.set("title", title.trim());
      if (expiry) form.set("valid_until", expiry);
      form.set("file", file);
      await api<OrgDocument>(`/orgs/${id}/documents`, { method: "POST", body: form });
      setUploadOk("Uploaded. It is now awaiting review and is private to your organization.");
      setTitle("");
      setExpiry("");
      setFile(null);
      setFileInputKey((k) => k + 1);
      await load();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed. Try again.");
    } finally {
      setUploading(false);
    }
  }

  async function onDownload(doc: OrgDocument) {
    setBusyDoc(doc.id);
    setRowError((r) => ({ ...r, [doc.id]: "" }));
    try {
      await downloadFile(`/orgs/${id}/documents/${doc.id}/download`, doc.original_filename);
    } catch (err) {
      setRowError((r) => ({ ...r, [doc.id]: err instanceof Error ? err.message : "Download failed." }));
    } finally {
      setBusyDoc(null);
    }
  }

  async function toggleHistory(doc: OrgDocument) {
    if (history[doc.id] && history[doc.id] !== "error") {
      setHistory((h) => {
        const next = { ...h };
        delete next[doc.id];
        return next;
      });
      return;
    }
    setHistory((h) => ({ ...h, [doc.id]: "loading" }));
    try {
      const rows = await api<Decision[]>(`/orgs/${id}/documents/${doc.id}/decisions`);
      setHistory((h) => ({ ...h, [doc.id]: rows }));
    } catch {
      setHistory((h) => ({ ...h, [doc.id]: "error" }));
    }
  }

  if (notFound) return <p className="text-muted">This organization was not found, or you are not a member of it.</p>;
  if (loadError) return <Notice kind="error">{loadError}</Notice>;
  if (!me || !org || !members || !docs) return <p className="text-muted">Loading documents…</p>;

  const myRole = members.find((m) => m.user_id === me.id)?.role;
  const canManage = myRole !== undefined && MANAGERS.includes(myRole);
  const isNgo = org.org_type === "NGO";

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">{org.name}</h1>
        <p className="text-muted">
          {org.org_type} · <VerificationBadge status={org.verification_status} />
        </p>
        <OrgNav orgId={id} showNgoTabs={isNgo} />
      </header>

      {!isNgo ? (
        <p className="text-muted">Compliance documents are collected for NGO organizations.</p>
      ) : (
        <>
          <section aria-labelledby="docs-intro" className="space-y-2">
            <h2 id="docs-intro" className="text-lg font-semibold text-navy">
              Compliance documents
            </h2>
            <p className="max-w-2xl text-sm text-muted">
              Documents are private. Only your team and Imparency reviewers can open them. A document is marked approved
              only after a reviewer has checked it. An approved document does not mean your claims are proven; it means
              this specific file was checked.
            </p>
          </section>

          {docs.length === 0 ? (
            <p className="rounded border border-dashed border-line bg-white p-6 text-muted">
              No documents yet.{" "}
              {canManage ? "Upload your registration certificate and tax-exemption records below to start review." : "Owners and admins can upload documents."}
            </p>
          ) : (
            <ul className="space-y-4" aria-label="Uploaded documents">
              {docs.map((doc) => (
                <li key={doc.id} className="space-y-3 rounded-sm border-2 border-line bg-white p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-navy">{doc.title}</p>
                      <p className="text-sm text-muted">
                        {DOC_TYPE_LABEL[doc.doc_type]} · {doc.original_filename} · {formatSize(doc.size_bytes)} · uploaded{" "}
                        {formatDate(doc.uploaded_at)}
                      </p>
                      {doc.valid_until_stated && (
                        <p className="text-sm text-muted">
                          Expiry stated by your organization: {formatDate(doc.valid_until_stated)} (not verified by Imparency)
                        </p>
                      )}
                    </div>
                    <ReviewBadge status={doc.review_status} />
                  </div>
                  <p className="text-sm">{statusCopy(doc)}</p>
                  {doc.latest_decision && (
                    <blockquote className="border-l-2 border-line pl-3 text-sm">
                      <span className="font-medium">Reviewer's note:</span> {doc.latest_decision.reason}
                    </blockquote>
                  )}
                  <div className="flex flex-wrap gap-3">
                    <button type="button" onClick={() => onDownload(doc)} disabled={busyDoc === doc.id}
                      className="rounded-sm border-2 border-navy px-3 py-1.5 text-sm font-display font-medium text-navy disabled:opacity-60">
                      {busyDoc === doc.id ? "Preparing…" : "Download"}
                    </button>
                    <button type="button" onClick={() => toggleHistory(doc)}
                      aria-expanded={!!history[doc.id]}
                      className="rounded-sm border-2 border-line px-3 py-1.5 text-sm font-display font-medium text-navy">
                      {history[doc.id] ? "Hide review history" : "Review history"}
                    </button>
                  </div>
                  {rowError[doc.id] && <Notice kind="error">{rowError[doc.id]}</Notice>}
                  {history[doc.id] === "loading" && <p className="text-sm text-muted">Loading history…</p>}
                  {history[doc.id] === "error" && <Notice kind="error">Could not load the review history.</Notice>}
                  {Array.isArray(history[doc.id]) && (
                    <HistoryList rows={history[doc.id] as Decision[]} />
                  )}
                </li>
              ))}
            </ul>
          )}

          {canManage ? (
            <section aria-labelledby="upload-heading" className="space-y-5 border-t border-line pt-8">
              <h2 id="upload-heading" className="text-lg font-semibold text-navy">
                Upload a document
              </h2>
              <form onSubmit={onUpload} className="grid gap-5 md:grid-cols-2">
                <label className="block">
                  <span className="text-sm font-medium">Document type</span>
                  <select value={docType} onChange={(e) => setDocType(e.target.value as DocumentType)}
                    className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2">
                    {DOC_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {DOC_TYPE_LABEL[t]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-sm font-medium">Title</span>
                  <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="For example: 12A certificate 2024–27"
                    className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
                </label>
                <label className="block">
                  <span className="text-sm font-medium">File (PDF, JPEG or PNG, 10 MB at most)</span>
                  <input key={fileInputKey} type="file" accept={ACCEPT} required
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="mt-1 block w-full text-sm" />
                </label>
                <label className="block">
                  <span className="text-sm font-medium">Expiry date, as shown on the document (optional)</span>
                  <input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)}
                    className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
                </label>
                <div className="md:col-span-2">
                  <button type="submit" disabled={uploading}
                    className="rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
                    {uploading ? "Uploading…" : "Upload document"}
                  </button>
                </div>
              </form>
              {uploadOk && <Notice kind="success">{uploadOk}</Notice>}
              {uploadError && <Notice kind="error">{uploadError}</Notice>}
            </section>
          ) : (
            <p className="text-sm text-muted">Only owners and admins can upload documents.</p>
          )}
        </>
      )}
    </div>
  );
}

function HistoryList({ rows }: { rows: Decision[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted">No reviews yet.</p>;
  return (
    <ol className="space-y-2 text-sm" aria-label="Review history, oldest first">
      {rows.map((r) => (
        <li key={r.id} className="rounded-sm bg-paper p-3">
          <span className="font-medium">{r.decision === "APPROVED" ? "Approved" : "Not accepted"}</span>
          <span className="text-muted"> on {formatDate(r.decided_at)}</span>
          <p className="mt-1">{r.reason}</p>
        </li>
      ))}
    </ol>
  );
}
