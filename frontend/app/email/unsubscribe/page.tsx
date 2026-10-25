'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';

// useSearchParams forces client rendering, so the page must present a Suspense
// boundary or the static export of this route fails at build time.
export default function UnsubscribePage() {
  return (
    <Suspense fallback={<p className="p-8 text-center text-muted">Loading…</p>}>
      <UnsubscribeContent />
    </Suspense>
  );
}

function UnsubscribeContent() {
  const searchParams = useSearchParams();
  const token = searchParams?.get('token') ?? null;

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError('Invalid or missing unsubscribe link');
      return;
    }

    handleUnsubscribe();
  }, [token]);

  const handleUnsubscribe = async () => {
    try {
      setStatus('loading');
      await api('/email/unsubscribe', {
        method: 'POST',
        body: JSON.stringify({ token }),
      });
      setStatus('success');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to unsubscribe');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <Card className="w-full max-w-md p-8 text-center">
        {status === 'loading' && (
          <div className="space-y-4">
            <div className="inline-block animate-spin">
              <svg className="w-8 h-8 text-teal" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
            <p className="text-muted">Processing your request...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-4">
            <div className="text-5xl text-status-approved mb-4">✓</div>
            <h1 className="text-2xl font-semibold text-navy">Unsubscribed</h1>
            <p className="text-muted">
              You've been unsubscribed from marketing emails. You'll no longer receive promotional content from Imparency.
            </p>
            <div className="rounded-sm border border-line bg-navy/5 p-4 text-left text-sm text-ink">
              <p className="font-medium text-navy mb-2">What changes:</p>
              <ul className="space-y-1">
                <li>No more marketing emails</li>
                <li>No campaign announcements</li>
                <li>No feature updates</li>
                <li>Important notifications still sent</li>
              </ul>
            </div>
            <p className="text-xs text-muted">
              You can manage all your preferences anytime by signing in and visiting your email settings.
            </p>
            <div className="flex gap-3 pt-4">
              <Link href="/" className="flex-1 rounded-sm bg-teal px-5 py-2.5 text-center font-display text-sm font-medium text-paper hover:opacity-90">
                Back to Home
              </Link>
              <Link href="/login" className="flex-1 rounded-sm border-2 border-navy px-5 py-2.5 text-center font-display text-sm font-medium text-navy hover:bg-navy hover:text-paper">
                Sign In
              </Link>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <div className="text-5xl text-status-rejected mb-4">!</div>
            <h1 className="text-2xl font-semibold text-navy">Unsubscribe Failed</h1>
            <p className="text-status-rejected font-medium">{error}</p>
            <p className="text-muted text-sm">
              The unsubscribe link may have expired or been invalid. Please try one of the following:
            </p>
            <div className="rounded-sm border border-status-pending/30 bg-status-pending/5 p-4 text-left text-sm text-ink space-y-2">
              <p>
                <strong className="text-navy">Option 1:</strong> Sign in to your account and manage preferences in your email settings
              </p>
              <p>
                <strong className="text-navy">Option 2:</strong> Reply to any Imparency email asking to unsubscribe
              </p>
              <p>
                <strong className="text-navy">Option 3:</strong> Contact us at support@imparency.org
              </p>
            </div>
            <div className="flex gap-3 pt-4">
              <Link href="/" className="flex-1 rounded-sm bg-teal px-5 py-2.5 text-center font-display text-sm font-medium text-paper hover:opacity-90">
                Back to Home
              </Link>
              <Link href="/login" className="flex-1 rounded-sm border-2 border-navy px-5 py-2.5 text-center font-display text-sm font-medium text-navy hover:bg-navy hover:text-paper">
                Sign In
              </Link>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
