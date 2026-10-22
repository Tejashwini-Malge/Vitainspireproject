"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Notice } from "@/components/Notice";
import { OrgNav } from "@/components/OrgNav";
import { VerificationBadge } from "@/components/VerificationBadge";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Me, Member, Org, Project, Role } from "@/lib/types";

const MANAGERS: Role[] = ["OWNER", "ADMIN"];

const EMPTY_FORM = { title: "", summary: "", description: "" };

export default function ProjectsPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>()!;
  const [me, setMe] = useState<Me | null>(null);
  const [org, setOrg] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowBlockers, setRowBlockers] = useState<Record<string, string[]>>({});
  const [rowError, setRowError] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const [m, o, mem, proj] = await Promise.all([
        api<Me>("/auth/me"),
        api<Org>(`/orgs/${id}`),
        api<Member[]>(`/orgs/${id}/members`),
        api<Project[]>(`/orgs/${id}/projects`),
      ]);
      setMe(m);
      setOrg(o);
      setMembers(mem);
      setProjects(proj);
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
      setLoadError(err instanceof Error ? err.message : "Could not load projects.");
    }
  }, [id, router]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [load, router]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api(`/orgs/${id}/projects`, {
        method: "POST",
        body: JSON.stringify({ ...form, description: form.description.trim() || null }),
      });
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  async function onSubmitForReview(project: Project) {
    setBusyId(project.id);
    setRowBlockers((r) => ({ ...r, [project.id]: [] }));
    setRowError((r) => ({ ...r, [project.id]: "" }));
    try {
      await api(`/orgs/${id}/projects/${project.id}/submit-for-review`, { method: "POST" });
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.blockers.length > 0) {
        setRowBlockers((r) => ({ ...r, [project.id]: err.blockers }));
      } else {
        setRowError((r) => ({ ...r, [project.id]: err instanceof Error ? err.message : "Could not submit for review." }));
      }
    } finally {
      setBusyId(null);
    }
  }

  async function onUnpublish(project: Project) {
    setBusyId(project.id);
    try {
      await api(`/orgs/${id}/projects/${project.id}/unpublish`, { method: "POST" });
      await load();
    } catch (err) {
      setRowError((r) => ({ ...r, [project.id]: err instanceof Error ? err.message : "Could not take this offline." }));
    } finally {
      setBusyId(null);
    }
  }

  if (notFound) {
    return <p className="text-muted">This organization was not found, or you are not a member of it.</p>;
  }
  if (loadError) return <Notice kind="error">{loadError}</Notice>;
  if (!me || !org || !members || !projects) return <p className="text-muted">Loading projects…</p>;

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
        <p className="text-muted">Projects are available for NGO organizations.</p>
      ) : (
        <>
          <section aria-labelledby="projects-heading" className="space-y-4">
            <h2 id="projects-heading" className="text-lg font-semibold text-navy">
              Your projects
            </h2>
            <p className="text-sm text-muted">
              A project only appears in the public feed once Imparency has reviewed and published it. Posting a
              project is never required -- an NGO with no projects can still be found and donated to directly.
            </p>
            {projects.length === 0 ? (
              <p className="text-muted">No projects yet.</p>
            ) : (
              <ul className="space-y-6">
                {projects.map((p) => (
                  <li key={p.id} className="space-y-3 rounded-sm border-2 border-line bg-white p-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-medium text-navy">{p.title}</p>
                        <p className="text-sm text-muted">{p.summary}</p>
                      </div>
                      <span
                        className={`text-sm font-medium ${
                          p.status === "PUBLISHED"
                            ? "text-status-approved"
                            : p.status === "PENDING_REVIEW"
                              ? "text-status-pending"
                              : p.status === "CHANGES_REQUESTED"
                                ? "text-status-rejected"
                                : "text-muted"
                        }`}
                      >
                        {p.status === "PUBLISHED"
                          ? "Published"
                          : p.status === "PENDING_REVIEW"
                            ? "Awaiting Imparency review"
                            : p.status === "CHANGES_REQUESTED"
                              ? "Changes requested"
                              : "Draft"}
                      </span>
                    </div>
                    {p.status === "CHANGES_REQUESTED" && p.review_feedback && (
                      <blockquote className="border-l-2 border-line pl-3 text-sm">
                        <span className="font-medium">Reviewer&apos;s note:</span> {p.review_feedback}
                      </blockquote>
                    )}
                    {canManage && (
                      <div className="flex gap-3">
                        {p.status === "PUBLISHED" ? (
                          <button type="button" disabled={busyId === p.id} onClick={() => onUnpublish(p)}
                            className="rounded-sm border-2 border-navy px-4 py-2 text-sm font-display font-medium text-navy disabled:opacity-60">
                            Take offline
                          </button>
                        ) : p.status === "PENDING_REVIEW" ? (
                          <button type="button" disabled={busyId === p.id} onClick={() => onUnpublish(p)}
                            className="rounded-sm border-2 border-navy px-4 py-2 text-sm font-display font-medium text-navy disabled:opacity-60">
                            Withdraw submission
                          </button>
                        ) : (
                          <button type="button" disabled={busyId === p.id} onClick={() => onSubmitForReview(p)}
                            className="rounded-sm bg-teal px-4 py-2 text-sm font-display font-medium text-paper disabled:opacity-60">
                            Submit for review
                          </button>
                        )}
                      </div>
                    )}
                    {rowBlockers[p.id]?.length > 0 && (
                      <div role="alert" className="rounded-sm border-2 border-status-rejected bg-white p-3 text-sm text-status-rejected">
                        <p className="font-medium">This project cannot be submitted for review yet:</p>
                        <ul className="mt-1 list-disc space-y-1 pl-5">
                          {rowBlockers[p.id].map((b) => (
                            <li key={b}>{b}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {rowError[p.id] && (
                      <p role="alert" className="text-sm text-status-rejected">
                        {rowError[p.id]}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {canManage ? (
            <form onSubmit={onCreate} className="space-y-4 border-t border-line pt-8" aria-labelledby="new-heading">
              <h2 id="new-heading" className="text-lg font-semibold text-navy">
                Add a project
              </h2>
              <label className="block">
                <span className="text-sm font-medium">Title</span>
                <input required maxLength={200} value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Short summary (shown in the feed)</span>
                <input required maxLength={500} value={form.summary} onChange={(e) => setForm((f) => ({ ...f, summary: e.target.value }))}
                  className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Description (optional)</span>
                <textarea rows={4} maxLength={5000} value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
              </label>
              <button type="submit" disabled={creating}
                className="rounded-sm bg-navy px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
                {creating ? "Adding…" : "Add project (as draft)"}
              </button>
              {createError && <Notice kind="error">{createError}</Notice>}
            </form>
          ) : (
            <p className="text-sm text-muted">Only owners and admins can manage projects.</p>
          )}

          <p className="border-t border-line pt-6 text-sm">
            <Link href={`/orgs/${id}/donations`} className="text-teal hover:underline">
              See donations received
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
