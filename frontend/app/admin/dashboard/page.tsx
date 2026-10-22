'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, ApiError, clearToken, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import type { AdminDashboard, AdminQueueItem, Org } from '@/lib/types';

function rupees(minor: number): string {
  return `₹${Math.round(minor / 100).toLocaleString('en-IN')}`;
}

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-sm text-gray-600">{label}</p>
      <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
      {hint && <p className="text-xs text-gray-500 mt-1">{hint}</p>}
    </div>
  );
}

export default function AdminDashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [orgQueue, setOrgQueue] = useState<Org[]>([]);
  const [docQueue, setDocQueue] = useState<AdminQueueItem[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/admin/login');
      return;
    }
    (async () => {
      try {
        // Each panel is fetched independently so one failing endpoint does not blank
        // the whole page -- an admin still needs the queues if analytics is down.
        const [dash, orgs, docs] = await Promise.allSettled([
          api<AdminDashboard>('/admin/analytics/dashboard'),
          api<Org[]>('/admin/verification-queue'),
          api<AdminQueueItem[]>('/admin/documents/queue'),
        ]);
        if (dash.status === 'fulfilled') setData(dash.value);
        if (orgs.status === 'fulfilled') setOrgQueue(orgs.value ?? []);
        if (docs.status === 'fulfilled') setDocQueue(docs.value ?? []);

        const denied = [dash, orgs, docs].some(
          (r) => r.status === 'rejected' && r.reason instanceof ApiError && r.reason.status === 401,
        );
        if (denied) {
          clearToken();
          router.replace('/admin/login');
          return;
        }
        if (dash.status === 'rejected') setError('Analytics could not be loaded.');
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  if (loading) return <div className="p-8 text-gray-500">Loading dashboard…</div>;

  const waiting = orgQueue.length + docQueue.length;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <AdminNav />

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">
          {waiting > 0
            ? `${waiting} item${waiting === 1 ? '' : 's'} waiting on a reviewer.`
            : 'Nothing is waiting on a reviewer right now.'}
        </p>
      </header>

      {error && <div className="bg-amber-100 text-amber-900 p-3 rounded mb-4">{error}</div>}

      <section aria-label="Waiting on you" className="grid gap-4 sm:grid-cols-2 mb-8">
        <Link href="/admin" className="block">
          <div className={`rounded-lg border p-4 ${orgQueue.length ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'}`}>
            <p className="text-sm text-gray-600">Organisations awaiting verification</p>
            <p className="text-2xl font-semibold text-gray-900 mt-1">{orgQueue.length}</p>
            <p className="text-xs text-blue-700 mt-1">Open the verification queue →</p>
          </div>
        </Link>
        <Link href="/admin/documents" className="block">
          <div className={`rounded-lg border p-4 ${docQueue.length ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'}`}>
            <p className="text-sm text-gray-600">Documents awaiting review</p>
            <p className="text-2xl font-semibold text-gray-900 mt-1">{docQueue.length}</p>
            <p className="text-xs text-blue-700 mt-1">Open the document queue →</p>
          </div>
        </Link>
      </section>

      {data && (
        <>
          <section aria-label="Platform totals" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-8">
            <Stat label="NGOs" value={data.total_ngos} hint={`${data.verified_ngos} verified`} />
            <Stat label="Campaigns" value={data.total_campaigns} hint={`${data.live_campaigns} live`} />
            <Stat label="Donors" value={data.total_donors} />
            <Stat label="Total raised" value={rupees(data.total_fundraising)} />
            <Stat
              label="Email queue"
              value={data.email_queue_health.queue_depth}
              hint={`${data.email_queue_health.failed_count} failed`}
            />
            <Stat
              label="Email open rate"
              value={`${Math.round(data.engagement.open_rate * 100)}%`}
              hint={`${data.engagement.total_sent} sent`}
            />
          </section>

          <section aria-label="Top campaigns" className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Top campaigns</h2>
            {data.top_campaigns.length === 0 ? (
              <p className="text-sm text-gray-500">No campaigns have raised anything yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border border-gray-200 rounded-lg">
                  <thead className="bg-gray-50 text-left">
                    <tr>
                      <th className="px-3 py-2 font-medium">Campaign</th>
                      <th className="px-3 py-2 font-medium">NGO</th>
                      <th className="px-3 py-2 font-medium text-right">Raised</th>
                      <th className="px-3 py-2 font-medium text-right">Donations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_campaigns.map((c) => (
                      <tr key={c.campaign_id} className="border-t border-gray-200">
                        <td className="px-3 py-2 text-gray-900">{c.title}</td>
                        <td className="px-3 py-2 text-gray-600">{c.ngo_name}</td>
                        <td className="px-3 py-2 text-right">{rupees(c.amount_raised)}</td>
                        <td className="px-3 py-2 text-right">{c.donation_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
