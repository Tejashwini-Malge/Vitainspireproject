"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError, clearToken, setToken } from "@/lib/api";
import type { Me } from "@/lib/types";

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
      const me = await api<Me>("/auth/me");
      if (!me.is_platform_admin) {
        clearToken();
        setError("This email and password are valid, but the account is not platform staff.");
        return;
      }
      router.push("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 rounded-sm border-2 border-navy bg-navy/5 p-8">
      <div className="space-y-1">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Back office</p>
        <h1 className="text-2xl font-semibold text-navy">Staff sign-in</h1>
        <p className="text-sm text-muted">
          For Imparency reviewers only. Staff access is granted from the command line, never through a form --
          correct credentials alone will not open this area.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" aria-describedby={error ? "admin-login-error" : undefined}>
        <label className="block">
          <span className="text-sm font-medium">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2"
          />
        </label>
        {error && (
          <p id="admin-login-error" role="alert" className="text-sm text-status-rejected">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-sm bg-navy px-4 py-2 font-display font-medium text-paper disabled:opacity-60"
        >
          {busy ? "Checking…" : "Enter the back office"}
        </button>
      </form>
    </div>
  );
}
