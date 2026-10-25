'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { api, getToken } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import type { Conversation } from '@/lib/types';

// useSearchParams forces client rendering, so this route needs a Suspense boundary
// or its static export fails at build time.
export default function NewConversationPage() {
  return (
    <Suspense fallback={<p className="p-8 text-muted">Loading…</p>}>
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
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <Link href="/inbox" className="text-sm font-medium text-teal hover:underline">← All conversations</Link>

      <div className="space-y-1.5">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted">New message</p>
        <h1 className="text-2xl font-semibold text-navy">
          {orgId ? 'Message this organisation' : targetOrgId ? 'Send a message' : 'Message platform staff'}
        </h1>
        <p className="text-muted">
          {orgId
            ? 'This opens a direct thread with the organisation.'
            : targetOrgId
            ? 'This opens a direct conversation. It is not tied to any proposal — use it for any question or inquiry.'
            : 'Ask about verification, a document, a receipt, or anything else. Someone will reply here.'}
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-3 text-status-rejected">
          {error}
        </p>
      )}

      <Card className="p-6">
        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-navy">What is this about?</span>
            <Input
              required
              minLength={3}
              maxLength={300}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="For example: my 80G certificate was rejected"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium text-navy">Your message</span>
            <Textarea
              required
              rows={6}
              maxLength={5000}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </label>

          <Button type="submit" variant="primary" size="md" disabled={sending || !subject.trim() || !message.trim()}>
            {sending ? 'Sending…' : 'Send message'}
          </Button>
        </form>
      </Card>
    </div>
  );
}
