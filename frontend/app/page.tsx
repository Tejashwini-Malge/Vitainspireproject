"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LedgerHero } from "@/components/LedgerHero";
import { SectorArt } from "@/components/SectorArt";
import { api } from "@/lib/api";
import type { PublicNgo, PublicProject } from "@/lib/types";

export default function Home() {
  const [ngos, setNgos] = useState<PublicNgo[] | null>(null);
  const [feed, setFeed] = useState<PublicProject[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<PublicNgo[]>("/public/ngos"), api<PublicProject[]>("/public/feed")])
      .then(([n, f]) => {
        setNgos(n);
        setFeed(f);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load NGOs."));
  }, []);

  return (
    <div className="space-y-20">
      <section className="grid items-center gap-10 md:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted">A donation ledger, not a charity app</p>
          <h1 className="max-w-2xl text-4xl font-semibold leading-[1.1] tracking-tight text-navy sm:text-5xl">
            Every rupee here leaves a trail you can follow back to a person who checked it.
          </h1>
          <p className="max-w-xl text-lg text-muted">
            Below are NGOs a reviewer at Imparency has actually looked at -- their registration, not just their website.
            Read about one, give if you want to, and leave. No account, no newsletter, no second ask.
          </p>
          <div className="flex flex-wrap gap-4 pt-2">
            <Link href="#ngos" className="rounded-sm bg-teal px-5 py-2.5 font-display font-medium text-paper hover:opacity-90">
              See who&apos;s verified
            </Link>
            <Link
              href="/register/ngo"
              className="rounded-sm border-2 border-navy px-5 py-2.5 font-display font-medium text-navy hover:bg-navy hover:text-paper"
            >
              I run an NGO
            </Link>
          </div>
        </div>
        <div className="hidden justify-self-center md:flex">
          <LedgerHero />
        </div>
      </section>

      <section aria-labelledby="feed-heading" className="space-y-5">
        <div>
          <h2 id="feed-heading" className="text-xl font-semibold text-navy">
            Projects open for donations
          </h2>
          <p className="text-sm text-muted">Posting a project is optional -- most of an NGO&apos;s giving happens with no project attached.</p>
        </div>
        {error && <p role="alert" className="text-status-rejected">{error}</p>}
        {!error && feed === null && <p className="text-muted">Loading…</p>}
        {feed && feed.length === 0 && (
          <p className="rounded-sm border border-dashed border-line bg-white/60 p-5 text-muted">
            No NGO has published a project yet. That&apos;s fine -- you can still donate straight to a verified NGO below.
          </p>
        )}
        {feed && feed.length > 0 && (
          <ul className="grid gap-x-6 gap-y-10 md:grid-cols-2">
            {feed.map((p) => (
              <li key={p.id} className="stub-card">
                <div className="flex gap-4 p-5">
                  <div className="h-14 w-14 shrink-0 overflow-hidden rounded-full border border-line">
                    <SectorArt sectors={p.org_sectors} />
                  </div>
                  <div className="space-y-2">
                    <p className="font-mono text-xs uppercase tracking-wide text-muted">{p.org_name}</p>
                    <h3 className="text-lg font-semibold text-navy">{p.title}</h3>
                    <p className="text-muted">{p.summary}</p>
                  </div>
                </div>
                <div className="stub-tear flex gap-4 p-5 text-sm">
                  <Link href={`/ngos/${p.org_id}`} className="font-medium text-navy hover:underline">
                    Read about {p.org_name}
                  </Link>
                  <Link href={`/donate/${p.org_id}?project=${p.id}`} className="font-medium text-teal hover:underline">
                    Donate to this project
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section id="ngos" aria-labelledby="ngos-heading" className="scroll-mt-10 space-y-5">
        <div>
          <h2 id="ngos-heading" className="text-xl font-semibold text-navy">
            Verified NGOs
          </h2>
          <p className="text-sm text-muted">Each one below cleared a human reviewer, not just a form.</p>
        </div>
        {!error && ngos === null && <p className="text-muted">Loading…</p>}
        {ngos && ngos.length === 0 && (
          <p className="rounded-sm border border-dashed border-line bg-white/60 p-5 text-muted">
            No NGO has been verified and published yet. If you run one,{" "}
            <Link href="/register/ngo" className="font-medium text-teal hover:underline">
              register it
            </Link>{" "}
            -- a reviewer looks at every submission by hand.
          </p>
        )}
        {ngos && ngos.length > 0 && (
          <ul className="divide-y-2 divide-dashed divide-line border-y-2 border-dashed border-line">
            {ngos.map((n) => (
              <li key={n.id} className="flex flex-wrap items-center justify-between gap-4 py-5">
                <div className="flex max-w-lg gap-4">
                  <div className="h-14 w-14 shrink-0 overflow-hidden rounded-full border border-line">
                    <SectorArt sectors={n.profile.sectors} />
                  </div>
                  <div>
                    <p className="font-semibold text-navy">{n.name}</p>
                    <p className="mt-1 text-sm text-muted">{n.profile.mission}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <Link href={`/ngos/${n.id}`} className="font-medium text-navy hover:underline">
                    Read more
                  </Link>
                  <Link href={`/donate/${n.id}`} className="rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper hover:opacity-90">
                    Donate
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid gap-6 border-t-2 border-navy pt-10 md:grid-cols-2" aria-label="Two ways to join">
        <div className="space-y-2">
          <p className="font-mono text-xs uppercase tracking-wide text-muted">If you give</p>
          <h2 className="text-xl font-semibold text-navy">Browsing never turns into a sign-up form.</h2>
          <p className="text-muted">
            Give once above and you&apos;re done. Want a running history of what you&apos;ve given instead?{" "}
            <Link href="/register/donor" className="font-medium text-teal hover:underline">
              Make an account
            </Link>{" "}
            -- it only changes what you can see afterward, never what it costs to donate.
          </p>
        </div>
        <div className="space-y-2">
          <p className="font-mono text-xs uppercase tracking-wide text-muted">If you run an NGO</p>
          <h2 className="text-xl font-semibold text-navy">Your projects are a feed, not a requirement.</h2>
          <p className="text-muted">
            <Link href="/register" className="font-medium text-teal hover:underline">
              Register
            </Link>
            , get verified, and post work when you have it to show. Donors can already find and give to your
            organization directly -- a project page is for when you want to point them at something specific.
          </p>
        </div>
      </section>
    </div>
  );
}
