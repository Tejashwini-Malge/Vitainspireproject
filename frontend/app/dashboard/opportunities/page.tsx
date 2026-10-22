'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';

interface Opportunity {
  id: string;
  title: string;
  description: string;
  status: string;
  sectors: string[];
  geographies: string[];
  budget_min: number;
  budget_max: number;
  deadline: string;
  created_at: string;
}

export default function OpportunitiesPage() {
  const router = useRouter();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    api<Opportunity[]>('/csr/opportunities')
      .then(data => setOpportunities(data || []))
      .catch(() => setError('Failed to load opportunities'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <div className="p-4">Loading...</div>;

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">My Opportunities</h1>
        <Link href="/dashboard/opportunities/create" className="bg-blue-600 text-white px-4 py-2 rounded">
          Create Opportunity
        </Link>
      </div>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      {opportunities.length === 0 ? (
        <div className="text-gray-500">No opportunities yet</div>
      ) : (
        <div className="grid gap-4">
          {opportunities.map(opp => (
            <div key={opp.id} className="border rounded-lg p-4 hover:shadow-lg transition">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-xl font-semibold">{opp.title}</h3>
                <span className={`px-3 py-1 rounded text-sm font-medium ${
                  opp.status === 'PUBLISHED' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {opp.status}
                </span>
              </div>
              <p className="text-gray-600 mb-3">{opp.description}</p>

              <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                <div>
                  <span className="font-semibold">Budget:</span> ${(opp.budget_min/100000).toFixed(1)}M - ${(opp.budget_max/100000).toFixed(1)}M
                </div>
                <div>
                  <span className="font-semibold">Deadline:</span> {new Date(opp.deadline).toLocaleDateString()}
                </div>
                <div className="col-span-2">
                  <span className="font-semibold">Sectors:</span> {opp.sectors.join(', ')}
                </div>
                <div className="col-span-2">
                  <span className="font-semibold">Geographies:</span> {opp.geographies.join(', ')}
                </div>
              </div>

              <div className="flex gap-2">
                <Link href={`/dashboard/opportunities/${opp.id}`} className="text-blue-600 hover:underline">
                  View
                </Link>
                {opp.status === 'DRAFT' && (
                  <Link href={`/dashboard/opportunities/${opp.id}/publish`} className="text-green-600 hover:underline">
                    Publish
                  </Link>
                )}
                {opp.status === 'PUBLISHED' && (
                  <Link href={`/dashboard/opportunities/${opp.id}/shortlist`} className="text-purple-600 hover:underline">
                    Create Shortlist
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
