'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

interface Proposal {
  id: string;
  proposal_id: string;
  opportunity_id: string;
  ngo_id: string;
  version_num: number;
  status: string;
  problem_statement: string;
  budget_requested: number;
  created_at: string;
}

export default function CSRProposalsPage() {
  const router = useRouter();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }

    api<Proposal[]>('/csr/proposals')
      .then(data => setProposals(data || []))
      .catch(() => setError('Failed to load proposals'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <div className="p-8">Loading...</div>;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl font-bold">Proposals for Review</h1>
        <NotificationBell />
      </div>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      {proposals.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-xl">No proposals pending review</p>
        </div>
      ) : (
        <div className="space-y-4">
          {proposals.map(proposal => (
            <div key={proposal.id} className="border rounded-lg p-6 hover:shadow-lg transition bg-white">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-2xl font-bold mb-2">
                    Proposal v{proposal.version_num}
                  </h2>
                  <p className="text-gray-600">{proposal.problem_statement.substring(0, 100)}...</p>
                </div>
                <span
                  className={`px-4 py-2 rounded-full font-semibold whitespace-nowrap ${
                    proposal.status === 'PENDING_CSR'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-orange-100 text-orange-800'
                  }`}
                >
                  {proposal.status === 'PENDING_CSR' ? 'Awaiting your review' : proposal.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
                <div>
                  <span className="font-semibold">Budget Requested:</span> ₹{(proposal.budget_requested / 100000).toFixed(1)}L
                </div>
                <div>
                  <span className="font-semibold">Submitted:</span> {new Date(proposal.created_at).toLocaleDateString()}
                </div>
              </div>

              <div className="flex gap-3">
                <Link
                  href={`/csr/proposals/${proposal.id}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  Review Details
                </Link>
                <Link
                  href={`/csr/proposals/${proposal.id}/approve`}
                  className="text-green-600 hover:underline font-medium"
                >
                  Approve
                </Link>
                <Link
                  href={`/csr/proposals/${proposal.id}/request-changes`}
                  className="text-orange-600 hover:underline font-medium"
                >
                  Request Changes
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
