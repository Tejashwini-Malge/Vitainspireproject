"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
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
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="mx-auto max-w-md space-y-8"
    >
      <PageHeader
        eyebrow="Join Imparency"
        title="Register your NGO"
        description={
          <>
            One account, one organization -- this creates both. A reviewer still has to verify your
            registration before your profile can go public; that review is what makes the
            &ldquo;verified&rdquo; label mean something.
          </>
        }
      />

      <Card className="p-6 sm:p-8">
        <form onSubmit={onSubmit} className="space-y-4" aria-describedby={error ? "ngo-register-error" : undefined}>
          <label className="block">
            <span className="text-sm font-medium text-navy">Your name</span>
            <Input
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              className="mt-1"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-navy">Email</span>
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className="mt-1"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-navy">Password (12 characters or more)</span>
            <Input
              type="password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              className="mt-1"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-navy">NGO name</span>
            <Input
              required
              minLength={2}
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="mt-1"
            />
          </label>
          {error && (
            <p id="ngo-register-error" role="alert" className="text-sm text-status-rejected">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Creating…" : "Register NGO"}
          </Button>
        </form>
      </Card>

      <p className="text-center text-sm text-muted">
        Giving instead of registering an NGO?{" "}
        <Link href="/register/donor" className="font-medium text-teal hover:underline">
          Register as a donor or CSR team
        </Link>
        .
      </p>
    </motion.div>
  );
}
