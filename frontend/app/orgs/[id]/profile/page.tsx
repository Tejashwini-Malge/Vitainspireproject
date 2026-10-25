"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Notice } from "@/components/Notice";
import { OrgNav } from "@/components/OrgNav";
import { VerificationBadge } from "@/components/VerificationBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Me, Member, Org, Profile, Role } from "@/lib/types";

const MANAGERS: Role[] = ["OWNER", "ADMIN"];

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0);
}

interface FormState {
  mission: string;
  about: string;
  vision: string;
  description: string;
  organization_title: string;
  sectors: string;
  geographies: string;
  founded_year: string;
  website: string;
  registration_number: string;
  section_80g_number: string;
}

function toForm(p: Profile | null): FormState {
  return {
    mission: p?.mission ?? "",
    about: p?.about ?? "",
    vision: p?.vision ?? "",
    description: p?.description ?? "",
    organization_title: p?.organization_title ?? "",
    sectors: p?.sectors.join(", ") ?? "",
    geographies: p?.geographies.join(", ") ?? "",
    founded_year: p?.founded_year ? String(p.founded_year) : "",
    website: p?.website ?? "",
    registration_number: p?.registration_number ?? "",
    section_80g_number: p?.section_80g_number ?? "",
  };
}

export default function ProfilePage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>()!;
  const [me, setMe] = useState<Me | null>(null);
  const [org, setOrg] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState<FormState>(toForm(null));
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [publishMessage, setPublishMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, o, mem, p] = await Promise.all([
        api<Me>("/auth/me"),
        api<Org>(`/orgs/${id}`),
        api<Member[]>(`/orgs/${id}/members`),
        api<Profile | null>(`/orgs/${id}/profile`),
      ]);
      setMe(m);
      setOrg(o);
      setMembers(mem);
      setProfile(p);
      setForm(toForm(p));
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
      setLoadError(err instanceof Error ? err.message : "Could not load the profile.");
    }
  }, [id, router]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [load, router]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaved(null);
    setPublishMessage(null);
    setBlockers([]);
    try {
      const body = {
        mission: form.mission,
        about: form.about.trim() || null,
        vision: form.vision.trim() || null,
        description: form.description.trim() || null,
        organization_title: form.organization_title.trim() || null,
        sectors: splitList(form.sectors),
        geographies: splitList(form.geographies),
        founded_year: form.founded_year ? Number(form.founded_year) : null,
        website: form.website.trim() || null,
        registration_number: form.registration_number.trim() || null,
        section_80g_number: form.section_80g_number.trim() || null,
      };
      const p = await api<Profile>(`/orgs/${id}/profile`, { method: "PUT", body: JSON.stringify(body) });
      setProfile(p);
      setForm(toForm(p));
      setSaved(
        p.status === "PUBLISHED"
          ? "Saved. Your public profile now shows these changes."
          : "Saved as a draft. It is not public yet.",
      );
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save the profile.");
    } finally {
      setSaving(false);
    }
  }

  async function onPublish() {
    setPublishing(true);
    setPublishMessage(null);
    setSaveError(null);
    setBlockers([]);
    try {
      const p = await api<Profile>(`/orgs/${id}/profile/publish`, { method: "POST" });
      setProfile(p);
      setForm(toForm(p));
      setPublishMessage("Published. Your public profile is live.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.blockers.length > 0) {
        setBlockers(err.blockers);
      } else {
        setSaveError(err instanceof Error ? err.message : "Could not publish the profile.");
      }
    } finally {
      setPublishing(false);
    }
  }

  async function onUnpublish() {
    setPublishing(true);
    setPublishMessage(null);
    setBlockers([]);
    try {
      const p = await api<Profile>(`/orgs/${id}/profile/unpublish`, { method: "POST" });
      setProfile(p);
      setPublishMessage("Your profile is offline. It is no longer visible to the public.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not take the profile offline.");
    } finally {
      setPublishing(false);
    }
  }

  if (notFound) {
    return <p className="text-muted">This organization was not found, or you are not a member of it.</p>;
  }
  if (loadError) return <Notice kind="error">{loadError}</Notice>;
  if (!me || !org || !members) return <p className="text-muted">Loading profile…</p>;

  const myRole = members.find((m) => m.user_id === me.id)?.role;
  const canManage = myRole !== undefined && MANAGERS.includes(myRole);
  const isNgo = org.org_type === "NGO";

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <PageHeader
          eyebrow={org.org_type}
          title={org.name}
          description={<VerificationBadge status={org.verification_status} />}
        />
        <OrgNav orgId={id} showNgoTabs={isNgo} />
      </div>

      {!isNgo ? (
        <p className="text-muted">Public profiles are available for NGO organizations.</p>
      ) : !canManage ? (
        <section aria-labelledby="readonly-heading" className="space-y-4">
          <h2 id="readonly-heading" className="text-lg font-semibold text-navy">
            Public profile
          </h2>
          {profile ? (
            <ProfileSummary profile={profile} />
          ) : (
            <p className="text-muted">No profile has been written yet. Owners and admins can add one.</p>
          )}
          <p className="text-sm text-muted">Only owners and admins can edit or publish this profile.</p>
        </section>
      ) : (
        <>
          <Card className="space-y-3 p-5">
            <h2 className="text-lg font-semibold text-navy">Visibility</h2>
            {!profile ? (
              <p className="text-muted">You have not written a profile yet. Start with your mission, then publish when ready.</p>
            ) : profile.status === "PUBLISHED" ? (
              <p>
                <span className="font-medium text-status-approved">Published.</span> Anyone can see this profile at{" "}
                <Link href={`/ngos/${id}`} className="text-teal hover:underline">
                  your public page
                </Link>
                .
              </p>
            ) : (
              <p>
                <span className="font-medium">Draft.</span> Only your team can see this profile.
              </p>
            )}
            <p className="text-sm text-muted">
              Profile text is written by your organization. It is not checked by Imparency. Your verification status is
              shown separately, and only verified organizations can publish.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              {profile?.status === "PUBLISHED" ? (
                <Button type="button" variant="secondary" onClick={onUnpublish} disabled={publishing}>
                  {publishing ? "Working…" : "Take profile offline"}
                </Button>
              ) : (
                <Button type="button" onClick={onPublish} disabled={publishing || !profile}>
                  {publishing ? "Publishing…" : "Publish profile"}
                </Button>
              )}
            </div>
            {publishMessage && <Notice kind="success">{publishMessage}</Notice>}
            {blockers.length > 0 && (
              <div role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/5 p-4 text-sm text-status-rejected">
                <p className="font-medium">The profile cannot be published yet:</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {blockers.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <form onSubmit={onSave} className="space-y-5" aria-labelledby="edit-heading">
            <h2 id="edit-heading" className="text-lg font-semibold text-navy">
              Edit profile
            </h2>
            <label className="block">
              <span className="text-sm font-medium">Mission (required, 1000 characters at most)</span>
              <Textarea required rows={3} maxLength={1000} value={form.mission}
                onChange={(e) => update("mission", e.target.value)}
                className="mt-1" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">About your work (optional)</span>
              <Textarea rows={6} maxLength={4000} value={form.about}
                onChange={(e) => update("about", e.target.value)}
                className="mt-1" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">Registered organisation name (optional)</span>
              <span className="block text-sm text-muted">The full legal name as it appears on your registration certificate.</span>
              <Input maxLength={300} value={form.organization_title}
                onChange={(e) => update("organization_title", e.target.value)}
                className="mt-1" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">Vision (optional)</span>
              <span className="block text-sm text-muted">The long-term change you want to see.</span>
              <Textarea rows={3} value={form.vision}
                onChange={(e) => update("vision", e.target.value)}
                className="mt-1" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">Description (optional)</span>
              <span className="block text-sm text-muted">A fuller account of who you are, for donors and funders.</span>
              <Textarea rows={5} value={form.description}
                onChange={(e) => update("description", e.target.value)}
                className="mt-1" />
            </label>
            <div className="grid gap-5 md:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium">Sectors of work</span>
                <span className="block text-sm text-muted">Separate with commas, for example: Water, Sanitation</span>
                <Input value={form.sectors} onChange={(e) => update("sectors", e.target.value)} className="mt-1" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Places you work</span>
                <span className="block text-sm text-muted">Separate with commas, for example: Odisha, Jharkhand</span>
                <Input value={form.geographies} onChange={(e) => update("geographies", e.target.value)} className="mt-1" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Founded (year, optional)</span>
                <Input type="number" min={1800} max={2100} value={form.founded_year}
                  onChange={(e) => update("founded_year", e.target.value)}
                  className="mt-1" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Website (optional, https only)</span>
                <Input type="url" placeholder="https://" value={form.website}
                  onChange={(e) => update("website", e.target.value)}
                  className="mt-1" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Registration number (optional)</span>
                <span className="block text-sm text-muted">As stated by you. Printed on donors' tax certificates.</span>
                <Input value={form.registration_number} onChange={(e) => update("registration_number", e.target.value)} className="mt-1" />
              </label>
              <label className="block">
                <span className="text-sm font-medium">80G registration number (optional)</span>
                <span className="block text-sm text-muted">As stated by you. Printed on donors' tax certificates.</span>
                <Input value={form.section_80g_number} onChange={(e) => update("section_80g_number", e.target.value)} className="mt-1" />
              </label>
            </div>
            <div className="flex items-center gap-4">
              <Button type="submit" variant="secondary" disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
            {saved && <Notice kind="success">{saved}</Notice>}
            {saveError && <Notice kind="error">{saveError}</Notice>}
          </form>
        </>
      )}
    </div>
  );
}

function ProfileSummary({ profile }: { profile: Profile }) {
  return (
    <Card className="p-5">
      <dl className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <dt className="text-sm font-medium text-muted">Mission</dt>
          <dd className="mt-1">{profile.mission}</dd>
        </div>
        {profile.about && (
          <div className="md:col-span-2">
            <dt className="text-sm font-medium text-muted">About</dt>
            <dd className="mt-1 whitespace-pre-line">{profile.about}</dd>
          </div>
        )}
        <div>
          <dt className="text-sm font-medium text-muted">Sectors</dt>
          <dd className="mt-1">{profile.sectors.join(", ") || "Not provided"}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-muted">Places</dt>
          <dd className="mt-1">{profile.geographies.join(", ") || "Not provided"}</dd>
        </div>
      </dl>
    </Card>
  );
}
