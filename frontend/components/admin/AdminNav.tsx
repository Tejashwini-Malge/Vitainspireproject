'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  ShieldCheck,
  FileCheck2,
  BadgeCheck,
  Building2,
  Users,
  UserRound,
  FolderKanban,
  ClipboardList,
  FileSignature,
  AlertTriangle,
  BarChart3,
  Wallet,
  BrainCircuit,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/components/ui/cn';

const LINKS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/admin', label: 'Verification queue', icon: ShieldCheck },
  { href: '/admin/documents', label: 'Documents', icon: FileCheck2 },
  { href: '/admin/pan-verifications', label: 'PAN verification', icon: BadgeCheck },
  { href: '/admin/ngos', label: 'NGOs', icon: Building2 },
  { href: '/admin/donors', label: 'CSR / Donors (orgs)', icon: Users },
  { href: '/admin/individual-donors', label: 'Individual donors', icon: UserRound },
  { href: '/admin/projects', label: 'Projects', icon: FolderKanban },
  { href: '/admin/project-review', label: 'Project review', icon: ClipboardList },
  { href: '/admin/proposal-review', label: 'Proposal review', icon: FileSignature },
  { href: '/admin/escalations', label: 'Escalations', icon: AlertTriangle },
  { href: '/admin/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/admin/payments', label: 'Payments', icon: Wallet },
  { href: '/admin/intelligence', label: 'Intelligence', icon: BrainCircuit },
];

/** Shared admin navigation. Without it the oversight pages exist but are unreachable. */
export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Admin sections" className="mb-6 border-b-2 border-line">
      <ul className="flex flex-wrap gap-1">
        {LINKS.map((l) => {
          const active = pathname === l.href;
          const Icon = l.icon;
          return (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'relative inline-flex items-center gap-1.5 rounded-t-sm px-3 py-2 font-mono text-xs uppercase tracking-wide transition-colors',
                  active
                    ? 'text-navy font-semibold'
                    : 'text-muted hover:text-navy',
                )}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {l.label}
                {active && (
                  <span className="absolute inset-x-1 -bottom-[2px] h-[2px] rounded-full bg-teal" />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default AdminNav;
