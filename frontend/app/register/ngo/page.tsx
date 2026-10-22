"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError, setToken } from "@/lib/api";
import type { Org } from "@/lib/types";

export default function RegisterNgoPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ full_name: fullName, email, password }),
      });
      const session = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(session.access_token);
      const org = await api<Org>("/orgs", {
        method: "POST",
        body: JSON.stringify({ name: orgName, org_type: "NGO" }),
      });
      router.push(`/orgs/${org.id}/profile-setup`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server. Try again.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold text-navy">Register your NGO</h1>
        <p className="text-muted">
          One account, one organization -- this creates both. A reviewer still has to verify your
          registration before your profile can go public; that review is what makes the
          &ldquo;verified&rdquo; label mean something.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" aria-describedby={error ? "ngo-register-error" : undefined}>
        <label className="block">
          <span className="text-sm font-medium">Your name</span>
          <input required value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name"
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email"
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Password (12 characters or more)</span>
          <input type="password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password" className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">NGO name</span>
          <input required minLength={2} value={orgName} onChange={(e) => setOrgName(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
        </label>
        {error && (
          <p id="ngo-register-error" role="alert" className="text-sm text-status-rejected">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}
          className="w-full rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
          {busy ? "Creating…" : "Register NGO"}
        </button>
      </form>
      <p className="text-sm text-muted">
        Giving instead of registering an NGO?{" "}
        <Link href="/register/donor" className="font-medium text-teal hover:underline">
          Register as a donor or CSR team
        </Link>
        .
      </p>
    </div>
  );
}
