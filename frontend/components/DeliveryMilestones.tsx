'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';

export interface DeliveryMilestone {
  id: string;
  sequence_num: number;
  title: string;
  description: string;
  target_date: string;
  amount_minor: number;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'VERIFIED';
  evidence_url: string | null;
  completed_at: string | null;
  verified_at: string | null;
}

interface DeliveryProgress {
  proposal_id: string;
  committed_amount_minor: number;
  milestone_count: number;
  completed_count: number;
  verified_count: number;
  percent_verified: number;
  next_due: DeliveryMilestone | null;
  overdue_count: number;
  milestones: DeliveryMilestone[];
}

const STATUS_TONE: Record<DeliveryMilestone['status'], BadgeTone> = {
  PENDING: 'neutral',
  IN_PROGRESS: 'pending',
  COMPLETED: 'pending',
  VERIFIED: 'approved',
};

const STATUS_LABEL: Record<DeliveryMilestone['status'], string> = {
  PENDING: 'Not started',
  IN_PROGRESS: 'In progress',
  COMPLETED: 'Awaiting verification',
  VERIFIED: 'Verified',
};

/** Minor units to rupees, grouped Indian-style. */
function formatAmount(minor: number): string {
  return new Intl.NumberFormat('en-IN').format(Math.round(minor / 100));
}

interface DraftRow {
  title: string;
  description: string;
  target_date: string;
  amount: string;
}

const EMPTY_ROW: DraftRow = { title: '', description: '', target_date: '', amount: '' };

/**
 * Delivery plan for an approved proposal.
 *
 * The same data, two roles: the NGO owns the plan and reports progress, the funder reads
 * it and verifies completed work. The server enforces both halves -- this only decides
 * which controls to render.
 */
export default function DeliveryMilestones({
  proposalId,
  role,
}: {
  proposalId: string;
  role: 'NGO' | 'CSR';
}) {
  const [progress, setProgress] = useState<DeliveryProgress | null>(null);
  const [unavailable, setUnavailable] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<DraftRow[]>([{ ...EMPTY_ROW }]);

  const load = useCallback(async () => {
    try {
      setProgress(await api<DeliveryProgress>(`/proposals/${proposalId}/milestones`));
      setUnavailable('');
    } catch (err) {
      // A 409 here is the normal "not approved yet" case, not a failure worth shouting about.
      setUnavailable(err instanceof Error ? err.message : 'Delivery tracking is not available yet');
    }
  }, [proposalId]);

  useEffect(() => {
    void load();
  }, [load]);

  const savePlan = async () => {
    setBusy(true);
    setError('');
    try {
      await api(`/ngo/proposals/${proposalId}/milestones`, {
        method: 'POST',
        body: JSON.stringify({
          milestones: rows.map(r => ({
            title: r.title.trim(),
            description: r.description.trim(),
            target_date: r.target_date,
            amount_minor: Math.round(Number(r.amount || '0') * 100),
          })),
        }),
      });
      setEditing(false);
      setRows([{ ...EMPTY_ROW }]);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save the plan');
    } finally {
      setBusy(false);
    }
  };

  const update = async (id: string, body: Record<string, string>) => {
    setBusy(true);
    setError('');
    try {
      await api(`/ngo/milestones/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update the milestone');
    } finally {
      setBusy(false);
    }
  };

  const verify = async (id: string) => {
    setBusy(true);
    setError('');
    try {
      await api(`/csr/milestones/${id}/verify`, { method: 'POST' });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to verify the milestone');
    } finally {
      setBusy(false);
    }
  };

  if (unavailable) {
    return (
      <section className="space-y-4">
        <h2 className="font-display text-lg font-semibold text-navy">Delivery</h2>
        <EmptyState title="Not started yet" description={unavailable} />
      </section>
    );
  }

  if (!progress) return <p className="text-muted">Loading delivery plan…</p>;

  const canPlan = role === 'NGO' && progress.milestones.every(m => m.status === 'PENDING');

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold text-navy">Delivery</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="neutral">₹{formatAmount(progress.committed_amount_minor)} committed</Badge>
          {progress.milestone_count > 0 && (
            <Badge tone={progress.percent_verified === 100 ? 'approved' : 'pending'}>
              {progress.verified_count}/{progress.milestone_count} verified
            </Badge>
          )}
          {progress.overdue_count > 0 && (
            <Badge tone="rejected">{progress.overdue_count} overdue</Badge>
          )}
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      {progress.milestone_count === 0 && !editing && (
        <EmptyState
          title="No delivery plan yet"
          description={
            role === 'NGO'
              ? 'Break the approved work into milestones so your funder can follow progress.'
              : 'The NGO has not published its delivery milestones yet.'
          }
          action={
            canPlan ? (
              <Button variant="primary" onClick={() => setEditing(true)}>
                Add milestones
              </Button>
            ) : undefined
          }
        />
      )}

      {editing && (
        <Card className="space-y-4 p-4">
          {rows.map((row, i) => (
            <div key={i} className="grid gap-3 border-b border-line pb-4 last:border-0 last:pb-0 sm:grid-cols-2">
              <input
                className="rounded-sm border border-line px-3 py-2 text-sm sm:col-span-2"
                placeholder="Milestone title"
                value={row.title}
                onChange={e => setRows(rows.map((r, j) => (i === j ? { ...r, title: e.target.value } : r)))}
              />
              <input
                className="rounded-sm border border-line px-3 py-2 text-sm sm:col-span-2"
                placeholder="What will be delivered"
                value={row.description}
                onChange={e => setRows(rows.map((r, j) => (i === j ? { ...r, description: e.target.value } : r)))}
              />
              <label className="text-sm text-muted">
                Target date
                <input
                  type="date"
                  className="mt-1 w-full rounded-sm border border-line px-3 py-2 text-sm text-navy"
                  value={row.target_date}
                  onChange={e => setRows(rows.map((r, j) => (i === j ? { ...r, target_date: e.target.value } : r)))}
                />
              </label>
              <label className="text-sm text-muted">
                Amount (₹)
                <input
                  type="number"
                  min="0"
                  className="mt-1 w-full rounded-sm border border-line px-3 py-2 text-sm text-navy"
                  value={row.amount}
                  onChange={e => setRows(rows.map((r, j) => (i === j ? { ...r, amount: e.target.value } : r)))}
                />
              </label>
            </div>
          ))}
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => setRows([...rows, { ...EMPTY_ROW }])}>
              Add another
            </Button>
            <Button variant="primary" onClick={savePlan} disabled={busy}>
              {busy ? 'Saving…' : 'Save plan'}
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
          <p className="text-xs text-muted">
            Milestone amounts must total no more than the ₹{formatAmount(progress.committed_amount_minor)} committed.
          </p>
        </Card>
      )}

      {progress.milestones.length > 0 && (
        <Card className="divide-y divide-line p-0">
          {progress.milestones.map(m => (
            <div key={m.id} className="space-y-2 px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-navy">
                  {m.sequence_num}. {m.title}
                </span>
                <Badge tone={STATUS_TONE[m.status]}>{STATUS_LABEL[m.status]}</Badge>
              </div>
              {m.description && <p className="text-sm text-muted">{m.description}</p>}
              <p className="font-mono text-[0.7rem] uppercase tracking-wide text-muted">
                Due {new Date(m.target_date).toLocaleDateString()} · ₹{formatAmount(m.amount_minor)}
              </p>
              {m.evidence_url && (
                <a href={m.evidence_url} target="_blank" rel="noreferrer" className="block text-sm text-teal underline">
                  Evidence
                </a>
              )}

              {role === 'NGO' && m.status !== 'VERIFIED' && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {m.status === 'PENDING' && (
                    <Button variant="secondary" onClick={() => update(m.id, { status: 'IN_PROGRESS' })} disabled={busy}>
                      Start work
                    </Button>
                  )}
                  {m.status !== 'COMPLETED' && (
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() => {
                        const evidence = window.prompt('Link to evidence (optional)') ?? '';
                        void update(m.id, evidence ? { status: 'COMPLETED', evidence_url: evidence } : { status: 'COMPLETED' });
                      }}
                    >
                      Mark complete
                    </Button>
                  )}
                </div>
              )}

              {role === 'CSR' && m.status === 'COMPLETED' && (
                <div className="pt-1">
                  <Button variant="primary" onClick={() => verify(m.id)} disabled={busy}>
                    Verify completion
                  </Button>
                </div>
              )}
            </div>
          ))}
        </Card>
      )}
    </section>
  );
}
