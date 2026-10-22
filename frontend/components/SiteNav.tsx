"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken, getToken, onAuthChanged } from "@/lib/api";
import type { Org } from "@/lib/types";

export function SiteNav() {
  const router = useRouter();
  const pathname = usePathname();
  // undefined = not checked yet, so nothing auth-gated renders before we know (avoids a flash
  // of "My account" for a signed-out visitor, or of nothing for a signed-in one).
  const [orgs, setOrgs] = useState<Org[] | undefined | null>(undefined);

  useEffect(() => {
    let cancelled = false;

    function refresh() {
      if (!getToken()) {
        setOrgs(null);
        return;
      }
      api<Org[]>("/orgs")
        .then((o) => {
          if (!cancelled) setOrgs(o);
        })
        .catch(() => {
          // Token rejected or request failed -- treat as signed out rather than guessing a role.
          if (!cancelled) setOrgs(null);
        });
    }

    refresh();
    const unsubscribe = onAuthChanged(refresh);
    return () => {
      cancelled = true;
      unsubscribe();
    };
    // Re-check on every route change too: a sign-in on /login redirects to /dashboard without
    // a full page load, so the nav would otherwise keep showing the signed-out state.
  }, [pathname]);

  const signedIn = orgs !== null && orgs !== undefined;
  const isNgo = Array.isArray(orgs) && orgs.some((o) => o.org_type === "NGO");
  const showFeed = signedIn && !isNgo;

  function signOut() {
    clearToken();
    router.push("/");
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm font-medium">
      <Link href="/#ngos" className="text-navy hover:text-teal hover:underline">
        Browse NGOs
      </Link>
      {showFeed && (
        <Link href="/feed" className="text-navy hover:text-teal hover:underline">
          Your feed
        </Link>
      )}
      {!signedIn && (
        <Link href="/register" className="text-navy hover:text-teal hover:underline">
          Register
        </Link>
      )}
      {signedIn && (
        <Link href="/dashboard" className="text-navy hover:text-teal hover:underline">
          My account
        </Link>
      )}
      {signedIn ? (
        <button
          onClick={signOut}
          className="rounded-sm border-2 border-navy px-3 py-1.5 text-navy hover:bg-navy hover:text-paper"
        >
          Sign out
        </button>
      ) : (
        <Link
          href="/login"
          className="rounded-sm border-2 border-navy px-3 py-1.5 text-navy hover:bg-navy hover:text-paper"
        >
          Sign in
        </Link>
      )}
    </div>
  );
}
