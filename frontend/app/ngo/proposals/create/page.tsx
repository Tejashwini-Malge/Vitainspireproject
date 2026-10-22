'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

interface Opportunity {
  id: string;
  title: string;
  org_id: string;
}

export default function CreateProposalPage() {
  const router = useRouter();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    opportunity_id: '',
    problem_statement: '',
    solution: '',
    budget_requested: '',
    timeline: '',
    expected_outcomes: '',
  });

  useEffect(() => {
    api<(Opportunity & { status: string })[]>('/csr/opportunities')
      .then(data => setOpportunities(data.filter(o => o.status === 'PUBLISHED') || []))
      .catch(() => setError('Failed to load opportunities'));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await api('/ngo/proposals', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          budget_requested: parseInt(formData.budget_requested),
        }),
      });
      router.push('/ngo/proposals');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit proposal');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Submit Proposal</h1>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block font-semibold mb-2">Select Opportunity *</label>
          <select
            value={formData.opportunity_id}
            onChange={e => setFormData({ ...formData, opportunity_id: e.target.value })}
            className="w-full border rounded px-4 py-2"
            required
          >
            <option value="">Choose an opportunity...</option>
            {opportunities.map(opp => (
              <option key={opp.id} value={opp.id}>
                {opp.title}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block font-semibold mb-2">Problem Statement *</label>
          <textarea
            value={formData.problem_statement}
            onChange={e => setFormData({ ...formData, problem_statement: e.target.value })}
            className="w-full border rounded px-4 py-2"
            rows={4}
            minLength={10}
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Solution *</label>
          <textarea
            value={formData.solution}
            onChange={e => setFormData({ ...formData, solution: e.target.value })}
            className="w-full border rounded px-4 py-2"
            rows={4}
            minLength={10}
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Budget Requested (₹) *</label>
          <input
            type="number"
            value={formData.budget_requested}
            onChange={e => setFormData({ ...formData, budget_requested: e.target.value })}
            className="w-full border rounded px-4 py-2"
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Timeline *</label>
          <input
            type="text"
            value={formData.timeline}
            onChange={e => setFormData({ ...formData, timeline: e.target.value })}
            className="w-full border rounded px-4 py-2"
            placeholder="e.g., 12 months"
            minLength={5}
            required
          />
        </div>

        <div>
          <label className="block font-semibold mb-2">Expected Outcomes *</label>
          <textarea
            value={formData.expected_outcomes}
            onChange={e => setFormData({ ...formData, expected_outcomes: e.target.value })}
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
            {loading ? 'Submitting...' : 'Submit Proposal'}
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
