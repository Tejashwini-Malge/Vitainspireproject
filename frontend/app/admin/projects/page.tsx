'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, ApiError, clearToken, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import { VerificationBadge } from '@/components/VerificationBadge';
import type { AdminProjectRow, ProjectStatus } from '@/lib/types';

const FILTERS: (ProjectStatus | 'ALL')[] = ['ALL', 'PUBLISHED', 'PENDING_REVIEW', 'CHANGES_REQUESTED', 'DRAFT'];

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
    <div className="max-w-6xl mx-auto p-8">
      <AdminNav />

      <header className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <p className="text-gray-600 mt-1">
          Every project across every organisation, with the standing of whoever owns it.
        </p>
      </header>

      {needsAttention.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {needsAttention.length} published{' '}
          {needsAttention.length === 1 ? 'project belongs' : 'projects belong'} to an organisation
          that is not approved.
        </div>
      )}

      <div className="flex gap-3 items-center mb-4">
        <label className="text-sm text-gray-700">
          Status{' '}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as ProjectStatus | 'ALL')}
            className="ml-1 rounded border border-gray-300 px-2 py-1"
          >
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {f === 'ALL' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </label>
        <span className="text-sm text-gray-500">{rows === null ? '' : `${rows.length} total`}</span>
      </div>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

      {rows === null ? (
        <p className="text-gray-500">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="text-center py-14 text-gray-500 border border-dashed border-gray-300 rounded-lg">
          <p className="text-lg mb-1">No projects</p>
          <p className="text-sm">
            {filter === 'ALL'
              ? 'No organisation has created a project yet.'
              : `No projects are currently ${filter.toLowerCase()}.`}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-gray-200 rounded-lg">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Project</th>
                <th className="px-3 py-2 font-medium">Organisation</th>
                <th className="px-3 py-2 font-medium">Org status</th>
                <th className="px-3 py-2 font-medium">Project status</th>
                <th className="px-3 py-2 font-medium">Funded by</th>
                <th className="px-3 py-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-gray-200">
                  <td className="px-3 py-2">
                    <span className="font-medium text-gray-900">{r.title}</span>
                    <p className="text-xs text-gray-500 mt-0.5 max-w-md truncate">{r.summary}</p>
                  </td>
                  <td className="px-3 py-2 text-gray-800">{r.org_name}</td>
                  <td className="px-3 py-2">
                    <VerificationBadge status={r.org_verification_status} />
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`text-xs rounded px-2 py-0.5 ${
                        r.status === 'PUBLISHED'
                          ? 'bg-green-100 text-green-800'
                          : r.status === 'PENDING_REVIEW'
                            ? 'bg-amber-100 text-amber-800'
                            : r.status === 'CHANGES_REQUESTED'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-600">
                    {r.campaign_id ? 'A campaign' : <span className="text-gray-400">No campaign</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-600">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
