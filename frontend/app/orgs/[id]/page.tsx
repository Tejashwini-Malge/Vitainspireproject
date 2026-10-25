"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { OrgNav } from "@/components/OrgNav";
import { VerificationBadge } from "@/components/VerificationBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Me, Member, Org, Role } from "@/lib/types";

const MANAGERS: Role[] = ["OWNER", "ADMIN"];

export default function OrgPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>()!;
  const [me, setMe] = useState<Me | null>(null);
  const [org, setOrg] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<{ kind: "notfound" | "failed"; message: string } | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("MEMBER");
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      const [m, o, mem] = await Promise.all([
        api<Me>("/auth/me"),
        api<Org>(`/orgs/${id}`),
        api<Member[]>(`/orgs/${id}/members`),
      ]);
      setMe(m);
      setOrg(o);
      setMembers(mem);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        router.replace("/login");
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setError({ kind: "notfound", message: "This organization was not found, or you are not a member of it." });
        return;
      }
      setError({ kind: "failed", message: err instanceof Error ? err.message : "Could not load this organization." });
    }
  }, [id, router]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [load, router]);

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    setAdding(true);
    setAddError(null);
    try {
      await api(`/orgs/${id}/members`, { method: "POST", body: JSON.stringify({ email, role }) });
      setEmail("");
      await load();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Could not add this member.");
    } finally {
      setAdding(false);
    }
  }

  if (error) {
    return (
      <div className="space-y-2">
        <p role="alert" className={error.kind === "notfound" ? "text-muted" : "text-status-rejected"}>
          {error.message}
        </p>
      </div>
    );
  }
  if (!me || !org || !members) return <p className="text-muted">Loading organization…</p>;

  const myRole = members.find((m) => m.user_id === me.id)?.role;
  const canManage = myRole !== undefined && MANAGERS.includes(myRole);

  return (
    <div className="space-y-10">
      <div className="space-y-3">
        <PageHeader
          eyebrow={org.org_type}
          title={org.name}
          description={<VerificationBadge status={org.verification_status} />}
        />
        {org.verification_status === "REJECTED" && org.verification_reason && (
          <p className="text-sm text-status-rejected">Reason given by the reviewer: {org.verification_reason}</p>
        )}
        <OrgNav orgId={id} showNgoTabs={org.org_type === "NGO"} />
      </div>

      <section aria-labelledby="members-heading" className="space-y-4">
        <h2 id="members-heading" className="text-lg font-semibold text-navy">
          Members
        </h2>
        <Card className="divide-y divide-line">
          {members.map((m) => (
            <div key={m.user_id} className="flex justify-between px-4 py-3">
              <span>
                {m.full_name} <span className="text-sm text-muted">{m.email}</span>
              </span>
              <span className="text-sm font-medium">{m.role}</span>
            </div>
          ))}
        </Card>
      </section>

      {canManage ? (
        <section aria-labelledby="add-heading" className="space-y-4 border-t border-line pt-8">
          <h2 id="add-heading" className="text-lg font-semibold text-navy">
            Add a member
          </h2>
          <p className="text-sm text-muted">The person must already have an account. Invitations by email come later.</p>
          <form onSubmit={onAdd} className="grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-end">
            <label className="block">
              <span className="text-sm font-medium">Email</span>
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">Role</span>
              <select value={role} onChange={(e) => setRole(e.target.value as Role)}
                className="mt-1 w-full rounded-sm border border-line bg-[#FFFDF7] px-3 py-2 text-ink">
                <option value="MEMBER">Member</option>
                <option value="ADMIN">Admin</option>
                {myRole === "OWNER" && <option value="OWNER">Owner</option>}
              </select>
            </label>
            <Button type="submit" disabled={adding}>
              {adding ? "Adding…" : "Add"}
            </Button>
          </form>
          {addError && (
            <p role="alert" className="text-sm text-status-rejected">
              {addError}
            </p>
          )}
        </section>
      ) : (
        <p className="text-sm text-muted">Only owners and admins can change membership.</p>
      )}
    </div>
  );
}
