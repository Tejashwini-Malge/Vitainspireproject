'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { api, getToken } from '@/lib/api';
import type { Conversation } from '@/lib/types';

// useSearchParams forces client rendering, so this route needs a Suspense boundary
// or its static export fails at build time.
export default function NewConversationPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading…</div>}>
      <NewConversationForm />
    </Suspense>
  );
}

function NewConversationForm() {
  const router = useRouter();
  const params = useSearchParams();
  // Platform staff reach an organisation by passing ?org_id=. Everyone else is
  // writing to the platform, so the counterparty is themselves and this stays null.
  const orgId = params?.get('org_id') ?? null;
  // ?target_org_id= opens a direct thread with a specific organisation instead of
  // staff: an NGO/CSR reaching the other kind of organisation, or a donor reaching an NGO.
  const targetOrgId = params?.get('target_org_id') ?? null;

  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) router.replace('/login');
  }, [router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSending(true);
    setError('');
    try {
      const created = await api<Conversation>('/conversations', {
        method: 'POST',
        body: JSON.stringify({
          subject: subject.trim(),
          message: message.trim(),
          ...(orgId ? { org_id: orgId } : {}),
          ...(targetOrgId ? { target_org_id: targetOrgId } : {}),
        }),
      });
      router.replace(`/conversations/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Your message could not be sent.');
      setSending(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <Link href="/inbox" className="text-blue-600 text-sm hover:underline">← All conversations</Link>

      <h1 className="text-2xl font-bold mt-3">
        {orgId ? 'Message this organisation' : targetOrgId ? 'Send a message' : 'Message platform staff'}
      </h1>
      <p className="text-gray-600 mt-1 mb-6">
        {orgId
          ? 'This opens a direct thread with the organisation.'
          : targetOrgId
          ? 'This opens a direct conversation. It is not tied to any proposal — use it for any question or inquiry.'
          : 'Ask about verification, a document, a receipt, or anything else. Someone will reply here.'}
      </p>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium">What is this about?</span>
          <input
            required
            minLength={3}
            maxLength={300}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="For example: my 80G certificate was rejected"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Your message</span>
          <textarea
            required
            rows={6}
            maxLength={5000}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          />
        </label>

        <button
          type="submit"
          disabled={sending || !subject.trim() || !message.trim()}
          className="rounded-md bg-blue-600 px-5 py-2 text-white disabled:opacity-50"
        >
          {sending ? 'Sending…' : 'Send message'}
        </button>
      </form>
    </div>
  );
}
