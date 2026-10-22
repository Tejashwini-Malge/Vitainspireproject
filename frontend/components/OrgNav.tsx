"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function OrgNav({ orgId, showNgoTabs }: { orgId: string; showNgoTabs: boolean }) {
  const pathname = usePathname();
  const base = `/orgs/${orgId}`;
  const tabs = [
    { href: base, label: "Overview", show: true },
    { href: `${base}/profile`, label: "Public profile", show: showNgoTabs },
    { href: `${base}/projects`, label: "Projects", show: showNgoTabs },
    { href: `${base}/documents`, label: "Compliance documents", show: showNgoTabs },
    { href: `${base}/donations`, label: "Donations", show: showNgoTabs },
  ].filter((t) => t.show);

  return (
    <nav aria-label="Organization sections" className="border-b-2 border-line">
      <ul className="flex flex-wrap gap-6 font-display text-sm">
        {tabs.map((t) => {
          const active = pathname === t.href;
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                aria-current={active ? "page" : undefined}
                className={`-mb-0.5 inline-block border-b-2 pb-3 font-medium tracking-tight ${
                  active ? "border-teal text-navy" : "border-transparent text-muted hover:text-navy"
                }`}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
