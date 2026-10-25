'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { api, getToken } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
}

export default function CSROpportunitiesPage() {
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

  if (loading) return <p className="text-muted">Loading…</p>;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="CSR workspace"
        title="My Opportunities"
        description="Funding opportunities you have posted for NGOs to apply against."
        action={
          <Link href="/csr/opportunities/create">
            <Button variant="primary">Create Opportunity</Button>
          </Link>
        }
      />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      {opportunities.length === 0 ? (
        <EmptyState
          title="No opportunities yet"
          description="Post your first funding opportunity to start receiving proposals from NGOs."
          action={
            <Link href="/csr/opportunities/create">
              <Button variant="secondary" size="sm">Create your first opportunity</Button>
            </Link>
          }
        />
      ) : (
        <ul className="space-y-4">
          {opportunities.map((opp, i) => (
            <motion.li
              key={opp.id}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.35, delay: Math.min(i, 6) * 0.05 }}
            >
              <Card className="p-6">
                <div className="mb-4 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-navy">{opp.title}</h2>
                    <p className="mt-1 text-muted">{opp.description}</p>
                  </div>
                  <Badge tone={opp.status === 'PUBLISHED' ? 'approved' : 'pending'} className="whitespace-nowrap">
                    {opp.status}
                  </Badge>
                </div>

                <div className="mb-6 grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm text-ink">
                  <div>
                    <span className="font-semibold text-navy">Budget:</span> ₹{(opp.budget_min / 100000).toFixed(1)}L - ₹{(opp.budget_max / 100000).toFixed(1)}L
                  </div>
                  <div>
                    <span className="font-semibold text-navy">Deadline:</span> {new Date(opp.deadline).toLocaleDateString()}
                  </div>
                  <div className="col-span-2">
                    <span className="font-semibold text-navy">Sectors:</span> {opp.sectors.join(', ')}
                  </div>
                  <div className="col-span-2">
                    <span className="font-semibold text-navy">Geographies:</span> {opp.geographies.join(', ')}
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link href={`/csr/opportunities/${opp.id}`}>
                    <Button variant="ghost" size="sm">View Details</Button>
                  </Link>
                  {opp.status === 'DRAFT' && (
                    <Link href={`/csr/opportunities/${opp.id}/publish`}>
                      <Button variant="secondary" size="sm">Publish</Button>
                    </Link>
                  )}
                  {opp.status === 'PUBLISHED' && (
                    <Link href={`/csr/opportunities/${opp.id}/shortlist`}>
                      <Button variant="secondary" size="sm">Create Shortlist</Button>
                    </Link>
                  )}
                </div>
              </Card>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  );
}
