// Original line-art, matched to an NGO's declared sector. Generic by design -- it illustrates
// a kind of work, never a specific place, person or event, so it can never misrepresent one.
import type { ReactElement } from "react";

const STROKE = "#1D2B4F";
const ACCENT = "#B9650A";

function WaterArt() {
  return (
    <svg viewBox="0 0 96 96" aria-hidden className="h-full w-full">
      <circle cx="48" cy="48" r="46" fill="#F5E6CB" />
      <path d="M30 70 V46 Q30 36 40 36 H46 V28 H50 V36 H56 Q66 36 66 46 V70" fill="none" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <path d="M34 70 H62" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <path d="M48 44 C 44 52, 44 56, 48 60 C 52 56, 52 52, 48 44 Z" fill={ACCENT} />
    </svg>
  );
}

function EducationArt() {
  return (
    <svg viewBox="0 0 96 96" aria-hidden className="h-full w-full">
      <circle cx="48" cy="48" r="46" fill="#F5E6CB" />
      <path d="M48 36 C 40 30, 28 30, 24 34 V62 C 28 58, 40 58, 48 64" fill="none" stroke={STROKE} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      <path d="M48 36 C 56 30, 68 30, 72 34 V62 C 68 58, 56 58, 48 64" fill="none" stroke={STROKE} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      <line x1="48" y1="36" x2="48" y2="64" stroke={STROKE} strokeWidth="2" />
      <circle cx="48" cy="26" r="4.5" fill={ACCENT} />
    </svg>
  );
}

function ElderCareArt() {
  return (
    <svg viewBox="0 0 96 96" aria-hidden className="h-full w-full">
      <circle cx="48" cy="48" r="46" fill="#F5E6CB" />
      <path d="M30 58 Q30 44 48 44 Q66 44 66 58" fill="none" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <path d="M26 58 H70" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <path d="M26 58 V66 M70 58 V66" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <path d="M44 50 C 41 46, 35 47, 35 52 C 35 57, 44 62, 44 62 C 44 62, 53 57, 53 52 C 53 47, 47 46, 44 50 Z" fill={ACCENT} />
    </svg>
  );
}

function CommunityArt() {
  return (
    <svg viewBox="0 0 96 96" aria-hidden className="h-full w-full">
      <circle cx="48" cy="48" r="46" fill="#F5E6CB" />
      <circle cx="33" cy="40" r="8" fill="none" stroke={STROKE} strokeWidth="2.5" />
      <path d="M20 66 Q20 52 33 52 Q46 52 46 66" fill="none" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="63" cy="40" r="8" fill="none" stroke={STROKE} strokeWidth="2.5" />
      <path d="M50 66 Q50 52 63 52 Q76 52 76 66" fill="none" stroke={STROKE} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="48" cy="28" r="4" fill={ACCENT} />
    </svg>
  );
}

const MATCHERS: { test: RegExp; Art: () => ReactElement }[] = [
  { test: /water|sanitation|well|irrigation/i, Art: WaterArt },
  { test: /education|school|learning|literacy/i, Art: EducationArt },
  { test: /elder|senior|ageing|aging/i, Art: ElderCareArt },
];

export function SectorArt({ sectors }: { sectors: string[] }) {
  const match = MATCHERS.find((m) => sectors.some((s) => m.test.test(s)));
  const Art = match?.Art ?? CommunityArt;
  return <Art />;
}
