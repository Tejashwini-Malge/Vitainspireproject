'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';
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

  if (loading) return <div className="p-8 text-gray-500">Loading your conversations…</div>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h1 className="text-3xl font-bold">Conversations</h1>
          <p className="text-gray-600 mt-1">
            {totalUnread > 0
              ? `${totalUnread} unread message${totalUnread === 1 ? '' : 's'} waiting for you.`
              : 'Everything here is up to date.'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Link
            href="/conversations/new"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
          >
            Message platform staff
          </Link>
          <NotificationBell />
        </div>
      </div>

      <label className="inline-flex items-center gap-2 text-sm text-gray-700 my-4">
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(e) => setUnreadOnly(e.target.checked)}
        />
        Only show conversations needing a reply
      </label>

      {error && <div className="bg-red-100 text-red-700 p-4 rounded mb-4">{error}</div>}

      {threads.length === 0 ? (
        <div className="text-center py-16 text-gray-500 border border-dashed border-gray-300 rounded-lg">
          <p className="text-lg mb-1">
            {unreadOnly ? 'Nothing is waiting on you' : 'No conversations yet'}
          </p>
          <p className="text-sm">
            {unreadOnly
              ? 'Untick the filter above to see every conversation.'
              : 'Proposal threads appear here automatically. You can also message platform staff at any time.'}
          </p>
        </div>
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
              <li
                key={t.thread_id}
                className={`rounded-lg border p-4 ${
                  t.unread_count > 0 ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'
                }`}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900">{t.counterparty_name}</span>
                      <span className="text-xs rounded bg-gray-200 px-2 py-0.5 text-gray-700">
                        {sideLabel}
                      </span>
                      {t.unread_count > 0 && (
                        <span className="text-xs rounded-full bg-blue-600 px-2 py-0.5 text-white">
                          {t.unread_count} new
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-0.5 truncate">{t.title}</p>
                    <p className="mt-2 text-gray-800 break-words">
                      {t.last_message_preview ?? (
                        <span className="text-gray-400 italic">
                          No messages yet — start the conversation.
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-gray-500">{relativeTime(t.last_message_at)}</p>
                    <p className="text-xs text-gray-500 mt-1">{t.status}</p>
                  </div>
                </div>

                <div className="mt-3 flex gap-4 items-center">
                  <Link href={href} className="text-blue-600 text-sm hover:underline">
                    Open conversation
                  </Link>
                  {t.unread_count > 0 && (
                    <button
                      type="button"
                      onClick={() => markRead(t)}
                      className="text-gray-600 text-sm hover:underline"
                    >
                      Mark as read
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
