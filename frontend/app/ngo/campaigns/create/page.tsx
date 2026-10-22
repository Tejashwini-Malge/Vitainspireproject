'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';

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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Create a Campaign</h1>
          <p className="text-gray-600 mt-1">Make a real impact. Tell your story. Get funded.</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar - Steps */}
          <div className="lg:col-span-1">
            <div className="sticky top-24">
              <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Campaign Setup
              </h3>
              <nav className="space-y-2">
                {steps.map((s) => (
                  <button
                    key={s.step}
                    onClick={() => setCurrentStep(s.step)}
                    className={`w-full text-left px-4 py-2 rounded-lg transition ${
                      currentStep === s.step
                        ? 'bg-blue-100 text-blue-900 font-semibold'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                          s.step < currentStep
                            ? 'bg-green-500 text-white'
                            : currentStep === s.step
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-200 text-gray-700'
                        }`}
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
            <Card className="bg-white">
              {/* Step 1: Campaign Basics */}
              {currentStep === 1 && (
                <div className="p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Campaign Basics</h2>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">
                        Campaign Title
                      </label>
                      <Input
                        name="title"
                        value={form.title}
                        onChange={handleInputChange}
                        placeholder="e.g., Clean Water for 50 Villages"
                        className="text-base"
                      />
                      <p className="text-xs text-gray-500 mt-1">10-300 characters. Make it compelling!</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">
                        Campaign Mission (One-liner)
                      </label>
                      <Input
                        name="mission"
                        value={form.mission}
                        onChange={handleInputChange}
                        placeholder="e.g., Provide clean drinking water to rural communities"
                        className="text-base"
                      />
                      <p className="text-xs text-gray-500 mt-1">5-500 characters. The essence of your cause.</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">
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
                      <p className="text-xs text-gray-500 mt-1">50-5000 characters. Be detailed and authentic.</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">
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
                      <p className="text-xs text-gray-500 mt-1">High-impact image for campaign cover</p>
                    </div>
                  </div>

                  <div className="flex gap-4 mt-8">
                    <Button
                      onClick={() => setCurrentStep(2)}
                      className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      Continue
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 2: Impact & Beneficiaries */}
              {currentStep === 2 && (
                <div className="p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Impact & Beneficiaries</h2>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">
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
                      <label className="block text-sm font-medium text-gray-900 mb-2">
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
                      <p className="text-xs text-gray-500 mt-1">Be specific! Who exactly will this help?</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">
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
                      <p className="text-xs text-gray-500 mt-1">Be measurable and realistic!</p>
                    </div>
                  </div>

                  <div className="flex gap-4 mt-8">
                    <Button
                      onClick={() => setCurrentStep(1)}
                      variant="outline"
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      onClick={() => setCurrentStep(3)}
                      className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      Continue
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 3: Budget & Timeline */}
              {currentStep === 3 && (
                <div className="p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Budget & Timeline</h2>
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-900 mb-2">
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
                          <span className="text-sm font-semibold text-gray-600">INR</span>
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-900 mb-2">
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
                          <span className="text-sm font-semibold text-gray-600">months</span>
                        </div>
                      </div>
                    </div>

                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-sm font-semibold text-blue-900 mb-3">Budget Breakdown (Optional)</p>
                      <p className="text-xs text-blue-700">
                        Help donors understand where their money goes. You can add this in the next step.
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-4 mt-8">
                    <Button
                      onClick={() => setCurrentStep(2)}
                      variant="outline"
                      className="flex-1"
                    >
                      Back
                    </Button>
                    <Button
                      onClick={handleCreateCampaign}
                      disabled={loading}
                      className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                    >
                      {loading ? 'Creating...' : 'Create Campaign'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 4 & 5 - Will show after campaign creation */}
              {(currentStep === 4 || currentStep === 5) && campaignId && (
                <div className="p-8 text-center">
                  <div className="text-green-600 text-5xl mb-4">✓</div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">Campaign Created!</h2>
                  <p className="text-gray-600 mb-6">
                    Now add milestones and donation type options to make your campaign complete.
                  </p>
                  <Button
                    onClick={() => router.push(`/ngo/campaigns/${campaignId}/edit`)}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    Continue Setting Up
                  </Button>
                </div>
              )}

              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
