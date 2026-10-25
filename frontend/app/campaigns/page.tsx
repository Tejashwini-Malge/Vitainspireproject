'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/ui/empty-state';

interface Campaign {
  id: string;
  ngo_id: string;
  title: string;
  mission: string;
  description: string;
  budget_total: number;
  amount_raised: number;
  currency: string;
  duration_months: number;
  status: string;
  hero_image_url: string | null;
  donation_count: number;
  beneficiary_count: number | null;
  created_at: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('recent');

  useEffect(() => {
    fetchCampaigns();
  }, [searchTerm, sortBy]);

  const fetchCampaigns = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        limit: '20',
      });
      if (searchTerm) params.append('search', searchTerm);

      const response = await fetch(`/api/campaigns?${params}`);
      if (response.ok) {
        const data = await response.json();
        setCampaigns(data);
      }
    } catch (error) {
      console.error('Failed to fetch campaigns:', error);
    } finally {
      setLoading(false);
    }
  };

  const getProgressPercentage = (raised: number, total: number) => {
    return total > 0 ? Math.min(100, Math.round((raised / total) * 100)) : 0;
  };

  const formatIndianNumber = (num: number) => {
    return new Intl.NumberFormat('en-IN').format(num);
  };

  return (
    <div className="space-y-12">
      {/* Header Hero */}
      <div className="-mx-4 border-b-2 border-navy bg-navy px-4 py-12 text-paper sm:-mx-6 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-paper/70">Discover</p>
          <h1 className="mt-2 text-4xl font-display font-semibold md:text-5xl">
            Campaigns making a difference
          </h1>
          <p className="mt-4 max-w-2xl text-paper/80">
            Find causes you care about. Support NGOs working on the ground. Track the real impact of your donation.
          </p>

          {/* Search & Filter */}
          <div className="mt-8 flex flex-col gap-4 sm:flex-row">
            <div className="flex-1">
              <Input
                type="text"
                placeholder="Search campaigns... education, healthcare, environment"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="rounded-sm border border-line bg-[#FFFDF7] px-4 py-2 font-medium text-ink"
            >
              <option value="recent">Most Recent</option>
              <option value="trending">Trending</option>
              <option value="ending_soon">Ending Soon</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-6xl">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-96 animate-pulse rounded-sm border border-line bg-navy/5" />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <EmptyState
            title="No campaigns found"
            description="Try adjusting your search or check back soon for new campaigns."
          />
        ) : (
          <>
            <div className="mb-8">
              <p className="text-sm text-muted">
                Showing <strong className="text-navy">{campaigns.length}</strong> active campaigns
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {campaigns.map((campaign, i) => {
                const progress = getProgressPercentage(campaign.amount_raised, campaign.budget_total);

                return (
                  <motion.div
                    key={campaign.id}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-40px' }}
                    transition={{ duration: 0.4, delay: Math.min(i, 6) * 0.05 }}
                  >
                    <Link href={`/campaigns/${campaign.id}`}>
                      <Card interactive className="h-full overflow-hidden">
                        {/* Image */}
                        <div className="relative h-48 overflow-hidden border-b border-line bg-navy/10">
                          {campaign.hero_image_url ? (
                            <img
                              src={campaign.hero_image_url}
                              alt={campaign.title}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-5xl text-navy/20">
                              ◈
                            </div>
                          )}

                          {/* Badge */}
                          <div className="absolute top-4 right-4 rounded-sm border border-line bg-[#FFFDF7] px-3 py-1">
                            <span className="font-mono text-xs font-semibold text-status-approved">
                              {progress}% Funded
                            </span>
                          </div>
                        </div>

                        {/* Content */}
                        <div className="p-6">
                          {/* Mission */}
                          <p className="font-mono text-xs uppercase tracking-wide text-muted mb-2">
                            {campaign.mission.length > 50
                              ? campaign.mission.substring(0, 50) + '...'
                              : campaign.mission}
                          </p>

                          {/* Title */}
                          <h3 className="text-lg font-semibold text-navy mb-2 line-clamp-2">
                            {campaign.title}
                          </h3>

                          {/* Beneficiaries */}
                          {campaign.beneficiary_count && (
                            <p className="text-sm text-muted mb-4">
                              <strong className="text-navy">{formatIndianNumber(campaign.beneficiary_count)}</strong> people to help
                            </p>
                          )}

                          {/* Progress Bar */}
                          <div className="mb-4">
                            <div className="h-2 w-full overflow-hidden rounded-full bg-line">
                              <div
                                className="h-full bg-teal transition-all duration-500"
                                style={{ width: `${progress}%` }}
                              />
                            </div>
                          </div>

                          {/* Funding Info */}
                          <div className="grid grid-cols-2 gap-4 mb-6 pb-6 border-b border-line">
                            <div>
                              <p className="text-xs text-muted mb-1">Raised</p>
                              <p className="font-semibold text-navy">
                                ₹{formatIndianNumber(campaign.amount_raised)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-muted mb-1">Goal</p>
                              <p className="font-semibold text-navy">
                                ₹{formatIndianNumber(campaign.budget_total)}
                              </p>
                            </div>
                          </div>

                          {/* Donor Count & CTA */}
                          <div className="flex items-center justify-between">
                            <p className="text-xs text-muted">
                              <strong className="text-navy">{campaign.donation_count}</strong> donors
                            </p>
                            <Button
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault();
                              }}
                            >
                              Donate Now
                            </Button>
                          </div>
                        </div>
                      </Card>
                    </Link>
                  </motion.div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* CTA Section */}
      <div className="-mx-4 border-t-2 border-navy bg-navy/5 py-12 sm:-mx-6">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6">
          <h2 className="text-3xl font-display font-semibold text-navy mb-4">Ready to make a difference?</h2>
          <p className="text-muted mb-8 max-w-2xl mx-auto">
            Every donation matters. Choose a cause you care about and start making an impact today. Track your donations and see the real results of your support.
          </p>
          <Button size="lg">
            Explore More Campaigns
          </Button>
        </div>
      </div>
    </div>
  );
}
