'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ShieldCheck, FileCheck2 } from 'lucide-react';
import { api, ApiError, clearToken, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import { StatCard } from '@/components/admin/StatCard';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { cn } from '@/components/ui/cn';
import type { AdminDashboard, AdminQueueItem, Org } from '@/lib/types';

function rupees(minor: number): string {
  return `₹${Math.round(minor / 100).toLocaleString('en-IN')}`;
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

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl p-8">
        <AdminNav />
        <p className="text-muted">Loading dashboard…</p>
      </div>
    );
  }

  const waiting = orgQueue.length + docQueue.length;

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-8">
      <AdminNav />

      <PageHeader
        eyebrow="Admin"
        title="Dashboard"
        description={
          waiting > 0
            ? `${waiting} item${waiting === 1 ? '' : 's'} waiting on a reviewer.`
            : 'Nothing is waiting on a reviewer right now.'
        }
      />

      {error && (
        <div className="rounded-sm border border-status-pending/40 bg-status-pending/10 p-3 text-sm text-status-pending">
          {error}
        </div>
      )}

      <section aria-label="Waiting on you" className="grid gap-4 sm:grid-cols-2">
        <Link href="/admin" className="block">
          <Card
            interactive
            className={cn(
              'flex items-start gap-3 p-4',
              orgQueue.length > 0 && 'border-teal/50 bg-teal/5',
            )}
          >
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-teal" aria-hidden />
            <div>
              <p className="text-sm text-muted">Organisations awaiting verification</p>
              <p className="mt-1 font-display text-2xl font-semibold text-navy">{orgQueue.length}</p>
              <p className="mt-1 text-xs font-medium text-teal">Open the verification queue →</p>
            </div>
          </Card>
        </Link>
        <Link href="/admin/documents" className="block">
          <Card
            interactive
            className={cn(
              'flex items-start gap-3 p-4',
              docQueue.length > 0 && 'border-teal/50 bg-teal/5',
            )}
          >
            <FileCheck2 className="mt-0.5 h-5 w-5 shrink-0 text-teal" aria-hidden />
            <div>
              <p className="text-sm text-muted">Documents awaiting review</p>
              <p className="mt-1 font-display text-2xl font-semibold text-navy">{docQueue.length}</p>
              <p className="mt-1 text-xs font-medium text-teal">Open the document queue →</p>
            </div>
          </Card>
        </Link>
      </section>

      {data && (
        <>
          <section aria-label="Platform totals" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { label: 'NGOs', value: data.total_ngos, subtitle: `${data.verified_ngos} verified`, color: 'teal' as const },
              { label: 'Campaigns', value: data.total_campaigns, subtitle: `${data.live_campaigns} live`, color: 'green' as const },
              { label: 'Donors', value: data.total_donors, color: 'blue' as const },
              { label: 'Total raised', value: rupees(data.total_fundraising), color: 'teal' as const },
              {
                label: 'Email queue',
                value: data.email_queue_health.queue_depth,
                subtitle: `${data.email_queue_health.failed_count} failed`,
                color: 'orange' as const,
              },
              {
                label: 'Email open rate',
                value: `${Math.round(data.engagement.open_rate * 100)}%`,
                subtitle: `${data.engagement.total_sent} sent`,
                color: 'blue' as const,
              },
            ].map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-40px' }}
                transition={{ duration: 0.35, delay: i * 0.05 }}
              >
                <StatCard label={stat.label} value={stat.value} subtitle={stat.subtitle} color={stat.color} />
              </motion.div>
            ))}
          </section>

          <section aria-label="Top campaigns">
            <h2 className="mb-3 font-display text-lg font-semibold text-navy">Top campaigns</h2>
            {data.top_campaigns.length === 0 ? (
              <p className="text-sm text-muted">No campaigns have raised anything yet.</p>
            ) : (
              <Card className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b-2 border-line text-left font-mono text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th className="px-4 py-3 font-medium">Campaign</th>
                      <th className="px-4 py-3 font-medium">NGO</th>
                      <th className="px-4 py-3 text-right font-medium">Raised</th>
                      <th className="px-4 py-3 text-right font-medium">Donations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_campaigns.map((c) => (
                      <tr key={c.campaign_id} className="border-t border-line">
                        <td className="px-4 py-3 font-medium text-navy">{c.title}</td>
                        <td className="px-4 py-3 text-muted">{c.ngo_name}</td>
                        <td className="px-4 py-3 text-right text-ink">{rupees(c.amount_raised)}</td>
                        <td className="px-4 py-3 text-right text-ink">{c.donation_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </section>
        </>
      )}
    </div>
  );
}
