'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

export default function RequestChangesPage() {
  const router = useRouter();
  const params = useParams()!;
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedback.trim()) {
      setError('Please provide feedback');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api(`/csr/proposals/${params.id}/request-changes`, {
        method: 'POST',
        body: JSON.stringify({ feedback }),
      });
      router.push('/csr/proposals');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request changes');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader eyebrow="CSR workspace" title="Request Changes" />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="mb-2 block font-medium text-navy">Feedback for NGO</label>
            <Textarea
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              rows={6}
              placeholder="Please describe what changes are needed..."
              required
            />
          </div>

          <div className="flex gap-4 border-t border-line pt-6">
            <Button type="submit" variant="danger" disabled={loading}>
              {loading ? 'Sending...' : 'Send Request'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
