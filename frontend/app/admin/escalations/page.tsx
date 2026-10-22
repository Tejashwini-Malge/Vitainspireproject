'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import Link from 'next/link';
import { AdminNav } from '@/components/admin/AdminNav';

interface Escalation {
  id: string;
  proposal_id: string;
  reason: string;
  escalated_at: string;
  admin_notes: string | null;
  status: string;
  resolved_at: string | null;
}

export default function AdminEscalationsPage() {
  const router = useRouter();
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'pending'>('pending');
  const [selectedEscalation, setSelectedEscalation] = useState<Escalation | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/admin/login');
      return;
    }

    loadEscalations();
  }, [router, filter]);

  const loadEscalations = async () => {
    try {
      const data = await api<Escalation[]>('/admin/escalations/pending');
      setEscalations(filter === 'pending' ? data : data);
    } catch (err) {
      setError('Failed to load escalations');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerCheck = async () => {
    try {
      const result = await api<{ five_day_escalations: number; ten_day_escalations: number }>(
        '/admin/escalations/check-and-create',
        { method: 'POST' },
      );
      alert(
        `Escalation check completed:\n5-day: ${result.five_day_escalations}\n10-day: ${result.ten_day_escalations}`
      );
      loadEscalations();
    } catch (err) {
      alert('Failed to trigger escalation check');
    }
  };

  const handleResolve = async (escalationId: string) => {
    const notes = prompt('Enter resolution notes (optional):');
    if (notes === null) return; // User cancelled

    try {
      await api(`/admin/escalations/${escalationId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      });
      alert('Escalation resolved');
      loadEscalations();
      setShowDetails(false);
    } catch (err) {
      alert('Failed to resolve escalation');
    }
  };

  const handleSendFollowUp = async (escalationId: string) => {
    const recipientType = prompt('Send to CSR or NGO?');
    if (recipientType === null) return;

    if (!['CSR', 'NGO'].includes(recipientType.toUpperCase())) {
      alert('Please enter CSR or NGO');
      return;
    }

    const message = prompt('Enter follow-up message:');
    if (message === null) return;

    try {
      await api(`/admin/escalations/${escalationId}/send-follow-up`, {
        method: 'POST',
        body: JSON.stringify({
          recipient_type: recipientType.toUpperCase(),
          message,
        }),
      });
      alert('Follow-up message sent');
      loadEscalations();
    } catch (err) {
      alert('Failed to send follow-up message');
    }
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <AdminNav />
        <h1 className="text-4xl font-bold mb-8">Escalation Management</h1>
        <div className="text-center py-12 text-gray-500">Loading...</div>
      </div>
    );
  }

  const pendingCount = escalations.filter((e) => e.status === 'PENDING').length;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <AdminNav />
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold">Escalation Management</h1>
          <p className="text-gray-600 mt-2">
            {pendingCount > 0
              ? `${pendingCount} pending escalation${pendingCount !== 1 ? 's' : ''}`
              : 'No pending escalations'}
          </p>
        </div>
        <button
          onClick={handleTriggerCheck}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-semibold"
        >
          🔄 Check for Escalations
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-8">
          {error}
        </div>
      )}

      {/* Escalations List */}
      {escalations.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
          <p className="text-lg font-semibold text-green-900">✓ All caught up!</p>
          <p className="text-green-700 mt-2">No pending escalations requiring attention.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {escalations.map((escalation) => (
            <div
              key={escalation.id}
              className={`border rounded-lg p-6 ${
                escalation.status === 'PENDING'
                  ? 'bg-yellow-50 border-yellow-200'
                  : 'bg-green-50 border-green-200'
              }`}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  {/* Title */}
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-xl font-bold text-gray-900">
                      Proposal {escalation.proposal_id.substring(0, 8)}...
                    </h2>
                    <span
                      className={`px-3 py-1 rounded-full font-semibold text-sm ${
                        escalation.reason === 'NO_REPLY_5_DAYS'
                          ? 'bg-yellow-200 text-yellow-800'
                          : 'bg-red-200 text-red-800'
                      }`}
                    >
                      {escalation.reason === 'NO_REPLY_5_DAYS' ? '⏰ 5 Days' : '🚨 10 Days'}
                    </span>
                    <span
                      className={`px-3 py-1 rounded-full font-semibold text-sm ${
                        escalation.status === 'PENDING'
                          ? 'bg-orange-200 text-orange-800'
                          : 'bg-green-200 text-green-800'
                      }`}
                    >
                      {escalation.status}
                    </span>
                  </div>

                  {/* Dates */}
                  <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-3">
                    <div>
                      <span className="font-semibold">Escalated:</span>{' '}
                      {new Date(escalation.escalated_at).toLocaleString()}
                    </div>
                    {escalation.resolved_at && (
                      <div>
                        <span className="font-semibold">Resolved:</span>{' '}
                        {new Date(escalation.resolved_at).toLocaleString()}
                      </div>
                    )}
                  </div>

                  {/* Notes */}
                  {escalation.admin_notes && (
                    <div className="bg-white rounded p-3 border border-gray-200 text-sm text-gray-700">
                      <span className="font-semibold">Notes:</span> {escalation.admin_notes}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex-shrink-0 ml-4 flex gap-2">
                  <button
                    onClick={() => {
                      setSelectedEscalation(escalation);
                      setShowDetails(true);
                    }}
                    className="text-blue-600 hover:text-blue-700 font-semibold text-sm"
                  >
                    Details
                  </button>
                  {escalation.status === 'PENDING' && (
                    <>
                      <button
                        onClick={() => handleSendFollowUp(escalation.id)}
                        className="text-green-600 hover:text-green-700 font-semibold text-sm"
                      >
                        Follow-up
                      </button>
                      <button
                        onClick={() => handleResolve(escalation.id)}
                        className="text-orange-600 hover:text-orange-700 font-semibold text-sm"
                      >
                        Resolve
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Details Modal */}
      {showDetails && selectedEscalation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-96 overflow-y-auto p-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Escalation Details</h2>
              <button
                onClick={() => setShowDetails(false)}
                className="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ×
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <span className="font-semibold text-gray-900">Proposal ID:</span>
                <p className="text-gray-600">{selectedEscalation.proposal_id}</p>
              </div>

              <div>
                <span className="font-semibold text-gray-900">Reason:</span>
                <p className="text-gray-600">
                  {selectedEscalation.reason === 'NO_REPLY_5_DAYS'
                    ? 'No reply for 5+ days'
                    : 'No reply for 10+ days'}
                </p>
              </div>

              <div>
                <span className="font-semibold text-gray-900">Status:</span>
                <p className="text-gray-600">{selectedEscalation.status}</p>
              </div>

              <div>
                <span className="font-semibold text-gray-900">Escalated At:</span>
                <p className="text-gray-600">
                  {new Date(selectedEscalation.escalated_at).toLocaleString()}
                </p>
              </div>

              {selectedEscalation.admin_notes && (
                <div>
                  <span className="font-semibold text-gray-900">Notes:</span>
                  <p className="text-gray-600 whitespace-pre-wrap">
                    {selectedEscalation.admin_notes}
                  </p>
                </div>
              )}

              <div className="flex gap-4 mt-6">
                <Link
                  href={`/csr/proposals/${selectedEscalation.proposal_id}`}
                  className="flex-1 bg-blue-600 text-white text-center py-2 rounded-lg hover:bg-blue-700 font-semibold"
                >
                  View Proposal
                </Link>
                {selectedEscalation.status === 'PENDING' && (
                  <>
                    <button
                      onClick={() => {
                        handleSendFollowUp(selectedEscalation.id);
                        setShowDetails(false);
                      }}
                      className="flex-1 bg-green-600 text-white py-2 rounded-lg hover:bg-green-700 font-semibold"
                    >
                      Send Follow-up
                    </button>
                    <button
                      onClick={() => {
                        handleResolve(selectedEscalation.id);
                        setShowDetails(false);
                      }}
                      className="flex-1 bg-orange-600 text-white py-2 rounded-lg hover:bg-orange-700 font-semibold"
                    >
                      Resolve
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
