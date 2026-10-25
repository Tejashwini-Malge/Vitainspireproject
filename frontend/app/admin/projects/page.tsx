'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import { api, ApiError, clearToken, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import { VerificationBadge } from '@/components/VerificationBadge';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import type { AdminProjectRow, ProjectStatus } from '@/lib/types';

const FILTERS: (ProjectStatus | 'ALL')[] = ['ALL', 'PUBLISHED', 'PENDING_REVIEW', 'CHANGES_REQUESTED', 'DRAFT'];

const STATUS_TONE: Record<ProjectStatus, BadgeTone> = {
  PUBLISHED: 'approved',
  PENDING_REVIEW: 'pending',
  CHANGES_REQUESTED: 'rejected',
  DRAFT: 'neutral',
};

export default function AdminProjectsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<AdminProjectRow[] | null>(null);
  const [filter, setFilter] = useState<ProjectStatus | 'ALL'>('ALL');
  const [error, setError] = useState('');

  const load = useCallback(
    async (status: ProjectStatus | 'ALL') => {
      const query = status === 'ALL' ? '' : `?status_filter=${status}`;
      try {
        setRows(await api<AdminProjectRow[]>(`/admin/projects${query}`));
        setError('');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace('/admin/login');
          return;
        }
        setError(
          err instanceof ApiError && err.status === 403
            ? 'This page is for platform staff.'
            : 'Could not load projects.',
        );
        setRows([]);
      }
    },
    [router],
  );

  useEffect(() => {
    if (!getToken()) {
      router.replace('/admin/login');
      return;
    }
    load(filter);
  }, [load, router, filter]);

  // A published project from an unverified organisation is the case worth surfacing.
  const needsAttention = (rows ?? []).filter(
    (r) => r.status === 'PUBLISHED' && r.org_verification_status !== 'APPROVED',
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <AdminNav />

      <PageHeader
        eyebrow="Admin"
        title="Projects"
        description="Every project across every organisation, with the standing of whoever owns it."
      />

      {needsAttention.length > 0 && (
        <div className="flex items-start gap-3 rounded-sm border border-status-pending/40 bg-status-pending/10 p-3 text-sm text-status-pending">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            {needsAttention.length} published{' '}
            {needsAttention.length === 1 ? 'project belongs' : 'projects belong'} to an organisation
            that is not approved.
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <label className="font-mono text-xs uppercase tracking-wide text-muted">
          Status{' '}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as ProjectStatus | 'ALL')}
            className="ml-1 rounded-sm border border-line bg-[#FFFDF7] px-2 py-1 text-sm normal-case tracking-normal text-ink"
          >
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {f === 'ALL' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </label>
        <span className="text-sm text-muted">{rows === null ? '' : `${rows.length} total`}</span>
      </div>

      {error && (
        <div className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-3 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {rows === null ? (
        <p className="text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No projects"
          description={
            filter === 'ALL'
              ? 'No organisation has created a project yet.'
              : `No projects are currently ${filter.toLowerCase()}.`
          }
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b-2 border-line text-left font-mono text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Project</th>
                <th className="px-4 py-3 font-medium">Organisation</th>
                <th className="px-4 py-3 font-medium">Org status</th>
                <th className="px-4 py-3 font-medium">Project status</th>
                <th className="px-4 py-3 font-medium">Funded by</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <motion.tr
                  key={r.id}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.25, delay: Math.min(i, 10) * 0.02 }}
                  className="border-t border-line"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium text-navy">{r.title}</span>
                    <p className="mt-0.5 max-w-md truncate text-xs text-muted">{r.summary}</p>
                  </td>
                  <td className="px-4 py-3 text-ink">{r.org_name}</td>
                  <td className="px-4 py-3">
                    <VerificationBadge status={r.org_verification_status} />
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-muted">
                    {r.campaign_id ? 'A campaign' : <span className="text-muted/70">No campaign</span>}
                  </td>
                  <td className="px-4 py-3 text-muted">
                    {new Date(r.created_at).toLocaleDateString()}
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
