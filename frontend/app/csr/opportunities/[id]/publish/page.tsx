'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState } from 'react';
import { api } from '@/lib/api';

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
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Publish Opportunity</h1>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 mb-8">
        <h2 className="font-bold text-lg mb-2">Ready to publish?</h2>
        <p className="text-gray-700 mb-4">
          Publishing this opportunity will make it visible to all NGOs. They will be able to view details and submit proposals.
        </p>
        <p className="text-gray-600">You can create a shortlist after publishing to invite specific NGOs.</p>
      </div>

      <div className="flex gap-4">
        <button
          onClick={handlePublish}
          disabled={loading}
          className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? 'Publishing...' : 'Confirm & Publish'}
        </button>
        <button
          onClick={() => router.back()}
          className="bg-gray-300 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-400"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
