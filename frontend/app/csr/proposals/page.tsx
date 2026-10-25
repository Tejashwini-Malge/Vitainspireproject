'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';

interface Proposal {
  id: string;
  proposal_id: string;
  opportunity_id: string;
  ngo_id: string;
  version_num: number;
  status: string;
  problem_statement: string;
  budget_requested: number;
  created_at: string;
}

export default function CSRProposalsPage() {
  const router = useRouter();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }

    api<Proposal[]>('/csr/proposals')
      .then(data => setProposals(data || []))
      .catch(() => setError('Failed to load proposals'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <p className="text-muted">Loading…</p>;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="CSR workspace"
        title="Proposals for Review"
        description="Proposals submitted by NGOs against your funding opportunities."
        action={<NotificationBell />}
      />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      {proposals.length === 0 ? (
        <EmptyState title="No proposals pending review" description="Proposals submitted against your opportunities will show up here." />
      ) : (
        <ul className="space-y-4">
          {proposals.map((proposal, i) => (
            <motion.li
              key={proposal.id}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.35, delay: Math.min(i, 6) * 0.05 }}
            >
              <Card className="p-6">
                <div className="mb-4 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-navy">
                      Proposal v{proposal.version_num}
                    </h2>
                    <p className="mt-1 text-muted">{proposal.problem_statement.substring(0, 100)}...</p>
                  </div>
                  <Badge tone={proposal.status === 'PENDING_CSR' ? 'pending' : 'neutral'} className="whitespace-nowrap">
                    {proposal.status === 'PENDING_CSR' ? 'Awaiting your review' : proposal.status}
                  </Badge>
                </div>

                <div className="mb-6 grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm text-ink">
                  <div>
                    <span className="font-semibold text-navy">Budget Requested:</span> ₹{(proposal.budget_requested / 100000).toFixed(1)}L
                  </div>
                  <div>
                    <span className="font-semibold text-navy">Submitted:</span> {new Date(proposal.created_at).toLocaleDateString()}
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link href={`/csr/proposals/${proposal.id}`}>
                    <Button variant="ghost" size="sm">Review Details</Button>
                  </Link>
                  <Link href={`/csr/proposals/${proposal.id}/approve`}>
                    <Button variant="secondary" size="sm">Approve</Button>
                  </Link>
                  <Link href={`/csr/proposals/${proposal.id}/request-changes`}>
                    <Button variant="danger" size="sm">Request Changes</Button>
                  </Link>
                </div>
              </Card>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  );
}
