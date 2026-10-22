"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SectorArt } from "@/components/SectorArt";
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
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Profile not available</h1>
        <p className="text-muted">
          This profile does not exist, has not been published, or the organization is not yet verified by Imparency.
        </p>
      </div>
    );
  }
  if (state === "error") return <p role="alert" className="text-status-rejected">{errorText}</p>;
  if (!data) return null;

  const { profile } = data;
  return (
    <article className="space-y-10">
      <header className="flex flex-wrap items-start gap-6">
        <div className="h-20 w-20 shrink-0 overflow-hidden rounded-full border-2 border-line">
          <SectorArt sectors={profile.sectors} />
        </div>
        <div className="max-w-2xl space-y-3">
          <p className="text-sm font-medium text-status-approved">
            Verified by Imparency{data.verified_at ? ` on ${formatDate(data.verified_at)}` : ""}
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-navy">{data.name}</h1>
          <p className="text-lg">{profile.mission}</p>
          {signedIn ? (
            <Link
              href={`/conversations/new?target_org_id=${data.id}`}
              className="inline-block rounded-sm bg-teal px-4 py-2 text-sm font-display font-medium text-paper"
            >
              Message this NGO
            </Link>
          ) : (
            <p className="text-sm text-muted">
              <Link href="/login" className="text-teal hover:underline">
                Sign in
              </Link>{" "}
              to message this NGO directly.
            </p>
          )}
        </div>
      </header>

      {profile.about && (
        <section aria-labelledby="about-heading" className="space-y-3">
          <h2 id="about-heading" className="text-lg font-semibold text-navy">
            About
          </h2>
          <p className="max-w-2xl whitespace-pre-line">{profile.about}</p>
        </section>
      )}

      <section aria-labelledby="work-heading" className="grid gap-6 md:grid-cols-3">
        <h2 id="work-heading" className="sr-only">
          Work and details
        </h2>
        <div>
          <p className="text-sm font-medium text-muted">Sectors</p>
          <p className="mt-1">{profile.sectors.join(", ") || "Not provided"}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-muted">Places</p>
          <p className="mt-1">{profile.geographies.join(", ") || "Not provided"}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-muted">Founded</p>
          <p className="mt-1">{profile.founded_year ?? "Not provided"}</p>
        </div>
        {profile.website && (
          <div className="md:col-span-3">
            <p className="text-sm font-medium text-muted">Website</p>
            <a href={profile.website} rel="noopener noreferrer" className="mt-1 inline-block text-teal hover:underline">
              {profile.website}
            </a>
          </div>
        )}
      </section>

      <section aria-labelledby="docs-heading" className="space-y-3 border-t border-line pt-8">
        <h2 id="docs-heading" className="text-lg font-semibold text-navy">
          Reviewed documents
        </h2>
        {data.reviewed_documents.length === 0 ? (
          <p className="text-muted">No compliance documents have been reviewed yet.</p>
        ) : (
          <ul className="divide-y-2 divide-line rounded-sm border-2 border-line bg-white">
            {data.reviewed_documents.map((d) => (
              <li key={d.doc_type} className="flex justify-between px-4 py-3">
                <span>{DOC_TYPE_LABEL[d.doc_type]}</span>
                <span className="text-sm text-muted">Reviewed {formatDate(d.reviewed_at)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="max-w-2xl text-sm text-muted">{data.disclaimer}</p>
      </section>
    </article>
  );
}
