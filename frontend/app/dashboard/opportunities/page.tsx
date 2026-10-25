'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';

interface Opportunity {
  id: string;
  title: string;
  description: string;
  status: string;
  sectors: string[];
  geographies: string[];
  budget_min: number;
  budget_max: number;
  deadline: string;
  created_at: string;
}

const STATUS_TONE: Record<string, BadgeTone> = {
  PUBLISHED: 'approved',
  DRAFT: 'pending',
};

export default function OpportunitiesPage() {
  const router = useRouter();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    api<Opportunity[]>('/csr/opportunities')
      .then(data => setOpportunities(data || []))
      .catch(() => setError('Failed to load opportunities'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <p className="text-muted">Loading opportunities…</p>;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="CSR"
        title="My Opportunities"
        action={
          <Link
            href="/csr/opportunities/create"
            className="inline-flex items-center justify-center gap-2 rounded-sm bg-teal px-5 py-2.5 font-display text-sm font-medium text-paper shadow-sm transition-all hover:opacity-90 hover:shadow-md"
          >
            Create Opportunity
          </Link>
        }
      />

      {error && (
        <div role="alert" className="rounded-sm border-2 border-status-rejected bg-white p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {opportunities.length === 0 ? (
        <EmptyState title="No opportunities yet" description="Create an opportunity so NGOs can submit proposals against it." />
      ) : (
        <div className="grid gap-4">
          {opportunities.map(opp => (
            <Card key={opp.id} interactive className="p-6">
              <div className="mb-2 flex items-start justify-between gap-4">
                <h3 className="font-display text-xl font-semibold text-navy">{opp.title}</h3>
                <Badge tone={STATUS_TONE[opp.status] ?? 'neutral'}>{opp.status}</Badge>
              </div>
              <p className="mb-3 text-sm text-muted">{opp.description}</p>

              <div className="mb-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-semibold text-navy">Budget:</span>{' '}
                  <span className="text-ink">
                    ${(opp.budget_min / 100000).toFixed(1)}M - ${(opp.budget_max / 100000).toFixed(1)}M
                  </span>
                </div>
                <div>
                  <span className="font-semibold text-navy">Deadline:</span>{' '}
                  <span className="text-ink">{new Date(opp.deadline).toLocaleDateString()}</span>
                </div>
                <div className="col-span-2">
                  <span className="font-semibold text-navy">Sectors:</span>{' '}
                  <span className="text-ink">{opp.sectors.join(', ')}</span>
                </div>
                <div className="col-span-2">
                  <span className="font-semibold text-navy">Geographies:</span>{' '}
                  <span className="text-ink">{opp.geographies.join(', ')}</span>
                </div>
              </div>

              <div className="flex gap-4 text-sm font-medium">
                <Link href={`/csr/opportunities/${opp.id}`} className="text-teal hover:underline">
                  View
                </Link>
                {opp.status === 'DRAFT' && (
                  <Link href={`/csr/opportunities/${opp.id}/publish`} className="text-status-approved hover:underline">
                    Publish
                  </Link>
                )}
                {opp.status === 'PUBLISHED' && (
                  <Link href={`/csr/opportunities/${opp.id}/shortlist`} className="text-navy hover:underline">
                    Create Shortlist
                  </Link>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
