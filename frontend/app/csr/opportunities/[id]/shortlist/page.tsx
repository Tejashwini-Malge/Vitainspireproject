'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';

/** A ranked candidate from GET /csr/opportunities/{id}/fit-scores. */
interface FitScore {
  ngo_id: string;
  ngo_name: string;
  sectors: string[];
  score: number;
  explanation: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
}

const CONFIDENCE_TONE = {
  HIGH: 'approved',
  MEDIUM: 'pending',
  LOW: 'neutral',
} as const;

export default function ShortlistPage() {
  const router = useRouter();
  const params = useParams()!;
  const [candidates, setCandidates] = useState<FitScore[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setCandidates(await api<FitScore[]>(`/csr/opportunities/${params.id}/fit-scores`));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load candidates');
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Rankings are cached after the first run, so an NGO that published a profile or had a
  // document approved since then will not move until the CSR asks for a fresh run.
  const handleRefresh = async () => {
    setRefreshing(true);
    setError('');
    try {
      setCandidates(
        await api<FitScore[]>(`/csr/opportunities/${params.id}/fit-scores/compute`, { method: 'POST' }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh ranking');
    } finally {
      setRefreshing(false);
    }
  };

  const handleSubmit = async () => {
    if (selected.length === 0) {
      setError('Please select at least one NGO');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api('/csr/opportunities/shortlist', {
        method: 'POST',
        body: JSON.stringify({
          opportunity_id: params.id,
          ngo_ids: selected,
        }),
      });
      router.push(`/csr/opportunities/${params.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create shortlist');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        eyebrow="CSR workspace"
        title="Select NGOs for Shortlist"
        description="Ranked by fit against this opportunity's sectors, geographies and compliance record. Scores are computed from verified data; the selection is yours."
      />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          {candidates.length} eligible {candidates.length === 1 ? 'NGO' : 'NGOs'}
        </p>
        <Button variant="secondary" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? 'Recalculating...' : 'Recalculate ranking'}
        </Button>
      </div>

      {candidates.length === 0 ? (
        <EmptyState
          title="No eligible NGOs"
          description="An NGO appears here once it is verified, has published its profile, and has all four required compliance documents approved."
        />
      ) : (
        <Card className="divide-y divide-line p-0">
          {candidates.map(c => (
            <label key={c.ngo_id} className="flex cursor-pointer items-start gap-4 px-4 py-4 transition-colors hover:bg-navy/5">
              <input
                type="checkbox"
                checked={selected.includes(c.ngo_id)}
                onChange={e => {
                  if (e.target.checked) {
                    setSelected([...selected, c.ngo_id]);
                  } else {
                    setSelected(selected.filter(id => id !== c.ngo_id));
                  }
                }}
                className="mt-1 h-4 w-4 shrink-0 accent-teal"
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-navy">{c.ngo_name}</span>
                  <Badge tone="neutral">{c.score}/100 fit</Badge>
                  <Badge tone={CONFIDENCE_TONE[c.confidence]}>{c.confidence} confidence</Badge>
                </span>
                <span className="mt-1 block text-sm text-muted">{c.explanation}</span>
                {c.sectors.length > 0 && (
                  <span className="mt-1 block font-mono text-[0.7rem] uppercase tracking-wide text-muted">
                    {c.sectors.join(' · ')}
                  </span>
                )}
              </span>
            </label>
          ))}
        </Card>
      )}

      <div className="flex gap-4">
        <Button variant="primary" onClick={handleSubmit} disabled={loading || selected.length === 0}>
          {loading ? 'Creating...' : `Create Shortlist (${selected.length} NGOs)`}
        </Button>
        <Button variant="secondary" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
