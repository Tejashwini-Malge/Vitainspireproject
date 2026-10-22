'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LINKS: { href: string; label: string }[] = [
  { href: '/admin/dashboard', label: 'Dashboard' },
  { href: '/admin', label: 'Verification queue' },
  { href: '/admin/documents', label: 'Documents' },
  { href: '/admin/pan-verifications', label: 'PAN verification' },
  { href: '/admin/ngos', label: 'NGOs' },
  { href: '/admin/donors', label: 'CSR / Donors (orgs)' },
  { href: '/admin/individual-donors', label: 'Individual donors' },
  { href: '/admin/projects', label: 'Projects' },
  { href: '/admin/project-review', label: 'Project review' },
  { href: '/admin/proposal-review', label: 'Proposal review' },
  { href: '/admin/escalations', label: 'Escalations' },
  { href: '/admin/analytics', label: 'Analytics' },
  { href: '/admin/payments', label: 'Payments' },
  { href: '/admin/intelligence', label: 'Intelligence' },
];

/** Shared admin navigation. Without it the oversight pages exist but are unreachable. */
export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Admin sections" className="mb-6 border-b border-gray-200">
      <ul className="flex flex-wrap gap-1">
        {LINKS.map((l) => {
          const active = pathname === l.href;
          return (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={active ? 'page' : undefined}
                className={`inline-block px-3 py-2 text-sm rounded-t-md ${
                  active
                    ? 'bg-white border border-b-white border-gray-200 font-medium text-gray-900'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {l.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default AdminNav;
