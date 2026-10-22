"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError, setToken } from "@/lib/api";
import type { Org, OrgType } from "@/lib/types";

type GivingAs = "INDIVIDUAL" | "CSR";

export default function RegisterDonorPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [givingAs, setGivingAs] = useState<GivingAs>("INDIVIDUAL");
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
      const org_type: OrgType = givingAs;
      const name = givingAs === "INDIVIDUAL" ? fullName : orgName;
      await api<Org>("/orgs", { method: "POST", body: JSON.stringify({ name, org_type }) });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server. Try again.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold text-navy">Register as a donor or CSR team</h1>
        <p className="text-muted">
          This keeps a record of what you&apos;ve given and who to. It&apos;s never required to
          donate once -- you can always do that below without an account.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" aria-describedby={error ? "donor-register-error" : undefined}>
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

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">You&apos;re giving as</legend>
          <label className="flex items-center gap-2">
            <input type="radio" name="givingAs" checked={givingAs === "INDIVIDUAL"} onChange={() => setGivingAs("INDIVIDUAL")} />
            <span>Just me</span>
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="givingAs" checked={givingAs === "CSR"} onChange={() => setGivingAs("CSR")} />
            <span>A company or CSR team</span>
          </label>
        </fieldset>

        {givingAs === "CSR" && (
          <label className="block">
            <span className="text-sm font-medium">Organization name</span>
            <input required minLength={2} value={orgName} onChange={(e) => setOrgName(e.target.value)}
              className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2" />
          </label>
        )}

        {error && (
          <p id="donor-register-error" role="alert" className="text-sm text-status-rejected">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}
          className="w-full rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60">
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="text-sm text-muted">
        Registering an NGO instead?{" "}
        <Link href="/register/ngo" className="font-medium text-teal hover:underline">
          Register your NGO
        </Link>
        .
      </p>
    </div>
  );
}
