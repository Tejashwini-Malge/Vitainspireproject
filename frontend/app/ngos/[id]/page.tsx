"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Globe, LogIn, MessageSquare } from "lucide-react";
import { SectorArt } from "@/components/SectorArt";
import { VerificationBadge } from "@/components/VerificationBadge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { api, ApiError, getToken } from "@/lib/api";
import { DOC_TYPE_LABEL, type PublicNgo } from "@/lib/types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export default function PublicNgoPage() {
  const { id } = useParams<{ id: string }>()!;
  const [data, setData] = useState<PublicNgo | null>(null);
  const [state, setState] = useState<"loading" | "missing" | "error" | "ready">("loading");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(!!getToken());
  }, []);

  useEffect(() => {
    setState("loading");
    api<PublicNgo>(`/public/ngos/${id}`)
      .then((d) => {
        setData(d);
        setState("ready");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setState("missing");
          return;
        }
        setErrorText(err instanceof Error ? err.message : "Could not load this profile.");
        setState("error");
      });
  }, [id]);

  if (state === "loading") return <p className="text-muted">Loading profile…</p>;
  if (state === "missing") {
    return (
      <EmptyState
        title="Profile not available"
        description="This profile does not exist, has not been published, or the organization is not yet verified by Imparency."
      />
    );
  }
  if (state === "error") return <p role="alert" className="text-status-rejected">{errorText}</p>;
  if (!data) return null;

  const { profile } = data;
  return (
    <article className="space-y-10">
      <Card className="flex flex-wrap items-start gap-6 p-6 sm:p-8">
        <div className="h-20 w-20 shrink-0 overflow-hidden rounded-full border-2 border-line">
          <SectorArt sectors={profile.sectors} />
        </div>
        <div className="max-w-2xl space-y-3">
          <VerificationBadge status="APPROVED" />
          {data.verified_at && (
            <p className="-mt-2 font-mono text-xs uppercase tracking-wide text-muted">
              Verified on {formatDate(data.verified_at)}
            </p>
          )}
          <h1 className="text-3xl font-semibold tracking-tight text-navy">{data.name}</h1>
          <p className="text-lg text-ink">{profile.mission}</p>
          {signedIn ? (
            <Link
              href={`/conversations/new?target_org_id=${data.id}`}
              className="mt-1 inline-flex items-center gap-2 rounded-sm bg-teal px-5 py-2.5 text-sm font-display font-medium text-paper shadow-sm transition-all hover:opacity-90 hover:shadow-md"
            >
              <MessageSquare className="h-4 w-4" aria-hidden />
              Message this NGO
            </Link>
          ) : (
            <p className="flex items-center gap-1.5 text-sm text-muted">
              <LogIn className="h-4 w-4" aria-hidden />
              <Link href="/login" className="font-medium text-teal hover:underline">
                Sign in
              </Link>{" "}
              to message this NGO directly.
            </p>
          )}
        </div>
      </Card>

      {profile.about && (
        <section aria-labelledby="about-heading">
          <Card className="space-y-3 p-6 sm:p-8">
            <h2 id="about-heading" className="font-mono text-xs uppercase tracking-[0.18em] text-muted">
              About
            </h2>
            <p className="max-w-2xl whitespace-pre-line text-ink">{profile.about}</p>
          </Card>
        </section>
      )}

      <section aria-labelledby="work-heading">
        <h2 id="work-heading" className="sr-only">
          Work and details
        </h2>
        <Card className="grid gap-6 p-6 sm:p-8 md:grid-cols-3">
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-muted">Sectors</p>
            <p className="mt-1 text-ink">{profile.sectors.join(", ") || "Not provided"}</p>
          </div>
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-muted">Places</p>
            <p className="mt-1 text-ink">{profile.geographies.join(", ") || "Not provided"}</p>
          </div>
          <div>
            <p className="font-mono text-xs uppercase tracking-wide text-muted">Founded</p>
            <p className="mt-1 text-ink">{profile.founded_year ?? "Not provided"}</p>
          </div>
          {profile.website && (
            <div className="md:col-span-3">
              <p className="font-mono text-xs uppercase tracking-wide text-muted">Website</p>
              <a
                href={profile.website}
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1.5 text-teal hover:underline"
              >
                <Globe className="h-4 w-4" aria-hidden />
                {profile.website}
              </a>
            </div>
          )}
        </Card>
      </section>

      <section aria-labelledby="docs-heading" className="space-y-3 border-t-2 border-navy pt-8">
        <h2 id="docs-heading" className="text-lg font-semibold text-navy">
          Reviewed documents
        </h2>
        {data.reviewed_documents.length === 0 ? (
          <EmptyState title="No compliance documents have been reviewed yet." />
        ) : (
          <Card className="divide-y divide-line overflow-hidden">
            {data.reviewed_documents.map((d) => (
              <div key={d.doc_type} className="flex justify-between px-5 py-3">
                <span className="text-ink">{DOC_TYPE_LABEL[d.doc_type]}</span>
                <span className="font-mono text-xs uppercase tracking-wide text-status-approved">
                  Reviewed {formatDate(d.reviewed_at)}
                </span>
              </div>
            ))}
          </Card>
        )}
        <p className="max-w-2xl text-sm text-muted">{data.disclaimer}</p>
      </section>
    </article>
  );
}
