'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import type { Conversation, ConversationMessage, Me } from '@/lib/types';

const SIDE_LABEL: Record<string, string> = {
  ADMIN: 'Platform staff',
  ORG: 'Your organisation',
  DONOR: 'Donor',
};

export default function ConversationPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>()!;
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [myUserId, setMyUserId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const [me, all, msgs] = await Promise.all([
        api<Me>('/auth/me'),
        api<Conversation[]>('/conversations'),
        api<ConversationMessage[]>(`/conversations/${id}/messages`),
      ]);
      const found = all.find((c) => c.id === id) ?? null;
      setMyUserId(me.id);
      setConversation(found);
      setMessages(msgs || []);
      setError(found ? '' : 'This conversation was not found, or you are not part of it.');
      // Opening a thread is reading it.
      if (found) await api(`/conversations/${id}/read`, { method: 'POST' });
    } catch {
      setError('This conversation was not found, or you are not part of it.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    load();
  }, [load, router]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const content = draft.trim();
    if (!content) return;
    setSending(true);
    try {
      const msg = await api<ConversationMessage>(`/conversations/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      });
      setMessages((m) => [...m, msg]);
      setDraft('');
      setError('');
    } catch {
      setError('Your message could not be sent. Nothing was lost — try again.');
    } finally {
      setSending(false);
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Loading conversation…</div>;

  if (!conversation) {
    return (
      <div className="max-w-3xl mx-auto p-8">
        <p className="text-gray-700">{error}</p>
        <Link href="/inbox" className="text-blue-600 hover:underline">Back to conversations</Link>
      </div>
    );
  }

  const closed = conversation.status === 'CLOSED';

  return (
    <div className="max-w-3xl mx-auto p-8">
      <Link href="/inbox" className="text-blue-600 text-sm hover:underline">← All conversations</Link>

      <header className="mt-3 mb-6">
        <h1 className="text-2xl font-bold">{conversation.subject}</h1>
        <p className="text-sm text-gray-600 mt-1">
          {conversation.kind === 'DONOR_ADMIN'
            ? 'With platform staff'
            : conversation.kind === 'ADMIN_ORG'
            ? 'Between your organisation and platform staff'
            : 'Direct conversation — not tied to any proposal'}
          {closed && ' · Closed'}
        </p>
      </header>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

      <ul className="space-y-3 mb-6">
        {messages.map((m) => {
          const mine = m.sender_user_id === myUserId;
          return (
            <li key={m.id} className={mine ? 'text-right' : 'text-left'}>
              <div
                className={`inline-block max-w-[85%] rounded-lg px-4 py-2 text-left ${
                  mine ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'
                }`}
              >
                <p className={`text-xs mb-1 ${mine ? 'text-blue-100' : 'text-gray-500'}`}>
                  {mine
                    ? 'You'
                    : conversation.kind === 'ORG_ORG'
                    ? 'Other organisation'
                    : SIDE_LABEL[m.sender_side] ?? m.sender_side}
                  {' · '}
                  {new Date(m.created_at).toLocaleString()}
                </p>
                <p className="whitespace-pre-wrap break-words">{m.content}</p>
              </div>
            </li>
          );
        })}
        <div ref={endRef} />
      </ul>

      {closed ? (
        <p className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
          This conversation is closed. Start a new one if you need anything else.
        </p>
      ) : (
        <form onSubmit={send} className="space-y-3">
          <textarea
            rows={4}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write your reply…"
            className="w-full rounded-md border border-gray-300 px-3 py-2"
            maxLength={5000}
          />
          <button
            type="submit"
            disabled={sending || !draft.trim()}
            className="rounded-md bg-blue-600 px-5 py-2 text-white disabled:opacity-50"
          >
            {sending ? 'Sending…' : 'Send'}
          </button>
        </form>
      )}
    </div>
  );
}
