'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function ApprovePage() {
  const router = useRouter();
  const params = useParams()!;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleApprove = async () => {
    setLoading(true);
    setError('');

    try {
      await api(`/csr/proposals/${params.id}/approve`, { method: 'POST' });
      router.push('/csr/proposals');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader eyebrow="CSR workspace" title="Approve Proposal" />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      <Card className="border-2 border-status-approved/40 bg-status-approved/5 p-6">
        <h2 className="mb-2 text-lg font-semibold text-navy">Approve this proposal?</h2>
        <p className="mb-4 text-ink">
          Approving this proposal will create a financial commitment for the budget amount requested.
        </p>
        <p className="text-muted">This action is final and will be recorded in the audit log.</p>
      </Card>

      <div className="flex gap-4">
        <Button variant="primary" onClick={handleApprove} disabled={loading}>
          {loading ? 'Approving...' : 'Confirm & Approve'}
        </Button>
        <Button variant="secondary" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
