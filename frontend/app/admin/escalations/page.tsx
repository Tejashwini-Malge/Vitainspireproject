'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Clock, RefreshCw, CheckCircle2, X } from 'lucide-react';
import { api, getToken } from '@/lib/api';
import { AdminNav } from '@/components/admin/AdminNav';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { cn } from '@/components/ui/cn';

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
      <div className="mx-auto max-w-6xl p-8">
        <AdminNav />
        <PageHeader eyebrow="Admin" title="Escalation management" />
        <div className="py-12 text-center text-muted">Loading...</div>
      </div>
    );
  }

  const pendingCount = escalations.filter((e) => e.status === 'PENDING').length;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <AdminNav />

      <PageHeader
        eyebrow="Admin"
        title="Escalation management"
        description={
          pendingCount > 0
            ? `${pendingCount} pending escalation${pendingCount !== 1 ? 's' : ''}`
            : 'No pending escalations'
        }
        action={
          <Button variant="primary" onClick={handleTriggerCheck}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            Check for escalations
          </Button>
        }
      />

      {error && (
        <div className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {escalations.length === 0 ? (
        <EmptyState
          title="All caught up"
          description="No pending escalations requiring attention."
        />
      ) : (
        <div className="space-y-4">
          {escalations.map((escalation, i) => {
            const statusTone: BadgeTone = escalation.status === 'PENDING' ? 'pending' : 'approved';
            const reasonTone: BadgeTone = escalation.reason === 'NO_REPLY_5_DAYS' ? 'pending' : 'rejected';
            return (
              <motion.div
                key={escalation.id}
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-40px' }}
                transition={{ duration: 0.3, delay: Math.min(i, 8) * 0.04 }}
              >
                <Card
                  className={cn(
                    'p-6',
                    escalation.status === 'PENDING' && 'border-status-pending/40',
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-3">
                        <h2 className="font-display text-xl font-semibold text-navy">
                          Proposal {escalation.proposal_id.substring(0, 8)}...
                        </h2>
                        <Badge tone={reasonTone}>
                          <Clock className="h-3 w-3" aria-hidden />
                          {escalation.reason === 'NO_REPLY_5_DAYS' ? '5 days' : '10 days'}
                        </Badge>
                        <Badge tone={statusTone}>{escalation.status}</Badge>
                      </div>

                      <div className="mb-3 grid grid-cols-2 gap-4 text-sm text-muted">
                        <div>
                          <span className="font-medium text-ink">Escalated:</span>{' '}
                          {new Date(escalation.escalated_at).toLocaleString()}
                        </div>
                        {escalation.resolved_at && (
                          <div>
                            <span className="font-medium text-ink">Resolved:</span>{' '}
                            {new Date(escalation.resolved_at).toLocaleString()}
                          </div>
                        )}
                      </div>

                      {escalation.admin_notes && (
                        <div className="rounded-sm border border-line bg-paper p-3 text-sm text-ink">
                          <span className="font-medium">Notes:</span> {escalation.admin_notes}
                        </div>
                      )}
                    </div>

                    <div className="ml-4 flex shrink-0 gap-3">
                      <button
                        onClick={() => {
                          setSelectedEscalation(escalation);
                          setShowDetails(true);
                        }}
                        className="text-sm font-medium text-navy hover:underline"
                      >
                        Details
                      </button>
                      {escalation.status === 'PENDING' && (
                        <>
                          <button
                            onClick={() => handleSendFollowUp(escalation.id)}
                            className="text-sm font-medium text-status-approved hover:underline"
                          >
                            Follow-up
                          </button>
                          <button
                            onClick={() => handleResolve(escalation.id)}
                            className="text-sm font-medium text-teal hover:underline"
                          >
                            Resolve
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Details Modal */}
      {showDetails && selectedEscalation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/50 p-4">
          <div className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-sm border border-line bg-[#FFFDF7] p-8 shadow-lg">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="font-display text-2xl font-semibold text-navy">Escalation details</h2>
              <button
                onClick={() => setShowDetails(false)}
                className="text-muted hover:text-navy"
                aria-label="Close"
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <span className="font-medium text-navy">Proposal ID:</span>
                <p className="text-muted">{selectedEscalation.proposal_id}</p>
              </div>

              <div>
                <span className="font-medium text-navy">Reason:</span>
                <p className="text-muted">
                  {selectedEscalation.reason === 'NO_REPLY_5_DAYS'
                    ? 'No reply for 5+ days'
                    : 'No reply for 10+ days'}
                </p>
              </div>

              <div>
                <span className="font-medium text-navy">Status:</span>
                <p className="text-muted">{selectedEscalation.status}</p>
              </div>

              <div>
                <span className="font-medium text-navy">Escalated At:</span>
                <p className="text-muted">
                  {new Date(selectedEscalation.escalated_at).toLocaleString()}
                </p>
              </div>

              {selectedEscalation.admin_notes && (
                <div>
                  <span className="font-medium text-navy">Notes:</span>
                  <p className="whitespace-pre-wrap text-muted">
                    {selectedEscalation.admin_notes}
                  </p>
                </div>
              )}

              <div className="mt-6 flex gap-4">
                <Link href={`/csr/proposals/${selectedEscalation.proposal_id}`} className="flex-1">
                  <Button variant="secondary" className="w-full">
                    View proposal
                  </Button>
                </Link>
                {selectedEscalation.status === 'PENDING' && (
                  <>
                    <Button
                      variant="primary"
                      className="flex-1"
                      onClick={() => {
                        handleSendFollowUp(selectedEscalation.id);
                        setShowDetails(false);
                      }}
                    >
                      Send follow-up
                    </Button>
                    <Button
                      variant="secondary"
                      className="flex-1"
                      onClick={() => {
                        handleResolve(selectedEscalation.id);
                        setShowDetails(false);
                      }}
                    >
                      <CheckCircle2 className="h-4 w-4" aria-hidden />
                      Resolve
                    </Button>
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
