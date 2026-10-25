'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Button } from '@/components/ui/button';

interface Opportunity {
  id: string;
  title: string;
  description: string;
  sectors: string[];
  geographies: string[];
  budget_min: number | null;
  budget_max: number | null;
  deadline: string;
  requirements_text: string;
}

interface ShortlistedOpportunity {
  opportunity: Opportunity;
  csr_org_id: string;
  csr_org_name: string;
  shortlisted_at: string;
  proposal_id: string | null;
  proposal_status: string | null;
  can_submit_proposal: boolean;
  blockers: string[];
}

const STATUS_TONE: Record<string, BadgeTone> = {
  APPROVED: 'approved',
  ADMIN_REJECTED: 'rejected',
  CHANGES_REQUESTED: 'rejected',
  SUBMITTED: 'pending',
  PENDING_CSR: 'pending',
};

function formatAmount(minor: number): string {
  return new Intl.NumberFormat('en-IN').format(Math.round(minor / 100));
}

/**
 * What a funder has actually invited this NGO to bid on.
 *
 * Distinct from the public opportunity feed: being shortlisted is the signal that a
 * specific CSR picked this organisation, and it is the only route to submitting a
 * proposal -- the API refuses proposals from NGOs that were not shortlisted.
 */
export default function NgoOpportunitiesPage() {
  const router = useRouter();
  const [items, setItems] = useState<ShortlistedOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    api<ShortlistedOpportunity[]>('/ngo/opportunities')
      .then(data => setItems(data || []))
      .catch(() => setError('Failed to load your invitations'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <p className="text-muted">Loading invitations…</p>;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="NGO workspace"
        title="You've been shortlisted"
        description="Funders who selected your organisation for a specific opportunity. Submit a proposal, or discuss budget and timeline with them first."
      />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      {items.length === 0 ? (
        <EmptyState
          title="No invitations yet"
          description="When a corporate funder shortlists your organisation for an opportunity, it appears here."
        />
      ) : (
        <div className="space-y-4">
          {items.map(item => (
            <Card key={item.opportunity.id} className="space-y-3 p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-display text-lg font-semibold text-navy">{item.opportunity.title}</h2>
                  <p className="text-sm text-muted">
                    Shortlisted by {item.csr_org_name} on{' '}
                    {new Date(item.shortlisted_at).toLocaleDateString()}
                  </p>
                </div>
                {item.proposal_status && (
                  <Badge tone={STATUS_TONE[item.proposal_status] ?? 'neutral'}>{item.proposal_status}</Badge>
                )}
              </div>

              <p className="text-muted">{item.opportunity.description}</p>

              <p className="font-mono text-[0.7rem] uppercase tracking-wide text-muted">
                Deadline {new Date(item.opportunity.deadline).toLocaleDateString()}
                {item.opportunity.budget_min != null && item.opportunity.budget_max != null && (
                  <>
                    {' · '}₹{formatAmount(item.opportunity.budget_min)}–₹
                    {formatAmount(item.opportunity.budget_max)}
                  </>
                )}
                {item.opportunity.sectors.length > 0 && <> · {item.opportunity.sectors.join(' · ')}</>}
              </p>

              {item.blockers.length > 0 && (
                <div className="rounded-sm border border-status-pending/40 bg-status-pending/10 px-4 py-3 text-sm text-status-pending">
                  <p className="font-medium">Before you can submit a proposal:</p>
                  <ul className="mt-1 list-inside list-disc">
                    {item.blockers.map(b => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex flex-wrap gap-3 pt-1">
                {item.proposal_id ? (
                  <Link href={`/ngo/proposals/${item.proposal_id}`}>
                    <Button variant="primary">View your proposal</Button>
                  </Link>
                ) : item.can_submit_proposal ? (
                  <Link href={`/ngo/proposals/create?opportunity_id=${item.opportunity.id}`}>
                    <Button variant="primary">Submit a proposal</Button>
                  </Link>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
