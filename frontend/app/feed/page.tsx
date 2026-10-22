"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { SectorArt } from "@/components/SectorArt";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { FeedItem } from "@/lib/types";

// Leaflet touches `window` at import time, so this can never run during server rendering.
const FeedMap = dynamic(() => import("@/components/FeedMap").then((m) => m.FeedMap), { ssr: false });

interface Location {
  label: string;
  lat: number;
  lon: number;
}

function formatMoney(amountMinor: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amountMinor / 100);
}

function formatDistance(km: number): string {
  return km < 1 ? "under 1 km away" : `${Math.round(km)} km away`;
}

function feedQuery(sectors: string[], location: Location | null): string {
  const params = new URLSearchParams();
  sectors.forEach((s) => params.append("sectors", s));
  if (location) {
    params.set("lat", String(location.lat));
    params.set("lon", String(location.lon));
  }
  const qs = params.toString();
  return qs ? `/feed?${qs}` : "/feed";
}

export default function FeedPage() {
  const router = useRouter();
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [allSectors, setAllSectors] = useState<string[]>([]);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [location, setLocation] = useState<Location | null>(null);
  const [locationInput, setLocationInput] = useState("");
  const [locationBusy, setLocationBusy] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sectors are a controlled-ish list (an NGO picks from the same set everyone else does), so
  // suggesting the ones already in the feed is enough -- derived once from the unfiltered feed.
  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api<FeedItem[]>("/feed")
      .then((data) => {
        setAllSectors(Array.from(new Set(data.flatMap((i) => i.org_sectors))).sort());
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/login");
        }
      });
  }, [router]);

  useEffect(() => {
    if (!getToken()) return;
    api<FeedItem[]>(feedQuery(selectedSectors, location))
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the feed."));
  }, [selectedSectors, location]);

  const hasPreferences = selectedSectors.length > 0 || location !== null;

  function toggleSector(value: string) {
    setSelectedSectors(selectedSectors.includes(value) ? selectedSectors.filter((v) => v !== value) : [...selectedSectors, value]);
  }

  function useMyLocation() {
    if (!("geolocation" in navigator)) {
      setLocationError("This browser can't share your location.");
      return;
    }
    setLocationBusy(true);
    setLocationError(null);

    // The browser's own `timeout` option is only guaranteed to apply once permission has been
    // granted or denied -- a permission prompt nobody answers can leave getCurrentPosition
    // pending indefinitely with no callback at all. This guard timer guarantees the button
    // always comes back to a usable state instead of silently hanging forever.
    let settled = false;
    const giveUp = setTimeout(() => {
      if (settled) return;
      settled = true;
      setLocationError("Location request timed out -- allow the browser's location prompt, or type a place instead.");
      setLocationBusy(false);
    }, 10_000);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (settled) return;
        settled = true;
        clearTimeout(giveUp);
        setLocation({ label: "Your location", lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocationBusy(false);
      },
      () => {
        if (settled) return;
        settled = true;
        clearTimeout(giveUp);
        setLocationError("Location permission was denied.");
        setLocationBusy(false);
      },
      { timeout: 10_000 }
    );
  }

  async function addTypedLocation(e: FormEvent) {
    e.preventDefault();
    const q = locationInput.trim();
    if (!q) return;
    setLocationBusy(true);
    setLocationError(null);
    try {
      const resolved = await api<{ lat: number; lon: number; display_name: string }>(`/geocode?q=${encodeURIComponent(q)}`);
      setLocation({ label: resolved.display_name, lat: resolved.lat, lon: resolved.lon });
      setLocationInput("");
    } catch {
      setLocationError(`Couldn't find "${q}". Try a city or state name.`);
    } finally {
      setLocationBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-navy">Your feed</h1>
        <p className="text-muted">
          Live campaigns and open projects from verified NGOs. Pick a sector or a location below to bring matching work to
          the top -- it narrows nothing, it just reorders.
        </p>
      </header>

      <div className="space-y-4 rounded-sm border-2 border-navy bg-white/60 p-4">
        {allSectors.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs uppercase tracking-wide text-muted">Sector</span>
            {allSectors.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => toggleSector(s)}
                className={`rounded-full border px-3 py-1 text-sm ${
                  selectedSectors.includes(s) ? "border-teal bg-teal text-paper" : "border-line text-navy hover:border-teal"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wide text-muted">Near</span>
          {location ? (
            <button
              type="button"
              onClick={() => setLocation(null)}
              className="rounded-full border border-teal bg-teal px-3 py-1 text-sm text-paper"
              title="Click to clear"
            >
              {location.label} ✕
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={useMyLocation}
                disabled={locationBusy}
                className="rounded-full border border-navy px-3 py-1 text-sm text-navy hover:bg-navy hover:text-paper disabled:opacity-60"
              >
                Use my location
              </button>
              <form onSubmit={addTypedLocation} className="flex items-center gap-1">
                <input
                  type="text"
                  value={locationInput}
                  onChange={(e) => setLocationInput(e.target.value)}
                  placeholder="…or type a city or state"
                  className="rounded-full border border-line bg-white px-3 py-1 text-sm"
                />
                <button
                  type="submit"
                  disabled={locationBusy}
                  className="rounded-full border border-navy px-3 py-1 text-sm text-navy hover:bg-navy hover:text-paper disabled:opacity-60"
                >
                  Add
                </button>
              </form>
            </>
          )}
        </div>
        {locationError && <p className="text-sm text-status-rejected">{locationError}</p>}
      </div>

      {error && (
        <p role="alert" className="text-status-rejected">
          {error}
        </p>
      )}
      {!error && items === null && <p className="text-muted">Loading…</p>}
      {items && items.length > 0 && (
        <FeedMap items={items} donorLocation={location ? { lat: location.lat, lon: location.lon } : null} />
      )}
      {items && items.length === 0 && (
        <p className="rounded-sm border border-dashed border-line bg-white/60 p-5 text-muted">
          Nothing live right now. Check back soon, or{" "}
          <Link href="/#ngos" className="font-medium text-teal hover:underline">
            browse verified NGOs
          </Link>{" "}
          directly.
        </p>
      )}
      {items && items.length > 0 && (
        <ul className="grid gap-x-6 gap-y-10 md:grid-cols-2">
          {items.map((item) => (
            <FeedCard key={`${item.kind}-${item.id}`} item={item} boosted={hasPreferences && item.score > 0} />
          ))}
        </ul>
      )}
    </div>
  );
}

function FeedCard({ item, boosted }: { item: FeedItem; boosted: boolean }) {
  const progress =
    item.kind === "campaign" && item.budget_total && item.budget_total > 0
      ? Math.min(100, Math.round(((item.amount_raised ?? 0) / item.budget_total) * 100))
      : null;

  return (
    <li className="stub-card">
      <div className="flex gap-4 p-5">
        <div className="h-14 w-14 shrink-0 overflow-hidden rounded-full border border-line">
          {item.hero_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.hero_image_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <SectorArt sectors={item.org_sectors} />
          )}
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <p className="font-mono text-xs uppercase tracking-wide text-muted">{item.org_name}</p>
            {boosted && <span className="ink-stamp text-status-approved">Matches your picks</span>}
          </div>
          <h3 className="text-lg font-semibold text-navy">{item.title}</h3>
          <p className="text-muted">{item.summary}</p>
          {item.distance_km !== null && item.distance_km !== undefined && (
            <p className="text-xs text-muted">{formatDistance(item.distance_km)}</p>
          )}
          {progress !== null && (
            <div className="space-y-1 pt-1">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
                <div className="h-full bg-teal" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-muted">
                {formatMoney(item.amount_raised ?? 0)} raised of {formatMoney(item.budget_total ?? 0)}
              </p>
            </div>
          )}
        </div>
      </div>
      <div className="stub-tear flex gap-4 p-5 text-sm">
        <Link href={`/ngos/${item.org_id}`} className="font-medium text-navy hover:underline">
          Read about {item.org_name}
        </Link>
        {item.kind === "campaign" ? (
          <Link href={`/campaigns/${item.id}`} className="font-medium text-teal hover:underline">
            View campaign
          </Link>
        ) : (
          <Link href={`/donate/${item.org_id}?project=${item.id}`} className="font-medium text-teal hover:underline">
            Donate to this project
          </Link>
        )}
      </div>
    </li>
  );
}
