'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api } from '@/lib/api';
import Link from 'next/link';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface Opportunity {
  id: string;
  title: string;
  description: string;
  sectors: string[];
  geographies: string[];
  budget_min: number;
  budget_max: number;
  deadline: string;
  requirements_text: string;
  status: string;
  created_at: string;
  published_at: string | null;
}

export default function OpportunityDetailPage() {
  const params = useParams()!;
  const router = useRouter();
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchOpportunity = async () => {
      try {
        const data = await api<Opportunity>(`/csr/opportunities/${params.id}`);
        setOpportunity(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch opportunity');
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      fetchOpportunity();
    }
  }, [params.id]);

  if (loading) {
    return <p className="text-muted">Loading…</p>;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    );
  }

  if (!opportunity) {
    return (
      <div className="space-y-4">
        <p className="text-muted">Opportunity not found</p>
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Button variant="ghost" size="sm" onClick={() => router.back()} className="-ml-3">
          ← Back
        </Button>
        <PageHeader
          eyebrow="CSR workspace"
          title={opportunity.title}
          description={`Created ${new Date(opportunity.created_at).toLocaleDateString()}`}
          action={<Badge tone={opportunity.status === 'PUBLISHED' ? 'approved' : 'pending'}>{opportunity.status}</Badge>}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className="p-4">
          <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Budget Range</h3>
          <p className="mt-2 text-2xl font-semibold text-navy">
            ₹{(opportunity.budget_min / 100000).toFixed(1)}L - ₹{(opportunity.budget_max / 100000).toFixed(1)}L
          </p>
        </Card>

        <Card className="p-4">
          <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Deadline</h3>
          <p className="mt-2 text-2xl font-semibold text-navy">
            {new Date(opportunity.deadline).toLocaleDateString()}
          </p>
        </Card>

        <Card className="p-4">
          <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Status</h3>
          <p className="mt-2 text-2xl font-semibold text-navy">
            {opportunity.status === 'PUBLISHED' ? '✓ Live' : 'Draft'}
          </p>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="mb-3 text-lg font-semibold text-navy">Description</h2>
        <p className="whitespace-pre-wrap text-ink">{opportunity.description}</p>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-navy">Sectors</h2>
          <div className="flex flex-wrap gap-2">
            {opportunity.sectors.map((sector) => (
              <Badge key={sector} tone="neutral">{sector}</Badge>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-navy">Geographies</h2>
          <div className="flex flex-wrap gap-2">
            {opportunity.geographies.map((geo) => (
              <Badge key={geo} tone="neutral">{geo}</Badge>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="mb-3 text-lg font-semibold text-navy">Requirements</h2>
        <p className="whitespace-pre-wrap text-ink">{opportunity.requirements_text}</p>
      </Card>

      {opportunity.status === 'DRAFT' && (
        <div className="flex flex-wrap gap-4">
          <Link href={`/csr/opportunities/${opportunity.id}/publish`}>
            <Button variant="primary">Publish Opportunity</Button>
          </Link>
          <Link href={`/csr/opportunities/${opportunity.id}/shortlist`}>
            <Button variant="secondary">Create Shortlist</Button>
          </Link>
        </div>
      )}

      {opportunity.status === 'PUBLISHED' && (
        <div className="flex flex-wrap gap-4">
          <Link href={`/csr/opportunities/${opportunity.id}/shortlist`}>
            <Button variant="secondary">Manage Shortlist</Button>
          </Link>
          <Link href={`/dashboard/opportunities`}>
            <Button variant="ghost">Back to Opportunities</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
