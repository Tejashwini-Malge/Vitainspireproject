'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { api, getToken } from '@/lib/api';
import ProposalMessages from '@/components/ProposalMessages';

interface Proposal {
  id: string;
  proposal_id: string;
  opportunity_id: string;
  ngo_id: string;
  version_num: number;
  status: string;
  problem_statement: string;
  solution: string;
  budget_requested: number;
  timeline: string;
  expected_outcomes: string;
  created_at: string;
  updated_at: string;
}

export default function CSRProposalDetailPage() {
  const router = useRouter();
  const params = useParams()!;
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }

    api<Proposal>(`/csr/proposals/${params.id}`)
      .then((data) => setProposal(data))
      .catch(() => setError('Failed to load proposal'))
      .finally(() => setLoading(false));
  }, [params.id, router]);

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">{error}</div>;
  if (!proposal) return <div className="p-8">Proposal not found</div>;

  const statusColor =
    proposal.status === 'PENDING_CSR'
      ? 'bg-yellow-100 text-yellow-800'
      : proposal.status === 'CHANGES_REQUESTED'
      ? 'bg-orange-100 text-orange-800'
      : 'bg-blue-100 text-blue-800';

  const statusLabel = proposal.status === 'PENDING_CSR' ? 'Awaiting your review' : proposal.status;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">Proposal Review v{proposal.version_num}</h1>
          <p className="text-gray-600">NGO ID: {proposal.ngo_id}</p>
        </div>
        <span className={`px-4 py-2 rounded-full font-semibold ${statusColor}`}>
          {statusLabel}
        </span>
      </div>

      {/* Proposal Details */}
      <div className="bg-white border rounded-lg p-8 mb-8 space-y-6">
        <div>
          <h2 className="text-2xl font-bold mb-2">Problem Statement</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{proposal.problem_statement}</p>
        </div>

        <div>
          <h2 className="text-2xl font-bold mb-2">Solution</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{proposal.solution}</p>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-gray-900">Budget Requested</h3>
            <p className="text-2xl font-bold text-green-600">₹{(proposal.budget_requested / 100000).toFixed(1)}L</p>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Timeline</h3>
            <p className="text-lg">{proposal.timeline}</p>
          </div>
        </div>

        <div>
          <h2 className="text-2xl font-bold mb-2">Expected Outcomes</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{proposal.expected_outcomes}</p>
        </div>

        <div className="text-sm text-gray-500">
          <p>Submitted: {new Date(proposal.created_at).toLocaleString()}</p>
          <p>Last Updated: {new Date(proposal.updated_at).toLocaleString()}</p>
        </div>
      </div>

      {/* Messaging Section */}
      <div className="bg-white border rounded-lg p-8 mb-8">
        <h2 className="text-2xl font-bold mb-6">Communication with NGO</h2>
        <ProposalMessages proposalId={params.id as string} currentUserType="CSR" />
      </div>

      {/* Decision Actions */}
      {proposal.status === 'PENDING_CSR' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 mb-8">
          <h2 className="text-2xl font-bold mb-4">Decision</h2>
          <p className="text-gray-700 mb-6">
            After reviewing this proposal and communicating with the NGO, you can approve or request changes.
          </p>
          <div className="flex gap-4">
            <Link
              href={`/csr/proposals/${params.id}/approve`}
              className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 font-semibold"
            >
              ✓ Approve Proposal
            </Link>
            <Link
              href={`/csr/proposals/${params.id}/request-changes`}
              className="bg-orange-600 text-white px-6 py-3 rounded-lg hover:bg-orange-700 font-semibold"
            >
              ✎ Request Changes
            </Link>
          </div>
        </div>
      )}

      {/* Navigation */}
      <button
        onClick={() => router.back()}
        className="bg-gray-300 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-400"
      >
        Back
      </button>
    </div>
  );
}
