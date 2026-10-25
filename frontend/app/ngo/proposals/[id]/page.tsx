'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import ProposalMessages from '@/components/ProposalMessages';
import DeliveryMilestones from '@/components/DeliveryMilestones';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

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

const STATUS_TONE: Record<string, BadgeTone> = {
  APPROVED: 'approved',
  ADMIN_REJECTED: 'rejected',
  CHANGES_REQUESTED: 'rejected',
  SUBMITTED: 'pending',
  PENDING_CSR: 'pending',
};

export default function NGOProposalDetailPage() {
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

    api<Proposal>(`/ngo/proposals/${params.id}`)
      .then((data) => setProposal(data))
      .catch(() => setError('Failed to load proposal'))
      .finally(() => setLoading(false));
  }, [params.id, router]);

  if (loading) return <p className="text-muted">Loading proposal…</p>;
  if (error) {
    return (
      <div role="alert" className="rounded-sm border-2 border-status-rejected bg-white p-4 text-sm text-status-rejected">
        {error}
      </div>
    );
  }
  if (!proposal) return <p className="text-muted">Proposal not found</p>;

  const statusTone = STATUS_TONE[proposal.status] ?? 'neutral';

  const statusLabel =
    proposal.status === 'SUBMITTED'
      ? 'Awaiting Imparency review'
      : proposal.status === 'PENDING_CSR'
      ? 'Awaiting CSR review'
      : proposal.status === 'ADMIN_REJECTED'
      ? 'Not accepted by Imparency'
      : proposal.status;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`Opportunity ${proposal.opportunity_id}`}
        title={`Proposal v${proposal.version_num}`}
        action={<Badge tone={statusTone}>{statusLabel}</Badge>}
      />

      <Card className="space-y-6 p-8">
        <div>
          <h2 className="mb-2 font-display text-xl font-semibold text-navy">Problem Statement</h2>
          <p className="whitespace-pre-wrap text-ink">{proposal.problem_statement}</p>
        </div>

        <div>
          <h2 className="mb-2 font-display text-xl font-semibold text-navy">Solution</h2>
          <p className="whitespace-pre-wrap text-ink">{proposal.solution}</p>
        </div>

        <div className="grid grid-cols-2 gap-6 border-t border-line pt-6">
          <div>
            <h3 className="font-semibold text-navy">Budget Requested</h3>
            <p className="text-2xl font-display font-bold text-status-approved">
              ₹{(proposal.budget_requested / 100000).toFixed(1)}L
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-navy">Timeline</h3>
            <p className="text-lg text-ink">{proposal.timeline}</p>
          </div>
        </div>

        <div className="border-t border-line pt-6">
          <h2 className="mb-2 font-display text-xl font-semibold text-navy">Expected Outcomes</h2>
          <p className="whitespace-pre-wrap text-ink">{proposal.expected_outcomes}</p>
        </div>

        <div className="border-t border-line pt-4 font-mono text-xs text-muted">
          <p>Created: {new Date(proposal.created_at).toLocaleString()}</p>
          <p>Last Updated: {new Date(proposal.updated_at).toLocaleString()}</p>
        </div>
      </Card>

      <Card className="p-8">
        <h2 className="mb-6 font-display text-xl font-semibold text-navy">Communication with CSR</h2>
        <ProposalMessages proposalId={params.id as string} currentUserType="NGO" />
      </Card>

      <Card className="p-8">
        <DeliveryMilestones proposalId={params.id as string} role="NGO" />
      </Card>

      <div className="flex gap-4">
        {(proposal.status === 'CHANGES_REQUESTED' || proposal.status === 'ADMIN_REJECTED') && (
          <Button variant="primary" onClick={() => router.push(`/ngo/proposals/${params.id}/edit`)}>
            Update Proposal
          </Button>
        )}
        <Button variant="secondary" onClick={() => router.back()}>
          Back
        </Button>
      </div>
    </div>
  );
}
