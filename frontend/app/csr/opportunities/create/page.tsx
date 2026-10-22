'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function CreateOpportunityPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    sectors: [] as string[],
    geographies: [] as string[],
    budget_min: '',
    budget_max: '',
    deadline: '',
    requirements_text: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const data = await api<{ id: string }>('/csr/opportunities', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          sectors: formData.sectors.filter(s => s),
          geographies: formData.geographies.filter(g => g),
          budget_min: parseInt(formData.budget_min),
          budget_max: parseInt(formData.budget_max),
        }),
      });
      router.push(`/csr/opportunities/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create opportunity');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Create New Opportunity</h1>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block font-semibold mb-2">Title</label>
          <input
            type="text"
            value={formData.title}
            onChange={e => setFormData({ ...formData, title: e.target.value })}
            className="w-full border rounded px-4 py-2"
            minLength={5}
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Description</label>
          <textarea
            value={formData.description}
            onChange={e => setFormData({ ...formData, description: e.target.value })}
            className="w-full border rounded px-4 py-2"
            rows={4}
            minLength={10}
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block font-semibold mb-2">Budget Min (₹)</label>
            <input
              type="number"
              value={formData.budget_min}
              onChange={e => setFormData({ ...formData, budget_min: e.target.value })}
              className="w-full border rounded px-4 py-2"
              required
            />
          </div>
          <div>
            <label className="block font-semibold mb-2">Budget Max (₹)</label>
            <input
              type="number"
              value={formData.budget_max}
              onChange={e => setFormData({ ...formData, budget_max: e.target.value })}
              className="w-full border rounded px-4 py-2"
              required
            />
          </div>
        </div>

        <div>
          <label className="block font-semibold mb-2">Deadline</label>
          <input
            type="date"
            value={formData.deadline}
            onChange={e => setFormData({ ...formData, deadline: e.target.value })}
            className="w-full border rounded px-4 py-2"
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Sectors (comma-separated)</label>
          <input
            type="text"
            value={formData.sectors.join(', ')}
            onChange={e => setFormData({ ...formData, sectors: e.target.value.split(',').map(s => s.trim()) })}
            className="w-full border rounded px-4 py-2"
            placeholder="health, education, water"
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Geographies (comma-separated)</label>
          <input
            type="text"
            value={formData.geographies.join(', ')}
            onChange={e => setFormData({ ...formData, geographies: e.target.value.split(',').map(g => g.trim()) })}
            className="w-full border rounded px-4 py-2"
            placeholder="Karnataka, Tamil Nadu"
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Requirements</label>
          <textarea
            value={formData.requirements_text}
            onChange={e => setFormData({ ...formData, requirements_text: e.target.value })}
            className="w-full border rounded px-4 py-2"
            rows={3}
            minLength={10}
            required
          />
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Opportunity'}
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
