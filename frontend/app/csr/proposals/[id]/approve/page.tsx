'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState } from 'react';
import { api } from '@/lib/api';

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
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Approve Proposal</h1>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-8">
        <h2 className="font-bold text-lg mb-2">Approve this proposal?</h2>
        <p className="text-gray-700 mb-4">
          Approving this proposal will create a financial commitment for the budget amount requested.
        </p>
        <p className="text-gray-600">This action is final and will be recorded in the audit log.</p>
      </div>

      <div className="flex gap-4">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? 'Approving...' : 'Confirm & Approve'}
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
