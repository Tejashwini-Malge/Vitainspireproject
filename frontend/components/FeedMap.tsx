"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useMemo, useRef } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import Link from "next/link";
import type { FeedItem } from "@/lib/types";

// India's rough bounding-box centre -- the sensible default when no pin or donor location
// exists yet to centre on instead.
const INDIA_CENTER: [number, number] = [22.9734, 78.6569];
const INDIA_ZOOM = 5;
const LOCATED_ZOOM = 10;

function pinIcon(color: string) {
  // A div-icon rather than Leaflet's default marker image: the default marker PNGs don't
  // resolve correctly through Next's bundler, and a custom shape lets the pin carry the same
  // ink-stamp circular style as the rest of the app instead of a generic map teardrop.
  return L.divIcon({
    className: "",
    html: `<span style="
      display:block;width:18px;height:18px;border-radius:9999px;
      background:${color};border:2px solid #F7F1E3;box-shadow:0 0 0 1px ${color};
    "></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -9],
  });
}

const MATCHED_ICON = pinIcon("#1F6F4A"); // stamp green, same as "Matches your picks"
const DEFAULT_ICON = pinIcon("#1D2B4F"); // navy

function isValidPoint(p: [number, number]): boolean {
  return Number.isFinite(p[0]) && Number.isFinite(p[1]);
}

function FitToPins({ points, hasDonorLocation }: { points: [number, number][]; hasDonorLocation: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (hasDonorLocation) return;
    const valid = points.filter(isValidPoint);
    if (valid.length === 0) return;
    try {
      if (valid.length === 1) {
        map.setView(valid[0], LOCATED_ZOOM);
      } else {
        map.fitBounds(L.latLngBounds(valid), { padding: [32, 32] });
      }
    } catch {
      // A mid-render pin list (e.g. during a fast refresh) can momentarily produce bounds
      // Leaflet rejects -- the map just keeps its current view rather than crashing the page.
    }
  }, [map, points, hasDonorLocation]);
  return null;
}

export function FeedMap({ items, donorLocation }: { items: FeedItem[]; donorLocation: { lat: number; lon: number } | null }) {
  const pinned = useMemo(() => items.filter((i): i is FeedItem & { lat: number; lon: number } => i.lat !== null && i.lon !== null), [items]);
  const points = useMemo<[number, number][]>(() => pinned.map((i) => [i.lat, i.lon]), [pinned]);
  const initialCenter = donorLocation ? ([donorLocation.lat, donorLocation.lon] as [number, number]) : INDIA_CENTER;
  // The map is only ever centred imperatively (FitToPins / setView), never re-created -- a key
  // tied to the donor location is still useful so switching "near me" on/off starts fresh.
  const mapKey = donorLocation ? `${donorLocation.lat},${donorLocation.lon}` : "default";
  const containerRef = useRef<HTMLDivElement>(null);

  if (pinned.length === 0) return null;

  return (
    <div ref={containerRef} className="h-80 w-full overflow-hidden rounded-sm border-2 border-navy">
      <MapContainer key={mapKey} center={initialCenter} zoom={donorLocation ? LOCATED_ZOOM : INDIA_ZOOM} className="h-full w-full" scrollWheelZoom={false}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitToPins points={points} hasDonorLocation={!!donorLocation} />
        {donorLocation && (
          <Marker position={[donorLocation.lat, donorLocation.lon]} icon={pinIcon("#B9650A")}>
            <Popup>You are here</Popup>
          </Marker>
        )}
        {pinned.map((item) => (
          <Marker key={`${item.kind}-${item.id}`} position={[item.lat, item.lon]} icon={item.score > 0 ? MATCHED_ICON : DEFAULT_ICON}>
            <Popup>
              <div className="space-y-1">
                <p className="font-mono text-xs uppercase tracking-wide text-muted">{item.org_name}</p>
                <p className="font-semibold text-navy">{item.title}</p>
                {item.distance_km !== null && <p className="text-xs text-muted">{Math.round(item.distance_km)} km away</p>}
                <Link href={`/ngos/${item.org_id}`} className="text-sm font-medium text-teal hover:underline">
                  Read about {item.org_name}
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
