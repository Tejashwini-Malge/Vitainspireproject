'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { api, getToken } from '@/lib/api';
import ProposalMessages from '@/components/ProposalMessages';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { BadgeTone } from '@/components/ui/badge';

interface Proposal {
  id: string;
  proposal_id: string;
  opportunity_id: string;
  ngo_id: string;
  version_num: number;
  status: string;
  problem_statement: string;
  solution: string;
  budget_requested: number;
  timeline: string;
  expected_outcomes: string;
  created_at: string;
  updated_at: string;
}

export default function CSRProposalDetailPage() {
  const router = useRouter();
  const params = useParams()!;
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }

    api<Proposal>(`/csr/proposals/${params.id}`)
      .then((data) => setProposal(data))
      .catch(() => setError('Failed to load proposal'))
      .finally(() => setLoading(false));
  }, [params.id, router]);

  if (loading) return <p className="text-muted">Loading…</p>;
  if (error) return <p role="alert" className="text-status-rejected">{error}</p>;
  if (!proposal) return <p className="text-muted">Proposal not found</p>;

  const statusTone: BadgeTone =
    proposal.status === 'PENDING_CSR'
      ? 'pending'
      : proposal.status === 'CHANGES_REQUESTED'
      ? 'rejected'
      : 'neutral';

  const statusLabel = proposal.status === 'PENDING_CSR' ? 'Awaiting your review' : proposal.status;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`NGO ID: ${proposal.ngo_id}`}
        title={`Proposal Review v${proposal.version_num}`}
        action={<Badge tone={statusTone}>{statusLabel}</Badge>}
      />

      {/* Proposal Details */}
      <Card className="space-y-6 p-8">
        <div>
          <h2 className="mb-2 text-lg font-semibold text-navy">Problem Statement</h2>
          <p className="whitespace-pre-wrap text-ink">{proposal.problem_statement}</p>
        </div>

        <div>
          <h2 className="mb-2 text-lg font-semibold text-navy">Solution</h2>
          <p className="whitespace-pre-wrap text-ink">{proposal.solution}</p>
        </div>

        <div className="grid grid-cols-2 gap-6 border-t border-line pt-6">
          <div>
            <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Budget Requested</h3>
            <p className="mt-1 text-2xl font-semibold text-navy">₹{(proposal.budget_requested / 100000).toFixed(1)}L</p>
          </div>
          <div>
            <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Timeline</h3>
            <p className="mt-1 text-lg text-ink">{proposal.timeline}</p>
          </div>
        </div>

        <div>
          <h2 className="mb-2 text-lg font-semibold text-navy">Expected Outcomes</h2>
          <p className="whitespace-pre-wrap text-ink">{proposal.expected_outcomes}</p>
        </div>

        <div className="border-t border-line pt-4 text-sm text-muted">
          <p>Submitted: {new Date(proposal.created_at).toLocaleString()}</p>
          <p>Last Updated: {new Date(proposal.updated_at).toLocaleString()}</p>
        </div>
      </Card>

      {/* Messaging Section */}
      <Card className="p-8">
        <h2 className="mb-6 text-lg font-semibold text-navy">Communication with NGO</h2>
        <ProposalMessages proposalId={params.id as string} currentUserType="CSR" />
      </Card>

      {/* Decision Actions */}
      {proposal.status === 'PENDING_CSR' && (
        <Card className="border-2 border-navy/20 bg-navy/5 p-8">
          <h2 className="mb-4 text-lg font-semibold text-navy">Decision</h2>
          <p className="mb-6 text-ink">
            After reviewing this proposal and communicating with the NGO, you can approve or request changes.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href={`/csr/proposals/${params.id}/approve`}>
              <Button variant="primary">Approve Proposal</Button>
            </Link>
            <Link href={`/csr/proposals/${params.id}/request-changes`}>
              <Button variant="danger">Request Changes</Button>
            </Link>
          </div>
        </Card>
      )}

      {/* Navigation */}
      <Button variant="ghost" onClick={() => router.back()}>
        Back
      </Button>
    </div>
  );
}
