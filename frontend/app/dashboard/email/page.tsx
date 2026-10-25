'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type { NotificationPreferencesOut } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';

export default function EmailPreferencesPage() {
  const [prefs, setPrefs] = useState<NotificationPreferencesOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    donation_received: 'INSTANT',
    milestone_reached: 'INSTANT',
    campaign_published: 'INSTANT',
    ngo_verified: 'INSTANT',
    donor_digest: 'WEEKLY',
    marketing_emails: false,
  });

  // Load preferences on mount
  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    try {
      setLoading(true);
      const data = await api<NotificationPreferencesOut>('/email/preferences');
      setPrefs(data);
      setFormData({
        donation_received: data.donation_received,
        milestone_reached: data.milestone_reached,
        campaign_published: data.campaign_published,
        ngo_verified: data.ngo_verified,
        donor_digest: data.donor_digest,
        marketing_emails: data.marketing_emails,
      });
    } catch (err) {
      setError('Failed to load preferences');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleChangeFrequency = (field: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    setMessage('');
  };

  const handleChangeMarketing = (value: boolean) => {
    setFormData((prev) => ({
      ...prev,
      marketing_emails: value,
    }));
    setMessage('');
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      await api('/email/preferences', {
        method: 'PATCH',
        body: JSON.stringify(formData),
      });
      setMessage('Preferences saved successfully');
      await loadPreferences();
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save preferences');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    try {
      setError('');
      await api('/email/test-email', { method: 'POST' });
      setMessage('Test email sent! Check your inbox in a few seconds');
      setTimeout(() => setMessage(''), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send test email');
    }
  };

  const FREQUENCY_FIELDS: Array<{ key: keyof typeof formData; title: string; description: string }> = [
    {
      key: 'donation_received',
      title: 'Donations Received',
      description: 'Get notified when someone donates to your campaigns',
    },
    {
      key: 'milestone_reached',
      title: 'Campaign Milestones',
      description: 'Get updates when your campaigns reach fundraising milestones',
    },
    {
      key: 'campaign_published',
      title: 'Campaign Published',
      description: 'Get notified when your campaigns are approved and go live',
    },
    {
      key: 'ngo_verified',
      title: 'Organization Verified',
      description: 'Get notified when your organization is verified',
    },
    {
      key: 'donor_digest',
      title: 'Impact Digest',
      description: 'Weekly summary of your donations and impact (donors only)',
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Email Preferences" description="Loading your preferences..." />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <PageHeader
        title="Email Preferences"
        description="Control how often you receive notifications about donations, campaigns, and updates."
      />

      {/* Messages */}
      {message && (
        <div className="rounded-sm border border-status-approved/40 bg-status-approved/10 p-4 text-sm text-status-approved">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {/* Notification Preferences */}
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-navy mb-4">Notification Frequency</h2>
          <p className="text-muted text-sm mb-6">
            Choose how often you want to receive each type of notification.
          </p>

          <div className="space-y-4">
            {FREQUENCY_FIELDS.map((field) => (
              <Card key={field.key} className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-navy">{field.title}</h3>
                    <p className="text-muted text-sm">{field.description}</p>
                  </div>
                  <select
                    value={formData[field.key] as string}
                    onChange={(e) => handleChangeFrequency(field.key, e.target.value)}
                    className="rounded-sm border border-line bg-[#FFFDF7] px-3 py-2 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-[var(--focus)]"
                  >
                    <option value="INSTANT">Instantly</option>
                    <option value="DAILY">Daily digest</option>
                    <option value="WEEKLY">Weekly digest</option>
                    <option value="NEVER">Never</option>
                  </select>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Marketing Emails */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-navy">Marketing Emails</h3>
              <p className="text-muted text-sm">
                Receive emails about new campaigns, features, and opportunities
              </p>
            </div>
            <button
              onClick={() => handleChangeMarketing(!formData.marketing_emails)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.marketing_emails ? 'bg-teal' : 'bg-line'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-[#FFFDF7] transition-transform ${
                  formData.marketing_emails ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </Card>
      </div>

      {/* Unsubscribe Section */}
      {prefs?.unsubscribed_at && (
        <div className="rounded-sm border border-status-pending/40 bg-status-pending/10 p-4">
          <p className="text-status-pending text-sm">
            You are currently unsubscribed from marketing emails.
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Preferences'}
        </Button>
        <Button variant="secondary" onClick={handleTestEmail}>
          Send Test Email
        </Button>
      </div>

      {/* Frequency Explanation */}
      <Card className="p-4 text-sm">
        <p className="font-medium text-navy mb-2">How frequencies work:</p>
        <ul className="space-y-1 text-xs text-muted">
          <li>• <strong className="text-navy">Instantly</strong> — Email sent right away when the event happens</li>
          <li>• <strong className="text-navy">Daily</strong> — All events collected and sent as a digest at 9 AM</li>
          <li>• <strong className="text-navy">Weekly</strong> — All events collected and sent as a digest every Monday at 9 AM</li>
          <li>• <strong className="text-navy">Never</strong> — No emails for this notification type</li>
        </ul>
      </Card>
    </div>
  );
}
