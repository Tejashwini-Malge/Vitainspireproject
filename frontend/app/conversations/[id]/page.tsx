'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { api, getToken } from '@/lib/api';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
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

  if (loading) return <p className="mx-auto max-w-3xl p-8 text-muted">Loading conversation…</p>;

  if (!conversation) {
    return (
      <div className="mx-auto max-w-3xl space-y-3 p-8">
        <p className="text-ink">{error}</p>
        <Link href="/inbox" className="font-medium text-teal hover:underline">Back to conversations</Link>
      </div>
    );
  }

  const closed = conversation.status === 'CLOSED';

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-8">
      <Link href="/inbox" className="text-sm font-medium text-teal hover:underline">← All conversations</Link>

      <header className="space-y-1.5">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted">
          {conversation.kind === 'DONOR_ADMIN'
            ? 'With platform staff'
            : conversation.kind === 'ADMIN_ORG'
            ? 'Between your organisation and platform staff'
            : 'Direct conversation'}
          {closed && ' · Closed'}
        </p>
        <h1 className="text-2xl font-semibold text-navy">{conversation.subject}</h1>
      </header>

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-3 text-status-rejected">
          {error}
        </p>
      )}

      <ul className="space-y-3">
        <AnimatePresence initial={false}>
          {messages.map((m) => {
            const mine = m.sender_user_id === myUserId;
            return (
              <motion.li
                key={m.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className={mine ? 'text-right' : 'text-left'}
              >
                <div
                  className={`inline-block max-w-[85%] rounded-sm px-4 py-2 text-left ${
                    mine
                      ? 'border border-navy bg-navy text-paper'
                      : 'border border-line bg-[#FFFDF7] text-ink'
                  }`}
                >
                  <p className={`mb-1 font-mono text-xs ${mine ? 'text-paper/70' : 'text-muted'}`}>
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
              </motion.li>
            );
          })}
        </AnimatePresence>
        <div ref={endRef} />
      </ul>

      {closed ? (
        <p className="rounded-sm border border-line bg-[#FFFDF7] p-4 text-sm text-muted">
          This conversation is closed. Start a new one if you need anything else.
        </p>
      ) : (
        <form onSubmit={send} className="space-y-3">
          <Textarea
            rows={4}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write your reply…"
            maxLength={5000}
          />
          <Button type="submit" variant="primary" size="md" disabled={sending || !draft.trim()}>
            {sending ? 'Sending…' : 'Send'}
          </Button>
        </form>
      )}
    </div>
  );
}
