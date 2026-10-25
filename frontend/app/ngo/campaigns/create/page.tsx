'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { cn } from '@/components/ui/cn';

interface CampaignStep {
  step: number;
  title: string;
  completed: boolean;
}

interface FormData {
  title: string;
  mission: string;
  description: string;
  beneficiaryCount: number;
  beneficiaryDescription: string;
  impactStatement: string;
  budgetTotal: number;
  currency: string;
  budgetBreakdown: Record<string, number>;
  durationMonths: number;
  heroImageUrl: string;
}

export default function CreateCampaignPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [campaignId, setCampaignId] = useState('');

  const [form, setForm] = useState<FormData>({
    title: '',
    mission: '',
    description: '',
    beneficiaryCount: 0,
    beneficiaryDescription: '',
    impactStatement: '',
    budgetTotal: 0,
    currency: 'INR',
    budgetBreakdown: {},
    durationMonths: 12,
    heroImageUrl: '',
  });

  const steps: CampaignStep[] = [
    { step: 1, title: 'Campaign Basics', completed: false },
    { step: 2, title: 'Impact & Beneficiaries', completed: false },
    { step: 3, title: 'Budget & Timeline', completed: false },
    { step: 4, title: 'Milestones', completed: false },
    { step: 5, title: 'Donation Types', completed: false },
    { step: 6, title: 'Review & Submit', completed: false },
  ];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: name === 'budgetTotal' || name === 'beneficiaryCount' || name === 'durationMonths'
        ? parseInt(value) || 0
        : value,
    }));
  };

  const handleCreateCampaign = async () => {
    setLoading(true);
    setError('');

    try {
      const token = sessionStorage.getItem('access_token');
      const response = await fetch('/api/ngo/campaigns', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error('Failed to create campaign');
      }

      const data = await response.json();
      setCampaignId(data.id);
      setCurrentStep(4); // Move to milestones
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating campaign');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitForReview = async () => {
    setLoading(true);
    setError('');

    try {
      const token = sessionStorage.getItem('access_token');
      const response = await fetch(`/api/ngo/campaigns/${campaignId}/submit-for-review`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to submit campaign');
      }

      router.push(`/ngo/campaigns/${campaignId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error submitting campaign');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="NGO"
        title="Create a Campaign"
        description="Make a real impact. Tell your story. Get funded."
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        {/* Sidebar - Steps */}
        <div className="lg:col-span-1">
          <div className="sticky top-24">
            <h3 className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-muted">
              Campaign Setup
            </h3>
            <nav className="space-y-2">
              {steps.map((s) => (
                <button
                  key={s.step}
                  type="button"
                  onClick={() => setCurrentStep(s.step)}
                  className={cn(
                    'w-full rounded-sm px-4 py-2 text-left transition-colors',
                    currentStep === s.step ? 'bg-navy/10 font-semibold text-navy' : 'text-muted hover:bg-navy/5',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-full font-mono text-sm font-bold',
                        s.step < currentStep
                          ? 'bg-status-approved text-paper'
                          : currentStep === s.step
                          ? 'bg-navy text-paper'
                          : 'bg-navy/10 text-muted',
                      )}
                    >
                      {s.step < currentStep ? '✓' : s.step}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{s.title}</p>
                    </div>
                  </div>
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3">
          <Card>
            {/* Step 1: Campaign Basics */}
            {currentStep === 1 && (
              <div className="p-8">
                <h2 className="mb-6 font-display text-2xl font-semibold text-navy">Campaign Basics</h2>
                <div className="space-y-6">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-navy">
                      Campaign Title
                    </label>
                    <Input
                      name="title"
                      value={form.title}
                      onChange={handleInputChange}
                      placeholder="e.g., Clean Water for 50 Villages"
                      className="text-base"
                    />
                    <p className="mt-1 text-xs text-muted">10-300 characters. Make it compelling!</p>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-navy">
                      Campaign Mission (One-liner)
                    </label>
                    <Input
                      name="mission"
                      value={form.mission}
                      onChange={handleInputChange}
                      placeholder="e.g., Provide clean drinking water to rural communities"
                      className="text-base"
                    />
                    <p className="mt-1 text-xs text-muted">5-500 characters. The essence of your cause.</p>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-navy">
                      Full Campaign Description
                    </label>
                    <Textarea
                      name="description"
                      value={form.description}
                      onChange={handleInputChange}
                      placeholder="Tell your story... Why does this matter? What's the problem? How will you solve it?"
                      rows={6}
                      className="text-base"
                    />
                    <p className="mt-1 text-xs text-muted">50-5000 characters. Be detailed and authentic.</p>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-navy">
                      Hero Image URL
                    </label>
                    <Input
                      name="heroImageUrl"
                      value={form.heroImageUrl}
                      onChange={handleInputChange}
                      placeholder="https://example.com/image.jpg"
                      type="url"
                      className="text-base"
                    />
                    <p className="mt-1 text-xs text-muted">High-impact image for campaign cover</p>
                  </div>
                </div>

                <div className="mt-8 flex gap-4">
                  <Button onClick={() => setCurrentStep(2)} variant="primary" className="flex-1">
                    Continue
                  </Button>
                </div>
              </div>
            )}

              {/* Step 2: Impact & Beneficiaries */}
              {currentStep === 2 && (
                <div className="p-8">
                  <h2 className="mb-6 font-display text-2xl font-semibold text-navy">Impact & Beneficiaries</h2>
                  <div className="space-y-6">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-navy">
                        How many people will benefit?
                      </label>
                      <Input
                        name="beneficiaryCount"
                        type="number"
                        value={form.beneficiaryCount || ''}
                        onChange={handleInputChange}
                        placeholder="e.g., 500"
                        className="text-base"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-navy">
                        Who are your beneficiaries? (Describe them clearly)
                      </label>
                      <Textarea
                        name="beneficiaryDescription"
                        value={form.beneficiaryDescription}
                        onChange={handleInputChange}
                        placeholder="e.g., Children aged 6-14 in rural Karnataka who lack access to quality education..."
                        rows={4}
                        className="text-base"
                      />
                      <p className="mt-1 text-xs text-muted">Be specific! Who exactly will this help?</p>
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-navy">
                        What impact will you create?
                      </label>
                      <Textarea
                        name="impactStatement"
                        value={form.impactStatement}
                        onChange={handleInputChange}
                        placeholder="e.g., Will improve literacy rates by 60% and reduce school dropout rates..."
                        rows={4}
                        className="text-base"
                      />
                      <p className="mt-1 text-xs text-muted">Be measurable and realistic!</p>
                    </div>
                  </div>

                  <div className="mt-8 flex gap-4">
                    <Button
                      onClick={() => setCurrentStep(1)}
                      variant="secondary"
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      onClick={() => setCurrentStep(3)}
                      variant="primary"
                      className="flex-1"
                    >
                      Continue
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 3: Budget & Timeline */}
              {currentStep === 3 && (
                <div className="p-8">
                  <h2 className="mb-6 font-display text-2xl font-semibold text-navy">Budget & Timeline</h2>
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="mb-2 block text-sm font-medium text-navy">
                          Total Budget Needed
                        </label>
                        <div className="flex items-center gap-2">
                          <Input
                            name="budgetTotal"
                            type="number"
                            value={form.budgetTotal || ''}
                            onChange={handleInputChange}
                            placeholder="500000"
                            className="text-base"
                          />
                          <span className="text-sm font-semibold text-muted">INR</span>
                        </div>
                      </div>

                      <div>
                        <label className="mb-2 block text-sm font-medium text-navy">
                          Campaign Duration
                        </label>
                        <div className="flex items-center gap-2">
                          <Input
                            name="durationMonths"
                            type="number"
                            value={form.durationMonths}
                            onChange={handleInputChange}
                            min="1"
                            max="60"
                            className="text-base"
                          />
                          <span className="text-sm font-semibold text-muted">months</span>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-sm border border-line bg-navy/5 p-4">
                      <p className="mb-3 text-sm font-semibold text-navy">Budget Breakdown (Optional)</p>
                      <p className="text-xs text-muted">
                        Help donors understand where their money goes. You can add this in the next step.
                      </p>
                    </div>
                  </div>

                  <div className="mt-8 flex gap-4">
                    <Button
                      onClick={() => setCurrentStep(2)}
                      variant="secondary"
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      onClick={handleCreateCampaign}
                      disabled={loading}
                      variant="primary"
                      className="flex-1"
                    >
                      {loading ? 'Creating...' : 'Create Campaign'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 4 & 5 - Will show after campaign creation */}
              {(currentStep === 4 || currentStep === 5) && campaignId && (
                <div className="p-8 text-center">
                  <div className="mb-4 text-5xl text-status-approved">✓</div>
                  <h2 className="mb-2 font-display text-2xl font-semibold text-navy">Campaign Created!</h2>
                  <p className="mb-6 text-muted">
                    Now add milestones and donation type options to make your campaign complete.
                  </p>
                  <Button
                    onClick={() => router.push(`/ngo/campaigns/${campaignId}/edit`)}
                    variant="primary"
                  >
                    Continue Setting Up
                  </Button>
                </div>
              )}

              {error && (
                <div role="alert" className="m-6 rounded-sm border-2 border-status-rejected bg-white p-4 text-sm text-status-rejected">
                  {error}
                </div>
              )}
            </Card>
          </div>
      </div>
    </div>
  );
}
