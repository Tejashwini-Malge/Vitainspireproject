'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';

interface NGO {
  id: string;
  name: string;
}

export default function ShortlistPage() {
  const router = useRouter();
  const params = useParams()!;
  const [ngos, setNgos] = useState<NGO[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api<(NGO & { org_type: string })[]>('/orgs/public/ngos')
      .then(data => setNgos(data))
      .catch(() => setError('Failed to load NGOs'));
  }, []);

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
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader eyebrow="CSR workspace" title="Select NGOs for Shortlist" />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      {ngos.length === 0 ? (
        <EmptyState title="No NGOs available" description="There are no verified NGOs to shortlist yet." />
      ) : (
        <Card className="divide-y divide-line p-0">
          {ngos.map(ngo => (
            <label key={ngo.id} className="flex cursor-pointer items-center gap-4 px-4 py-4 transition-colors hover:bg-navy/5">
              <input
                type="checkbox"
                checked={selected.includes(ngo.id)}
                onChange={e => {
                  if (e.target.checked) {
                    setSelected([...selected, ngo.id]);
                  } else {
                    setSelected(selected.filter(id => id !== ngo.id));
                  }
                }}
                className="h-4 w-4 accent-teal"
              />
              <span className="font-medium text-navy">{ngo.name}</span>
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
