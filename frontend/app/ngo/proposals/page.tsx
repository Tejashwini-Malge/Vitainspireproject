'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';

interface Proposal {
  id: string;
  proposal_id: string;
  opportunity_id: string;
  version_num: number;
  status: string;
  problem_statement: string;
  budget_requested: number;
  created_at: string;
}

const STATUS_TONE: Record<string, BadgeTone> = {
  APPROVED: 'approved',
  ADMIN_REJECTED: 'rejected',
  CHANGES_REQUESTED: 'rejected',
  SUBMITTED: 'pending',
  PENDING_CSR: 'pending',
};

function statusLabel(status: string): string {
  if (status === 'SUBMITTED') return 'Awaiting Imparency review';
  if (status === 'PENDING_CSR') return 'Awaiting CSR review';
  if (status === 'ADMIN_REJECTED') return 'Not accepted by Imparency';
  return status;
}

export default function NGOProposalsPage() {
  const router = useRouter();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    api<Proposal[]>('/ngo/proposals')
      .then(data => setProposals(data || []))
      .catch(() => setError('Failed to load proposals'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <p className="text-muted">Loading proposals…</p>;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="NGO"
        title="My Proposals"
        action={
          <div className="flex items-center gap-4">
            <NotificationBell />
            <Link
              href="/ngo/proposals/create"
              className="inline-flex items-center justify-center gap-2 rounded-sm bg-teal px-5 py-2.5 font-display text-sm font-medium text-paper shadow-sm transition-all hover:opacity-90 hover:shadow-md"
            >
              Submit Proposal
            </Link>
          </div>
        }
      />

      {error && (
        <div role="alert" className="rounded-sm border-2 border-status-rejected bg-white p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {proposals.length === 0 ? (
        <EmptyState
          title="No proposals yet"
          description="Submit your first proposal to a published opportunity."
          action={
            <Link
              href="/ngo/proposals/create"
              className="inline-flex items-center justify-center gap-2 rounded-sm bg-teal px-5 py-2.5 font-display text-sm font-medium text-paper shadow-sm transition-all hover:opacity-90 hover:shadow-md"
            >
              Submit your first proposal
            </Link>
          }
        />
      ) : (
        <ul className="space-y-4">
          {proposals.map((proposal, i) => (
            <motion.li
              key={proposal.id}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
            >
              <Card interactive className="p-6">
                <div className="mb-4 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-display text-xl font-semibold text-navy">
                      Proposal v{proposal.version_num}
                    </h2>
                    <p className="mt-1 text-sm text-muted">{proposal.problem_statement.substring(0, 100)}...</p>
                  </div>
                  <Badge tone={STATUS_TONE[proposal.status] ?? 'neutral'}>{statusLabel(proposal.status)}</Badge>
                </div>

                <div className="mb-6 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-semibold text-navy">Budget Requested:</span>{' '}
                    <span className="text-ink">₹{(proposal.budget_requested / 100000).toFixed(1)}L</span>
                  </div>
                  <div>
                    <span className="font-semibold text-navy">Submitted:</span>{' '}
                    <span className="text-ink">{new Date(proposal.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                <div className="flex gap-4">
                  <Link href={`/ngo/proposals/${proposal.id}`} className="text-sm font-medium text-teal hover:underline">
                    View Details
                  </Link>
                  {(proposal.status === 'CHANGES_REQUESTED' || proposal.status === 'ADMIN_REJECTED') && (
                    <Link
                      href={`/ngo/proposals/${proposal.id}/edit`}
                      className="text-sm font-medium text-status-pending hover:underline"
                    >
                      Update Proposal
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
