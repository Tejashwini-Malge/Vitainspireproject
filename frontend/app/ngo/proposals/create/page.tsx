'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';

interface Opportunity {
  id: string;
  title: string;
  org_id: string;
}

export default function CreateProposalPage() {
  const router = useRouter();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    opportunity_id: '',
    problem_statement: '',
    solution: '',
    budget_requested: '',
    timeline: '',
    expected_outcomes: '',
  });

  useEffect(() => {
    api<(Opportunity & { status: string })[]>('/csr/opportunities?status_filter=PUBLISHED')
      .then(data => setOpportunities(data || []))
      .catch(() => setError('Failed to load opportunities'));
  }, []);

  const handleGenerate = async () => {
    if (!formData.opportunity_id) return;
    setGenerating(true);
    setError('');
    try {
      const draft = await api<{
        problem_statement: string;
        solution: string;
        timeline: string;
        expected_outcomes: string;
      }>('/ngo/proposals/generate-draft', {
        method: 'POST',
        body: JSON.stringify({ opportunity_id: formData.opportunity_id }),
      });
      setFormData(prev => ({
        ...prev,
        problem_statement: draft.problem_statement,
        solution: draft.solution,
        timeline: draft.timeline,
        expected_outcomes: draft.expected_outcomes,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate draft');
    } finally {
      setGenerating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await api('/ngo/proposals', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          budget_requested: parseInt(formData.budget_requested),
        }),
      });
      router.push('/ngo/proposals');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit proposal');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader eyebrow="NGO" title="Submit Proposal" />

      {error && (
        <div role="alert" className="rounded-sm border-2 border-status-rejected bg-white p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      <Card className="p-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="mb-2 block text-sm font-semibold text-navy">Select Opportunity *</label>
            <select
              value={formData.opportunity_id}
              onChange={e => setFormData({ ...formData, opportunity_id: e.target.value })}
              className="w-full rounded-sm border border-line bg-[#FFFDF7] px-3 py-2 text-ink transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--focus)] focus:ring-offset-1"
              required
            >
              <option value="">Choose an opportunity...</option>
              {opportunities.map(opp => (
                <option key={opp.id} value={opp.id}>
                  {opp.title}
                </option>
              ))}
            </select>
          </div>

          {formData.opportunity_id && (
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={handleGenerate}
                disabled={generating}
              >
                {generating ? 'Generating…' : 'Generate draft with AI'}
              </Button>
              <p className="text-xs text-muted">
                Drafts the fields below from this opportunity and your NGO profile — review and edit before submitting.
              </p>
            </div>
          )}

          <div>
            <label className="mb-2 block text-sm font-semibold text-navy">Problem Statement *</label>
            <Textarea
              value={formData.problem_statement}
              onChange={e => setFormData({ ...formData, problem_statement: e.target.value })}
              rows={4}
              minLength={10}
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-navy">Solution *</label>
            <Textarea
              value={formData.solution}
              onChange={e => setFormData({ ...formData, solution: e.target.value })}
              rows={4}
              minLength={10}
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-navy">Budget Requested (₹) *</label>
            <Input
              type="number"
              value={formData.budget_requested}
              onChange={e => setFormData({ ...formData, budget_requested: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-navy">Timeline *</label>
            <Input
              type="text"
              value={formData.timeline}
              onChange={e => setFormData({ ...formData, timeline: e.target.value })}
              placeholder="e.g., 12 months"
              minLength={5}
              required
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-navy">Expected Outcomes *</label>
            <Textarea
              value={formData.expected_outcomes}
              onChange={e => setFormData({ ...formData, expected_outcomes: e.target.value })}
              rows={3}
              minLength={10}
              required
            />
          </div>

          <div className="flex gap-4">
            <Button type="submit" variant="primary" disabled={loading}>
              {loading ? 'Submitting...' : 'Submit Proposal'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
