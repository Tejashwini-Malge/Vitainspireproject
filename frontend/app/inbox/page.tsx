'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import type { InboxThread } from '@/lib/types';

function relativeTime(iso: string | null): string {
  if (!iso) return 'No messages yet';
  const then = new Date(iso).getTime();
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
  return new Date(iso).toLocaleDateString();
}

export default function InboxPage() {
  const router = useRouter();
  const [threads, setThreads] = useState<InboxThread[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (filterUnread: boolean) => {
    try {
      const data = await api<InboxThread[]>(`/inbox${filterUnread ? '?unread_only=true' : ''}`);
      setThreads(data || []);
      setError('');
    } catch {
      setError('Could not load your conversations.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    load(unreadOnly);
  }, [load, router, unreadOnly]);

  async function markRead(thread: InboxThread) {
    // Proposal threads and direct conversations are different stores, so each has
    // its own mark-as-read endpoint.
    const path = thread.kind === 'PROPOSAL'
      ? `/inbox/threads/${thread.thread_id}/read`
      : `/conversations/${thread.thread_id}/read`;
    try {
      await api(path, { method: 'POST' });
      await load(unreadOnly);
    } catch {
      setError('Could not mark that conversation as read.');
    }
  }

  const totalUnread = threads.reduce((sum, t) => sum + t.unread_count, 0);

  if (loading) return <p className="mx-auto max-w-4xl p-8 text-muted">Loading your conversations…</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <PageHeader
        eyebrow="Inbox"
        title="Conversations"
        description={
          totalUnread > 0
            ? `${totalUnread} unread message${totalUnread === 1 ? '' : 's'} waiting for you.`
            : 'Everything here is up to date.'
        }
        action={
          <div className="flex items-center gap-4">
            <Link href="/conversations/new">
              <Button variant="primary" size="md">Message platform staff</Button>
            </Link>
            <NotificationBell />
          </div>
        }
      />

      <label className="inline-flex items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(e) => setUnreadOnly(e.target.checked)}
          className="h-4 w-4 rounded-sm border-line text-teal focus:ring-[var(--focus)]"
        />
        Only show conversations needing a reply
      </label>

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-4 text-status-rejected">
          {error}
        </p>
      )}

      {threads.length === 0 ? (
        <EmptyState
          title={unreadOnly ? 'Nothing is waiting on you' : 'No conversations yet'}
          description={
            unreadOnly
              ? 'Untick the filter above to see every conversation.'
              : 'Proposal threads appear here automatically. You can also message platform staff at any time.'
          }
        />
      ) : (
        <ul className="space-y-3">
          {threads.map((t) => {
            const href = t.kind !== 'PROPOSAL'
              ? `/conversations/${t.thread_id}`
              : t.my_side === 'NGO'
                ? `/ngo/proposals/${t.proposal_id}`
                : `/csr/proposals/${t.proposal_id}`;
            const sideLabel =
              t.kind === 'PROPOSAL'
                ? (t.my_side === 'NGO' ? 'Funder' : 'NGO')
                : t.kind === 'ORG_ORG'
                  ? 'Organisation'
                  : t.kind === 'DONOR_NGO'
                    ? (t.my_side === 'DONOR' ? 'Organisation' : 'Donor')
                    : t.my_side === 'ADMIN'
                      ? (t.kind === 'DONOR_ADMIN' ? 'Donor' : 'Organisation')
                      : 'Platform';
            return (
              <li key={t.thread_id}>
                <Card
                  interactive
                  className={`p-4 ${t.unread_count > 0 ? 'border-teal/50 bg-teal/5' : ''}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-navy">{t.counterparty_name}</span>
                        <Badge tone="neutral">{sideLabel}</Badge>
                        {t.unread_count > 0 && (
                          <Badge tone="pending">{t.unread_count} new</Badge>
                        )}
                      </div>
                      <p className="mt-0.5 truncate text-sm text-muted">{t.title}</p>
                      <p className="mt-2 break-words text-ink">
                        {t.last_message_preview ?? (
                          <span className="italic text-muted">
                            No messages yet — start the conversation.
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="font-mono text-xs text-muted">{relativeTime(t.last_message_at)}</p>
                      <p className="mt-1 font-mono text-xs uppercase tracking-wide text-muted">{t.status}</p>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-4">
                    <Link href={href} className="text-sm font-medium text-teal hover:underline">
                      Open conversation
                    </Link>
                    {t.unread_count > 0 && (
                      <button
                        type="button"
                        onClick={() => markRead(t)}
                        className="text-sm font-medium text-muted hover:text-navy hover:underline"
                      >
                        Mark as read
                      </button>
                    )}
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
