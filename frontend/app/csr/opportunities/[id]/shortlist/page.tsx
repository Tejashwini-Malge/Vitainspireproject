'use client';

import { useRouter, useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

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
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Select NGOs for Shortlist</h1>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      <div className="space-y-3 mb-8">
        {ngos.map(ngo => (
          <label key={ngo.id} className="flex items-center p-4 border rounded hover:bg-gray-50">
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
              className="mr-4 w-4 h-4"
            />
            <span className="font-medium">{ngo.name}</span>
          </label>
        ))}
      </div>

      <div className="flex gap-4">
        <button
          onClick={handleSubmit}
          disabled={loading || selected.length === 0}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Creating...' : `Create Shortlist (${selected.length} NGOs)`}
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
