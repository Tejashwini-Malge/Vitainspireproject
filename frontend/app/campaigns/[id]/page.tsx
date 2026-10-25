'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-line border-t-teal" />
          <p className="text-muted">Loading campaign details...</p>
        </div>
      </div>
    );
  }

  const progressPct = impact ? impact.completion_percentage : 0;

  const formatIndian = (num: number) => new Intl.NumberFormat('en-IN').format(num);

  return (
    <div className="space-y-10 -mt-6">
      {/* Hero Section */}
      <div className="relative -mx-4 h-96 overflow-hidden border-b-2 border-navy bg-navy/10 sm:-mx-6">
        {campaign.hero_image_url ? (
          <img
            src={campaign.hero_image_url}
            alt={campaign.title}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-9xl text-navy/10">
            ◈
          </div>
        )}

        {/* Overlay */}
        <div className="absolute inset-0 bg-navy/20" />

        {/* Progress Badge */}
        <div className="absolute top-6 right-6 rounded-sm border border-line bg-[#FFFDF7] px-6 py-3 shadow-sm">
          <p className="text-sm font-semibold text-navy">
            <span className="text-2xl text-status-approved">{progressPct}%</span> Funded
          </p>
        </div>
      </div>

      <div className="mx-auto max-w-5xl">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {/* Title & Mission */}
            <div className="mb-8">
              <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted mb-2">
                {campaign.mission}
              </p>
              <h1 className="text-4xl font-display font-semibold text-navy mb-4">{campaign.title}</h1>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 py-6 border-t border-b border-line">
                <div>
                  <p className="text-xs text-muted font-semibold uppercase mb-1">Raised</p>
                  <p className="text-2xl font-semibold text-navy">
                    ₹{formatIndian(campaign.amount_raised)}
                  </p>
                  <p className="text-xs text-muted mt-1">of ₹{formatIndian(campaign.budget_total)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted font-semibold uppercase mb-1">Donors</p>
                  <p className="text-2xl font-semibold text-navy">{impact?.total_donors || 0}</p>
                  <p className="text-xs text-muted mt-1">people supporting</p>
                </div>
                <div>
                  <p className="text-xs text-muted font-semibold uppercase mb-1">Timeline</p>
                  <p className="text-2xl font-semibold text-navy">{campaign.duration_months}mo</p>
                  <p className="text-xs text-muted mt-1">campaign duration</p>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="story" className="mt-8">
              <TabsList className="grid w-full grid-cols-3 rounded-sm border border-line bg-navy/5 p-1">
                <TabsTrigger value="story">Story</TabsTrigger>
                <TabsTrigger value="milestones">Milestones</TabsTrigger>
                <TabsTrigger value="impact">Impact</TabsTrigger>
              </TabsList>

              {/* Story Tab */}
              <TabsContent value="story" className="mt-6">
                <Card className="p-8">
                  <h2 className="text-2xl font-semibold text-navy mb-4">Campaign Story</h2>
                  <div className="prose prose-sm max-w-none text-ink whitespace-pre-wrap">
                    {campaign.description}
                  </div>

                  <div className="mt-8 rounded-sm border border-teal/30 bg-teal/5 p-6">
                    <h3 className="font-semibold text-navy mb-2">Our Impact Vision</h3>
                    <p className="text-ink">{campaign.impact_statement}</p>
                  </div>

                  {campaign.beneficiary_count && (
                    <div className="mt-6 rounded-sm border border-status-approved/30 bg-status-approved/5 p-6">
                      <h3 className="font-semibold text-navy mb-2">Who We Serve</h3>
                      <p className="text-ink mb-2">
                        <strong>{formatIndian(campaign.beneficiary_count)}</strong> people will benefit directly from this campaign
                      </p>
                      <p className="text-muted">{campaign.beneficiary_description}</p>
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
                        <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                          milestone.status === 'COMPLETED'
                            ? 'bg-status-approved text-paper'
                            : milestone.status === 'IN_PROGRESS'
                            ? 'bg-teal text-paper'
                            : 'bg-line text-muted'
                        }`}>
                          {milestone.status === 'COMPLETED' ? '✓' : idx + 1}
                        </div>
                        <div className="flex-1">
                          <h3 className="font-semibold text-navy text-lg">{milestone.title}</h3>
                          <p className="text-muted mt-2">{milestone.description}</p>
                          <div className="flex items-center justify-between mt-4 text-sm">
                            <span className="text-muted">
                              Target: <strong className="text-navy">₹{formatIndian(milestone.target_amount)}</strong>
                            </span>
                            <span className="text-muted">
                              By: <strong className="text-navy">{new Date(milestone.target_date).toLocaleDateString()}</strong>
                            </span>
                            {milestone.status === 'COMPLETED' && <Badge tone="approved">Completed</Badge>}
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
                  <h2 className="text-2xl font-semibold text-navy mb-6">Campaign Progress</h2>

                  {/* Progress Bar */}
                  <div className="mb-8">
                    <div className="flex justify-between mb-2">
                      <span className="text-sm font-semibold text-navy">Funding Progress</span>
                      <span className="text-sm font-semibold text-status-approved">{progressPct}%</span>
                    </div>
                    <div className="w-full bg-line rounded-full h-4 overflow-hidden">
                      <div
                        className="bg-teal h-full transition-all duration-500"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                  </div>

                  {/* Metrics */}
                  <div className="grid grid-cols-2 gap-6">
                    <div className="p-4 rounded-sm border border-line bg-navy/5">
                      <p className="text-xs text-muted font-semibold uppercase mb-1">Milestones</p>
                      <p className="text-3xl font-semibold text-navy">
                        {impact?.completed_milestones}/{impact?.total_milestones}
                      </p>
                      <p className="text-xs text-muted mt-1">completed</p>
                    </div>
                    <div className="p-4 rounded-sm border border-status-approved/30 bg-status-approved/5">
                      <p className="text-xs text-status-approved font-semibold uppercase mb-1">Donors</p>
                      <p className="text-3xl font-semibold text-navy">{impact?.total_donors}</p>
                      <p className="text-xs text-muted mt-1">supporting this cause</p>
                    </div>
                  </div>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

          {/* Sidebar - Donation */}
          <div className="lg:col-span-1">
            <Card className="sticky top-24 p-6 border-2 border-teal/30 bg-teal/5">
              <h3 className="text-xl font-semibold text-navy mb-4">Make Your Impact</h3>

              {/* Donation Types */}
              <div className="space-y-3 mb-6">
                {donationTypes.map((type) => (
                  <button
                    key={type.id}
                    onClick={() => {
                      setSelectedDonationType(type.id);
                      setShowDonationModal(true);
                    }}
                    className={`w-full text-left p-4 rounded-sm border transition ${
                      selectedDonationType === type.id
                        ? 'border-teal bg-teal/10'
                        : 'border-line bg-[#FFFDF7] hover:border-teal/50'
                    }`}
                  >
                    <p className="font-semibold text-navy">{type.label}</p>
                    <p className="text-xs text-muted mt-1">{type.description}</p>
                    <p className="text-xs text-muted mt-2">
                      Impact value: <strong className="text-navy">₹{formatIndian(type.value_in_rupees)}</strong>
                    </p>
                  </button>
                ))}
              </div>

              {/* CTA Button */}
              <Button
                onClick={() => setShowDonationModal(true)}
                size="lg"
                className="w-full"
              >
                Donate Now
              </Button>

              <p className="text-xs text-muted text-center mt-4">
                Your donation is 100% transparent. Track where your money goes.
              </p>

              {/* Trust Badges */}
              <div className="mt-6 pt-6 border-t border-line space-y-2">
                <div className="flex items-center gap-2 text-xs text-ink">
                  <span className="text-status-approved">✓</span>
                  <span>Verified NGO</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-ink">
                  <span className="text-status-approved">✓</span>
                  <span>Transparent Budget</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-ink">
                  <span className="text-status-approved">✓</span>
                  <span>Impact Tracking</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Donation Modal */}
      {showDonationModal && (
        <div className="fixed inset-0 bg-navy/40 flex items-center justify-center z-50 p-4">
          <Card className="max-w-md w-full p-8">
            <h2 className="text-2xl font-semibold text-navy mb-6">Complete Your Donation</h2>
            <p className="text-muted mb-6">
              You're about to make a real difference in someone's life. Every donation counts.
            </p>
            <Button
              onClick={() => setShowDonationModal(false)}
              className="w-full mb-3"
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
