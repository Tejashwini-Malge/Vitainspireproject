'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, ApiError, clearToken, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import { VerificationBadge } from '@/components/VerificationBadge';
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
    <div className="max-w-6xl mx-auto p-8">
      <AdminNav />

      <header className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        <p className="text-gray-600 mt-1">{blurb}</p>
      </header>

      <div className="flex flex-wrap gap-3 items-center mb-4">
        <label className="text-sm text-gray-700">
          Status{' '}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as VerificationStatus | 'ALL')}
            className="ml-1 rounded border border-gray-300 px-2 py-1"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </label>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name…"
          className="rounded border border-gray-300 px-3 py-1 text-sm"
        />
        <span className="text-sm text-gray-500">
          {rows === null ? '' : `${visible.length} of ${rows.length}`}
        </span>
      </div>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

      {rows === null ? (
        <p className="text-gray-500">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="text-center py-14 text-gray-500 border border-dashed border-gray-300 rounded-lg">
          <p className="text-lg mb-1">Nothing to show</p>
          <p className="text-sm">
            {search.trim()
              ? 'No organisation matches that name.'
              : statusFilter === 'ALL'
                ? 'No organisations of this type have registered yet.'
                : `No organisations are currently ${statusFilter.toLowerCase()}.`}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-gray-200 rounded-lg">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Organisation</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium text-right">Members</th>
                <th className="px-3 py-2 font-medium text-right">{countLabel}</th>
                <th className="px-3 py-2 font-medium text-right">Raised</th>
                <th className="px-3 py-2 font-medium">Joined</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.id} className="border-t border-gray-200">
                  <td className="px-3 py-2">
                    <span className="font-medium text-gray-900">{r.name}</span>
                    {r.verification_reason && (
                      <p className="text-xs text-gray-500 mt-0.5">{r.verification_reason}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <VerificationBadge status={r.verification_status} />
                  </td>
                  <td className="px-3 py-2 text-right">{r.member_count}</td>
                  <td className="px-3 py-2 text-right">
                    {orgType === 'NGO' ? r.project_count : r.campaign_count}
                  </td>
                  <td className="px-3 py-2 text-right">{rupees(r.total_raised_minor)}</td>
                  <td className="px-3 py-2 text-gray-600">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/conversations/new?org_id=${r.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      Message
                    </Link>
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

export default OrgDirectory;
