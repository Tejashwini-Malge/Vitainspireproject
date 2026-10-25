'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { api, ApiError, clearToken, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import { VerificationBadge } from '@/components/VerificationBadge';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/ui/empty-state';
import type { AdminOrgRow, OrgType, VerificationStatus } from '@/lib/types';

const STATUSES: (VerificationStatus | 'ALL')[] = ['ALL', 'APPROVED', 'PENDING', 'REJECTED'];

function rupees(minor: number): string {
  // Amounts are stored in paise; show whole rupees, which is what a reviewer reads.
  return `₹${Math.round(minor / 100).toLocaleString('en-IN')}`;
}

export function OrgDirectory({
  orgType,
  title,
  blurb,
  countLabel,
}: {
  orgType: OrgType;
  title: string;
  blurb: string;
  /** What the per-organisation count column means for this type. */
  countLabel: string;
}) {
  const router = useRouter();
  const [rows, setRows] = useState<AdminOrgRow[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<VerificationStatus | 'ALL'>('ALL');
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(
    async (status: VerificationStatus | 'ALL') => {
      const query =
        `?org_type=${orgType}` + (status === 'ALL' ? '' : `&verification_status=${status}`);
      try {
        setRows(await api<AdminOrgRow[]>(`/admin/organizations${query}`));
        setError('');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace('/admin/login');
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          setError('This page is for platform staff.');
          setRows([]);
          return;
        }
        setError('Could not load the directory.');
        setRows([]);
      }
    },
    [orgType, router],
  );

  useEffect(() => {
    if (!getToken()) {
      router.replace('/admin/login');
      return;
    }
    load(statusFilter);
  }, [load, router, statusFilter]);

  const visible = (rows ?? []).filter((r) =>
    r.name.toLowerCase().includes(search.trim().toLowerCase()),
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <AdminNav />

      <PageHeader eyebrow="Admin" title={title} description={blurb} />

      <div className="flex flex-wrap items-center gap-3">
        <label className="font-mono text-xs uppercase tracking-wide text-muted">
          Status{' '}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as VerificationStatus | 'ALL')}
            className="ml-1 rounded-sm border border-line bg-[#FFFDF7] px-2 py-1 text-sm normal-case tracking-normal text-ink"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </label>
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name…"
          className="w-56"
        />
        <span className="text-sm text-muted">
          {rows === null ? '' : `${visible.length} of ${rows.length}`}
        </span>
      </div>

      {error && (
        <div className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-3 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {rows === null ? (
        <p className="text-muted">Loading…</p>
      ) : visible.length === 0 ? (
        <EmptyState
          title="Nothing to show"
          description={
            search.trim()
              ? 'No organisation matches that name.'
              : statusFilter === 'ALL'
                ? 'No organisations of this type have registered yet.'
                : `No organisations are currently ${statusFilter.toLowerCase()}.`
          }
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b-2 border-line text-left font-mono text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Organisation</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Members</th>
                <th className="px-4 py-3 text-right font-medium">{countLabel}</th>
                <th className="px-4 py-3 text-right font-medium">Raised</th>
                <th className="px-4 py-3 font-medium">Joined</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {visible.map((r, i) => (
                <motion.tr
                  key={r.id}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.25, delay: Math.min(i, 10) * 0.02 }}
                  className="border-t border-line"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium text-navy">{r.name}</span>
                    {r.verification_reason && (
                      <p className="mt-0.5 text-xs text-muted">{r.verification_reason}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <VerificationBadge status={r.verification_status} />
                  </td>
                  <td className="px-4 py-3 text-right text-ink">{r.member_count}</td>
                  <td className="px-4 py-3 text-right text-ink">
                    {orgType === 'NGO' ? r.project_count : r.campaign_count}
                  </td>
                  <td className="px-4 py-3 text-right text-ink">{rupees(r.total_raised_minor)}</td>
                  <td className="px-4 py-3 text-muted">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/conversations/new?org_id=${r.id}`}
                      className="font-medium text-teal hover:underline"
                    >
                      Message
                    </Link>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

export default OrgDirectory;
