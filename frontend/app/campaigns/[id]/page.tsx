'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface Campaign {
  id: string;
  title: string;
  mission: string;
  description: string;
  budget_total: number;
  amount_raised: number;
  currency: string;
  beneficiary_count: number | null;
  beneficiary_description: string;
  impact_statement: string;
  duration_months: number;
  hero_image_url: string | null;
  donation_count: number;
  status: string;
}

interface Milestone {
  id: string;
  sequence_num: number;
  title: string;
  description: string;
  target_date: string;
  target_amount: number;
  status: string;
  completed_at: string | null;
}

interface DonationType {
  id: string;
  type: string;
  label: string;
  description: string;
  quantity_unit: string | null;
  value_in_rupees: number;
}

interface Impact {
  budget_total: number;
  amount_raised: number;
  completion_percentage: number;
  total_donors: number;
  donation_count: number;
  total_milestones: number;
  completed_milestones: number;
  status: string;
}

export default function CampaignDetailPage() {
  const params = useParams()!;
  const campaignId = params.id as string;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [donationTypes, setDonationTypes] = useState<DonationType[]>([]);
  const [impact, setImpact] = useState<Impact | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDonationModal, setShowDonationModal] = useState(false);
  const [selectedDonationType, setSelectedDonationType] = useState<string | null>(null);

  useEffect(() => {
    fetchCampaignDetails();
  }, [campaignId]);

  const fetchCampaignDetails = async () => {
    setLoading(true);
    try {
      const [campaignRes, milestonesRes, typesRes, impactRes] = await Promise.all([
        fetch(`/api/campaigns/${campaignId}`),
        fetch(`/api/campaigns/${campaignId}/milestones`),
        fetch(`/api/campaigns/${campaignId}/donation-types`),
        fetch(`/api/campaigns/${campaignId}/impact`),
      ]);

      if (campaignRes.ok) setCampaign(await campaignRes.json());
      if (milestonesRes.ok) setMilestones(await milestonesRes.json());
      if (typesRes.ok) setDonationTypes(await typesRes.json());
      if (impactRes.ok) setImpact(await impactRes.json());
    } catch (error) {
      console.error('Failed to fetch campaign details:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !campaign) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading campaign details...</p>
        </div>
      </div>
    );
  }

  const progressPct = impact ? impact.completion_percentage : 0;

  const formatIndian = (num: number) => new Intl.NumberFormat('en-IN').format(num);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Hero Section */}
      <div className="relative h-96 bg-gradient-to-br from-blue-400 to-green-400 overflow-hidden">
        {campaign.hero_image_url ? (
          <img
            src={campaign.hero_image_url}
            alt={campaign.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-white text-9xl opacity-20">💚</div>
          </div>
        )}

        {/* Overlay */}
        <div className="absolute inset-0 bg-black bg-opacity-20" />

        {/* Progress Badge */}
        <div className="absolute top-6 right-6 bg-white rounded-full px-6 py-3 shadow-lg">
          <p className="text-sm font-bold text-gray-900">
            <span className="text-2xl text-green-600">{progressPct}%</span> Funded
          </p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {/* Title & Mission */}
            <div className="mb-8">
              <p className="text-sm font-semibold text-blue-600 uppercase tracking-wide mb-2">
                {campaign.mission}
              </p>
              <h1 className="text-4xl font-bold text-gray-900 mb-4">{campaign.title}</h1>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 py-6 border-t border-b border-gray-200">
                <div>
                  <p className="text-xs text-gray-600 font-semibold uppercase mb-1">Raised</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ₹{formatIndian(campaign.amount_raised)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">of ₹{formatIndian(campaign.budget_total)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-600 font-semibold uppercase mb-1">Donors</p>
                  <p className="text-2xl font-bold text-gray-900">{impact?.total_donors || 0}</p>
                  <p className="text-xs text-gray-500 mt-1">people supporting</p>
                </div>
                <div>
                  <p className="text-xs text-gray-600 font-semibold uppercase mb-1">Timeline</p>
                  <p className="text-2xl font-bold text-gray-900">{campaign.duration_months}mo</p>
                  <p className="text-xs text-gray-500 mt-1">campaign duration</p>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="story" className="mt-8">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="story">Story</TabsTrigger>
                <TabsTrigger value="milestones">Milestones</TabsTrigger>
                <TabsTrigger value="impact">Impact</TabsTrigger>
              </TabsList>

              {/* Story Tab */}
              <TabsContent value="story" className="mt-6">
                <Card className="p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-4">Campaign Story</h2>
                  <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                    {campaign.description}
                  </div>

                  <div className="mt-8 p-6 bg-blue-50 border border-blue-200 rounded-lg">
                    <h3 className="font-bold text-blue-900 mb-2">🎯 Our Impact Vision</h3>
                    <p className="text-blue-800">{campaign.impact_statement}</p>
                  </div>

                  {campaign.beneficiary_count && (
                    <div className="mt-6 p-6 bg-green-50 border border-green-200 rounded-lg">
                      <h3 className="font-bold text-green-900 mb-2">👥 Who We Serve</h3>
                      <p className="text-green-800 mb-2">
                        <strong>{formatIndian(campaign.beneficiary_count)}</strong> people will benefit directly from this campaign
                      </p>
                      <p className="text-green-700">{campaign.beneficiary_description}</p>
                    </div>
                  )}
                </Card>
              </TabsContent>

              {/* Milestones Tab */}
              <TabsContent value="milestones" className="mt-6">
                <div className="space-y-4">
                  {milestones.map((milestone, idx) => (
                    <Card key={milestone.id} className="p-6">
                      <div className="flex gap-4">
                        <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${
                          milestone.status === 'COMPLETED'
                            ? 'bg-green-500'
                            : milestone.status === 'IN_PROGRESS'
                            ? 'bg-blue-500'
                            : 'bg-gray-300'
                        }`}>
                          {milestone.status === 'COMPLETED' ? '✓' : idx + 1}
                        </div>
                        <div className="flex-1">
                          <h3 className="font-bold text-gray-900 text-lg">{milestone.title}</h3>
                          <p className="text-gray-600 mt-2">{milestone.description}</p>
                          <div className="flex items-center justify-between mt-4 text-sm">
                            <span className="text-gray-500">
                              Target: <strong>₹{formatIndian(milestone.target_amount)}</strong>
                            </span>
                            <span className="text-gray-500">
                              By: <strong>{new Date(milestone.target_date).toLocaleDateString()}</strong>
                            </span>
                            {milestone.status === 'COMPLETED' && (
                              <span className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-xs font-semibold">
                                Completed
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              {/* Impact Tab */}
              <TabsContent value="impact" className="mt-6">
                <Card className="p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Campaign Progress</h2>

                  {/* Progress Bar */}
                  <div className="mb-8">
                    <div className="flex justify-between mb-2">
                      <span className="text-sm font-semibold text-gray-900">Funding Progress</span>
                      <span className="text-sm font-bold text-green-600">{progressPct}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-green-500 h-full transition-all duration-500"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                  </div>

                  {/* Metrics */}
                  <div className="grid grid-cols-2 gap-6">
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <p className="text-xs text-blue-600 font-semibold uppercase mb-1">Milestones</p>
                      <p className="text-3xl font-bold text-blue-900">
                        {impact?.completed_milestones}/{impact?.total_milestones}
                      </p>
                      <p className="text-xs text-blue-700 mt-1">completed</p>
                    </div>
                    <div className="p-4 bg-green-50 rounded-lg">
                      <p className="text-xs text-green-600 font-semibold uppercase mb-1">Donors</p>
                      <p className="text-3xl font-bold text-green-900">{impact?.total_donors}</p>
                      <p className="text-xs text-green-700 mt-1">supporting this cause</p>
                    </div>
                  </div>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

          {/* Sidebar - Donation */}
          <div className="lg:col-span-1">
            <Card className="sticky top-24 p-6 bg-gradient-to-br from-blue-50 to-green-50 border-2 border-blue-200">
              <h3 className="text-xl font-bold text-gray-900 mb-4">Make Your Impact</h3>

              {/* Donation Types */}
              <div className="space-y-3 mb-6">
                {donationTypes.map((type) => (
                  <button
                    key={type.id}
                    onClick={() => {
                      setSelectedDonationType(type.id);
                      setShowDonationModal(true);
                    }}
                    className={`w-full text-left p-4 rounded-lg border-2 transition ${
                      selectedDonationType === type.id
                        ? 'border-blue-600 bg-blue-100'
                        : 'border-gray-200 bg-white hover:border-blue-400'
                    }`}
                  >
                    <p className="font-bold text-gray-900">{type.label}</p>
                    <p className="text-xs text-gray-600 mt-1">{type.description}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Impact value: <strong>₹{formatIndian(type.value_in_rupees)}</strong>
                    </p>
                  </button>
                ))}
              </div>

              {/* CTA Button */}
              <Button
                onClick={() => setShowDonationModal(true)}
                className="w-full bg-gradient-to-r from-blue-600 to-green-600 hover:from-blue-700 hover:to-green-700 text-white py-6 text-lg font-bold rounded-lg"
              >
                💚 Donate Now
              </Button>

              <p className="text-xs text-gray-600 text-center mt-4">
                Your donation is 100% transparent. Track where your money goes.
              </p>

              {/* Trust Badges */}
              <div className="mt-6 pt-6 border-t border-gray-200 space-y-2">
                <div className="flex items-center gap-2 text-xs text-gray-700">
                  <span>✓</span>
                  <span>Verified NGO</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-700">
                  <span>✓</span>
                  <span>Transparent Budget</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-700">
                  <span>✓</span>
                  <span>Impact Tracking</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Donation Modal */}
      {showDonationModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="max-w-md w-full p-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Complete Your Donation</h2>
            <p className="text-gray-600 mb-6">
              You're about to make a real difference in someone's life. Every donation counts.
            </p>
            <Button
              onClick={() => setShowDonationModal(false)}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white mb-3"
            >
              Continue to Payment
            </Button>
            <Button
              onClick={() => setShowDonationModal(false)}
              variant="outline"
              className="w-full"
            >
              Cancel
            </Button>
          </Card>
        </div>
      )}
    </div>
  );
}
