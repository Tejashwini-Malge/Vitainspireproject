'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function PublishPage() {
  const router = useRouter();
  const params = useParams()!;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handlePublish = async () => {
    setLoading(true);
    setError('');

    try {
      await api(`/csr/opportunities/${params.id}/publish`, { method: 'POST' });
      router.push(`/csr/opportunities/${params.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader eyebrow="CSR workspace" title="Publish Opportunity" />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      <Card className="border-2 border-status-pending/40 bg-status-pending/5 p-6">
        <h2 className="mb-2 text-lg font-semibold text-navy">Ready to publish?</h2>
        <p className="mb-4 text-ink">
          Publishing this opportunity will make it visible to all NGOs. They will be able to view details and submit proposals.
        </p>
        <p className="text-muted">You can create a shortlist after publishing to invite specific NGOs.</p>
      </Card>

      <div className="flex gap-4">
        <Button variant="primary" onClick={handlePublish} disabled={loading}>
          {loading ? 'Publishing...' : 'Confirm & Publish'}
        </Button>
        <Button variant="secondary" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
