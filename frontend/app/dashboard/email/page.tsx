'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type { NotificationPreferencesOut } from '@/lib/types';

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
      setMessage('✓ Preferences saved successfully');
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
      setMessage('✓ Test email sent! Check your inbox in a few seconds');
      setTimeout(() => setMessage(''), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send test email');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Email Preferences</h1>
          <p className="text-muted mt-2">Loading your preferences...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Email Preferences</h1>
        <p className="text-muted mt-2">
          Control how often you receive notifications about donations, campaigns, and updates.
        </p>
      </div>

      {/* Messages */}
      {message && (
        <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-green-800 text-sm">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-800 text-sm">
          {error}
        </div>
      )}

      {/* Notification Preferences */}
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold mb-4">Notification Frequency</h2>
          <p className="text-muted text-sm mb-6">
            Choose how often you want to receive each type of notification.
          </p>

          {/* Donation Received */}
          <div className="border rounded-lg p-6 mb-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold">Donations Received</h3>
                <p className="text-muted text-sm">
                  Get notified when someone donates to your campaigns
                </p>
              </div>
              <select
                value={formData.donation_received}
                onChange={(e) => handleChangeFrequency('donation_received', e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="INSTANT">Instantly</option>
                <option value="DAILY">Daily digest</option>
                <option value="WEEKLY">Weekly digest</option>
                <option value="NEVER">Never</option>
              </select>
            </div>
          </div>

          {/* Milestone Reached */}
          <div className="border rounded-lg p-6 mb-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold">Campaign Milestones</h3>
                <p className="text-muted text-sm">
                  Get updates when your campaigns reach fundraising milestones
                </p>
              </div>
              <select
                value={formData.milestone_reached}
                onChange={(e) => handleChangeFrequency('milestone_reached', e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="INSTANT">Instantly</option>
                <option value="DAILY">Daily digest</option>
                <option value="WEEKLY">Weekly digest</option>
                <option value="NEVER">Never</option>
              </select>
            </div>
          </div>

          {/* Campaign Published */}
          <div className="border rounded-lg p-6 mb-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold">Campaign Published</h3>
                <p className="text-muted text-sm">
                  Get notified when your campaigns are approved and go live
                </p>
              </div>
              <select
                value={formData.campaign_published}
                onChange={(e) => handleChangeFrequency('campaign_published', e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="INSTANT">Instantly</option>
                <option value="DAILY">Daily digest</option>
                <option value="WEEKLY">Weekly digest</option>
                <option value="NEVER">Never</option>
              </select>
            </div>
          </div>

          {/* NGO Verified */}
          <div className="border rounded-lg p-6 mb-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold">Organization Verified</h3>
                <p className="text-muted text-sm">
                  Get notified when your organization is verified
                </p>
              </div>
              <select
                value={formData.ngo_verified}
                onChange={(e) => handleChangeFrequency('ngo_verified', e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="INSTANT">Instantly</option>
                <option value="DAILY">Daily digest</option>
                <option value="WEEKLY">Weekly digest</option>
                <option value="NEVER">Never</option>
              </select>
            </div>
          </div>

          {/* Donor Digest */}
          <div className="border rounded-lg p-6 mb-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="font-semibold">Impact Digest</h3>
                <p className="text-muted text-sm">
                  Weekly summary of your donations and impact (donors only)
                </p>
              </div>
              <select
                value={formData.donor_digest}
                onChange={(e) => handleChangeFrequency('donor_digest', e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="INSTANT">Instantly</option>
                <option value="DAILY">Daily digest</option>
                <option value="WEEKLY">Weekly digest</option>
                <option value="NEVER">Never</option>
              </select>
            </div>
          </div>
        </div>

        {/* Marketing Emails */}
        <div className="border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Marketing Emails</h3>
              <p className="text-muted text-sm">
                Receive emails about new campaigns, features, and opportunities
              </p>
            </div>
            <button
              onClick={() => handleChangeMarketing(!formData.marketing_emails)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.marketing_emails ? 'bg-teal-500' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.marketing_emails ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Unsubscribe Section */}
      {prefs?.unsubscribed_at && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-4">
          <p className="text-amber-800 text-sm">
            You are currently unsubscribed from marketing emails.
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-sm bg-teal px-6 py-2.5 font-medium text-paper hover:opacity-90 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Preferences'}
        </button>
        <button
          onClick={handleTestEmail}
          className="rounded-sm border-2 border-navy px-6 py-2.5 font-medium text-navy hover:bg-navy hover:text-paper"
        >
          Send Test Email
        </button>
      </div>

      {/* Frequency Explanation */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm text-blue-900">
        <p className="font-medium mb-2">How frequencies work:</p>
        <ul className="space-y-1 text-xs">
          <li>• <strong>Instantly</strong> — Email sent right away when the event happens</li>
          <li>• <strong>Daily</strong> — All events collected and sent as a digest at 9 AM</li>
          <li>• <strong>Weekly</strong> — All events collected and sent as a digest every Monday at 9 AM</li>
          <li>• <strong>Never</strong> — No emails for this notification type</li>
        </ul>
      </div>
    </div>
  );
}
