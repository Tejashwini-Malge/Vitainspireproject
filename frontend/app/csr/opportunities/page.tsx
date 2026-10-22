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
}

export default function CSROpportunitiesPage() {
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

  if (loading) return <div className="p-8">Loading...</div>;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl font-bold">My Opportunities</h1>
        <Link
          href="/csr/opportunities/create"
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
        >
          Create Opportunity
        </Link>
      </div>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      {opportunities.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-xl mb-4">No opportunities yet</p>
          <Link href="/csr/opportunities/create" className="text-blue-600 underline">
            Create your first opportunity
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {opportunities.map(opp => (
            <div key={opp.id} className="border rounded-lg p-6 hover:shadow-lg transition bg-white">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-2xl font-bold mb-2">{opp.title}</h2>
                  <p className="text-gray-600">{opp.description}</p>
                </div>
                <span
                  className={`px-4 py-2 rounded-full font-semibold whitespace-nowrap ${
                    opp.status === 'PUBLISHED'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}
                >
                  {opp.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
                <div>
                  <span className="font-semibold">Budget:</span> ₹{(opp.budget_min / 100000).toFixed(1)}L - ₹{(opp.budget_max / 100000).toFixed(1)}L
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

              <div className="flex gap-3">
                <Link
                  href={`/csr/opportunities/${opp.id}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  View Details
                </Link>
                {opp.status === 'DRAFT' && (
                  <Link
                    href={`/csr/opportunities/${opp.id}/publish`}
                    className="text-green-600 hover:underline font-medium"
                  >
                    Publish
                  </Link>
                )}
                {opp.status === 'PUBLISHED' && (
                  <Link
                    href={`/csr/opportunities/${opp.id}/shortlist`}
                    className="text-purple-600 hover:underline font-medium"
                  >
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
