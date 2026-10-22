'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api } from '@/lib/api';
import Link from 'next/link';

interface Opportunity {
  id: string;
  title: string;
  description: string;
  sectors: string[];
  geographies: string[];
  budget_min: number;
  budget_max: number;
  deadline: string;
  requirements_text: string;
  status: string;
  created_at: string;
  published_at: string | null;
}

export default function OpportunityDetailPage() {
  const params = useParams()!;
  const router = useRouter();
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchOpportunity = async () => {
      try {
        const data = await api<Opportunity>(`/csr/opportunities/${params.id}`);
        setOpportunity(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch opportunity');
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      fetchOpportunity();
    }
  }, [params.id]);

  if (loading) {
    return <div className="max-w-2xl mx-auto p-8">Loading...</div>;
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>
        <button onClick={() => router.back()} className="text-blue-600 underline">
          Go Back
        </button>
      </div>
    );
  }

  if (!opportunity) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <p>Opportunity not found</p>
        <button onClick={() => router.back()} className="text-blue-600 underline">
          Go Back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="mb-6">
        <button onClick={() => router.back()} className="text-blue-600 underline mb-4">
          ← Back
        </button>
        <h1 className="text-4xl font-bold mb-2">{opportunity.title}</h1>
        <div className="flex gap-4 mb-4">
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
            opportunity.status === 'PUBLISHED' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
          }`}>
            {opportunity.status}
          </span>
          <span className="text-gray-600">
            Created {new Date(opportunity.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-blue-50 p-4 rounded-lg">
          <h3 className="font-semibold text-gray-700 mb-2">Budget Range</h3>
          <p className="text-2xl font-bold text-blue-600">
            ₹{(opportunity.budget_min / 100000).toFixed(1)}L - ₹{(opportunity.budget_max / 100000).toFixed(1)}L
          </p>
        </div>

        <div className="bg-purple-50 p-4 rounded-lg">
          <h3 className="font-semibold text-gray-700 mb-2">Deadline</h3>
          <p className="text-2xl font-bold text-purple-600">
            {new Date(opportunity.deadline).toLocaleDateString()}
          </p>
        </div>

        <div className="bg-indigo-50 p-4 rounded-lg">
          <h3 className="font-semibold text-gray-700 mb-2">Status</h3>
          <p className="text-2xl font-bold text-indigo-600">
            {opportunity.status === 'PUBLISHED' ? '✓ Live' : 'Draft'}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg border p-6 mb-8">
        <h2 className="text-2xl font-bold mb-4">Description</h2>
        <p className="text-gray-700 whitespace-pre-wrap">{opportunity.description}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-xl font-bold mb-4">Sectors</h2>
          <div className="flex flex-wrap gap-2">
            {opportunity.sectors.map((sector) => (
              <span key={sector} className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
                {sector}
              </span>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-xl font-bold mb-4">Geographies</h2>
          <div className="flex flex-wrap gap-2">
            {opportunity.geographies.map((geo) => (
              <span key={geo} className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">
                {geo}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border p-6 mb-8">
        <h2 className="text-2xl font-bold mb-4">Requirements</h2>
        <p className="text-gray-700 whitespace-pre-wrap">{opportunity.requirements_text}</p>
      </div>

      {opportunity.status === 'DRAFT' && (
        <div className="flex gap-4">
          <Link
            href={`/csr/opportunities/${opportunity.id}/publish`}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700"
          >
            Publish Opportunity
          </Link>
          <Link
            href={`/csr/opportunities/${opportunity.id}/shortlist`}
            className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700"
          >
            Create Shortlist
          </Link>
        </div>
      )}

      {opportunity.status === 'PUBLISHED' && (
        <div className="flex gap-4">
          <Link
            href={`/csr/opportunities/${opportunity.id}/shortlist`}
            className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700"
          >
            Manage Shortlist
          </Link>
          <Link
            href={`/dashboard/opportunities`}
            className="bg-gray-600 text-white px-6 py-2 rounded-lg hover:bg-gray-700"
          >
            Back to Opportunities
          </Link>
        </div>
      )}
    </div>
  );
}
