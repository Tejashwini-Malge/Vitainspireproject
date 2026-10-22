"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api";

const SECTORS = [
  "Agriculture",
  "Arts & Culture",
  "Disability",
  "Disaster Relief",
  "Education",
  "Environment",
  "Food Security",
  "Gender Equality",
  "Health",
  "Heritage",
  "Livelihoods",
  "Rural Infrastructure",
  "Sanitation",
  "Water",
];

// Sector-specific mission templates
const TEMPLATES: Record<string, string[]> = {
  Water: [
    "We provide clean water and sanitation solutions to rural communities.",
    "We rebuild hand-dug wells in drought-hit villages to ensure year-round water access.",
    "Our mission is to end water scarcity in underserved regions through sustainable well maintenance.",
  ],
  Health: [
    "We provide accessible healthcare services to remote and underserved populations.",
    "We run mobile clinics and telemedicine centers to serve rural communities.",
    "Our mission is to bridge the healthcare gap in informal settlements through trained volunteers.",
  ],
  Education: [
    "We provide quality education and skill development to underprivileged children.",
    "We run evening study centers and vocational training programs for youth in informal settlements.",
    "Our mission is to unlock potential through education in communities that need it most.",
  ],
  Agriculture: [
    "We support smallholder farmers with sustainable farming practices and market access.",
    "We help farmers increase yields and income through training and resource access.",
    "Our mission is to transform rural livelihoods through sustainable agriculture.",
  ],
  Default: [
    "We work to create positive social impact in our community.",
    "Our mission is to empower and support vulnerable populations.",
    "We are dedicated to building sustainable solutions for social change.",
  ],
};

type Step = "template" | "edit" | "complete";

export default function ProfileSetupPage() {
  const params = useParams()!;
  const router = useRouter();
  const orgId = params.id as string;

  const [step, setStep] = useState<Step>("template");
  const [sectors, setSectors] = useState<string[]>([]);
  const [website, setWebsite] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [mission, setMission] = useState("");
  const [about, setAbout] = useState("");
  const [vision, setVision] = useState("");
  const [description, setDescription] = useState("");
  const [organizationTitle, setOrganizationTitle] = useState("");
  const [foundedYear, setFoundedYear] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generatingAbout, setGeneratingAbout] = useState(false);
  const [extractingWebsite, setExtractingWebsite] = useState(false);
  const [extractedData, setExtractedData] = useState<any>(null);

  const primarySector = sectors[0] || "Default";
  const templates = TEMPLATES[primarySector] || TEMPLATES.Default;

  function selectTemplate(template: string) {
    setSelectedTemplate(template);
    setMission(template);
    setStep("edit");
  }

  async function extractWebsite() {
    if (!website) return;

    setExtractingWebsite(true);
    setError(null);
    try {
      const response = await api<any>("/orgs/" + orgId + "/profile/extract-website", {
        method: "POST",
        body: JSON.stringify({
          website_url: website,
        }),
      });

      setExtractedData(response);

      // Auto-populate ALL fields from extracted data
      if (response.title) setOrganizationTitle(response.title);
      if (response.description) setDescription(response.description);
      if (response.vision) setVision(response.vision);
      if (response.mission) setMission(response.mission);
      if (response.about) setAbout(response.about);
      if (response.founded_year) setFoundedYear(response.founded_year);

      // Show success message
      setError(null);
    } catch (err) {
      setError("Could not extract website data. Try manually entering information.");
    } finally {
      setExtractingWebsite(false);
    }
  }

  async function generateAbout() {
    if (!mission) return;

    setGeneratingAbout(true);
    setError(null);
    try {
      const response = await api<{ about: string }>("/ngo/generate-about", {
        method: "POST",
        body: JSON.stringify({
          mission,
          sectors,
          website_url: website || null,
        }),
      });
      setAbout(response.about);
    } catch (err) {
      // If generation fails, show a placeholder
      setAbout("We are working to create positive change in our community. Our approach combines proven methodologies with local insights. We measure impact and continuously improve our programs.");
    } finally {
      setGeneratingAbout(false);
    }
  }

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api(`/orgs/${orgId}/profile`, {
        method: "PUT",
        body: JSON.stringify({
          mission,
          about,
          vision: vision || null,
          description: description || null,
          organization_title: organizationTitle || null,
          sectors,
          founded_year: foundedYear,
          website: website || null,
        }),
      });
      setStep("complete");
      setTimeout(() => router.push(`/orgs/${orgId}`), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save profile. Try again.");
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-navy">Set up your profile</h1>
        <p className="text-muted">
          {step === "template"
            ? "Choose a mission statement template or create your own."
            : step === "edit"
            ? "Review and customize your profile, then save."
            : "Profile saved! Redirecting..."}
        </p>
      </div>

      {/* Step 1: Select Sector & Template */}
      {step === "template" && (
        <form onSubmit={(e) => { e.preventDefault(); }} className="space-y-8">
          {/* Website URL (optional) */}
          <div className="space-y-2 rounded-sm border-2 border-teal/30 bg-teal/5 p-4">
            <label className="block">
              <span className="text-sm font-medium">Website (optional)</span>
              <p className="text-xs text-muted mt-1">We'll extract founding year, mission, vision, and about information</p>
              <div className="mt-2 flex gap-2">
                <input
                  type="url"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://yourngodomain.org"
                  className="flex-1 rounded-sm border-2 border-line bg-white px-3 py-2"
                />
                <button
                  type="button"
                  onClick={extractWebsite}
                  disabled={extractingWebsite || !website}
                  className="rounded-sm bg-teal px-4 py-2 text-sm font-medium text-paper disabled:opacity-60"
                >
                  {extractingWebsite ? "🔍 Extracting..." : "🔍 Extract"}
                </button>
              </div>
            </label>

            {/* Show extracted data preview */}
            {extractedData && (
              <div className="mt-4 rounded-sm border-2 border-teal bg-white p-3 space-y-2">
                <p className="text-xs font-medium text-navy">✓ Extracted from website:</p>
                {extractedData.title && (
                  <p className="text-xs"><strong>Title:</strong> {extractedData.title}</p>
                )}
                {extractedData.description && (
                  <p className="text-xs"><strong>Description:</strong> {extractedData.description.substring(0, 120)}...</p>
                )}
                {extractedData.founded_year && (
                  <p className="text-xs"><strong>Founded:</strong> {extractedData.founded_year}</p>
                )}
                {extractedData.mission && (
                  <p className="text-xs"><strong>Mission:</strong> {extractedData.mission.substring(0, 100)}...</p>
                )}
                {extractedData.vision && (
                  <p className="text-xs"><strong>Vision:</strong> {extractedData.vision.substring(0, 100)}...</p>
                )}
                {extractedData.about && (
                  <p className="text-xs"><strong>About:</strong> {extractedData.about.substring(0, 100)}...</p>
                )}
                {extractedData.mission_statements && extractedData.mission_statements.length > 0 && (
                  <div className="mt-2 border-t pt-2">
                    <p className="text-xs font-medium text-navy mb-1">💡 Found mission statements:</p>
                    <div className="space-y-1">
                      {extractedData.mission_statements.map((stmt: string, idx: number) => (
                        <p key={idx} className="text-xs bg-yellow-50 p-2 rounded text-navy cursor-pointer hover:bg-yellow-100" onClick={() => setMission(stmt)}>
                          {stmt}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sectors */}
          <div className="space-y-3">
            <label className="text-sm font-medium">What sectors does your NGO work in?</label>
            <div className="grid grid-cols-2 gap-2">
              {SECTORS.map((sector) => (
                <label key={sector} className="flex items-center gap-2 rounded-sm border-2 border-line p-3 hover:bg-navy/5">
                  <input
                    type="checkbox"
                    checked={sectors.includes(sector)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSectors([...sectors, sector]);
                      } else {
                        setSectors(sectors.filter((s) => s !== sector));
                      }
                    }}
                    className="h-4 w-4"
                  />
                  <span className="text-sm font-medium">{sector}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Templates */}
          {sectors.length > 0 && (
            <div className="space-y-3">
              <label className="text-sm font-medium">Choose a mission statement template or write your own</label>
              <div className="space-y-2">
                {templates.map((template, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => selectTemplate(template)}
                    className="w-full rounded-sm border-2 border-teal bg-teal/5 p-4 text-left hover:bg-teal hover:text-paper"
                  >
                    <p className="text-sm">{template}</p>
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    setMission("");
                    setStep("edit");
                  }}
                  className="w-full rounded-sm border-2 border-navy p-4 font-medium text-navy hover:bg-navy hover:text-paper"
                >
                  + Write your own mission
                </button>
              </div>
            </div>
          )}

          {error && <p className="text-sm text-status-rejected">{error}</p>}
        </form>
      )}

      {/* Step 2: Edit & Review */}
      {step === "edit" && (
        <form onSubmit={saveProfile} className="space-y-6">
          {/* Mission */}
          <div className="space-y-2">
            <label className="block">
              <span className="text-sm font-medium">Mission (1-2 sentences)</span>
              <textarea
                required
                value={mission}
                onChange={(e) => setMission(e.target.value)}
                className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2"
                rows={2}
              />
            </label>
          </div>

          {/* About */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">About (2-3 sentences)</label>
              <button
                type="button"
                onClick={generateAbout}
                disabled={generatingAbout}
                className="text-sm font-medium text-teal hover:underline disabled:opacity-60"
              >
                {generatingAbout ? "✨ Generating..." : "✨ Generate with AI"}
                {website && <span className="text-xs text-navy ml-1">(using your website)</span>}
              </button>
            </div>
            <textarea
              value={about}
              onChange={(e) => setAbout(e.target.value)}
              placeholder="Your organization's story and approach..."
              className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2"
              rows={3}
            />
            {website && <p className="text-xs text-muted">Website data will be used to generate a personalized about section</p>}
          </div>

          {/* Sectors Tag */}
          <div className="flex flex-wrap gap-2">
            {sectors.map((sector) => (
              <span key={sector} className="rounded-full bg-teal/20 px-3 py-1 text-sm text-navy">
                {sector}
              </span>
            ))}
          </div>

          {error && <p className="text-sm text-status-rejected">{error}</p>}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep("template")}
              disabled={saving}
              className="flex-1 rounded-sm border-2 border-navy px-4 py-2 font-display font-medium text-navy hover:bg-navy hover:text-paper disabled:opacity-60"
            >
              Back
            </button>
            <button
              type="submit"
              disabled={saving || !mission || !about}
              className="flex-1 rounded-sm bg-teal px-4 py-2 font-display font-medium text-paper disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save & Continue"}
            </button>
          </div>
        </form>
      )}

      {/* Step 3: Complete */}
      {step === "complete" && (
        <div className="space-y-6 rounded-sm border-2 border-teal bg-teal/5 p-8 text-center">
          <div className="text-5xl">✓</div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold text-navy">Profile created!</h2>
            <p className="text-muted">Your profile has been saved. A reviewer will verify your information before it goes public.</p>
          </div>
          <p className="text-sm text-muted">Redirecting you to your organization dashboard...</p>
        </div>
      )}
    </div>
  );
}
