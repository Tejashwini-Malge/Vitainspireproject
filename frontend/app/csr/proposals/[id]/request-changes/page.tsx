'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState } from 'react';
import { api } from '@/lib/api';

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
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Request Changes</h1>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block font-semibold mb-2">Feedback for NGO</label>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            className="w-full border rounded px-4 py-2"
            rows={6}
            placeholder="Please describe what changes are needed..."
            required
          />
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="bg-orange-600 text-white px-6 py-2 rounded-lg hover:bg-orange-700 disabled:opacity-50"
          >
            {loading ? 'Sending...' : 'Send Request'}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="bg-gray-300 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-400"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
