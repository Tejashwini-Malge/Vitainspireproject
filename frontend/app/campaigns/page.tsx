'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

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
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Header Hero */}
      <div className="bg-gradient-to-r from-blue-600 to-green-600 text-white py-12">
        <div className="max-w-6xl mx-auto px-4">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Discover Campaigns Making a Difference
          </h1>
          <p className="text-lg text-blue-100 mb-8 max-w-2xl">
            Find causes you care about. Support NGOs working on the ground. Track the real impact of your donation.
          </p>

          {/* Search & Filter */}
          <div className="flex flex-col sm:flex-row gap-4 max-w-2xl">
            <div className="flex-1">
              <Input
                type="text"
                placeholder="Search campaigns... education, healthcare, environment"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-4 py-3 rounded-lg text-gray-900 placeholder-gray-500"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-4 py-3 rounded-lg bg-white text-gray-900 font-medium cursor-pointer"
            >
              <option value="recent">Most Recent</option>
              <option value="trending">Trending</option>
              <option value="ending_soon">Ending Soon</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-12">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-gray-200 rounded-lg h-96 animate-pulse" />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🔍</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">No campaigns found</h2>
            <p className="text-gray-600">Try adjusting your search or check back soon for new campaigns!</p>
          </div>
        ) : (
          <>
            <div className="mb-8">
              <p className="text-sm text-gray-600">
                Showing <strong>{campaigns.length}</strong> active campaigns
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {campaigns.map((campaign) => {
                const progress = getProgressPercentage(campaign.amount_raised, campaign.budget_total);

                return (
                  <Link key={campaign.id} href={`/campaigns/${campaign.id}`}>
                    <Card className="h-full hover:shadow-lg transition-shadow duration-300 overflow-hidden cursor-pointer group">
                      {/* Image */}
                      <div className="relative h-48 bg-gradient-to-br from-blue-400 to-green-400 overflow-hidden">
                        {campaign.hero_image_url ? (
                          <img
                            src={campaign.hero_image_url}
                            alt={campaign.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="text-white text-5xl opacity-30">💚</div>
                          </div>
                        )}

                        {/* Badge */}
                        <div className="absolute top-4 right-4 bg-white rounded-full px-3 py-1">
                          <span className="text-xs font-bold text-green-600">
                            {progress}% Funded
                          </span>
                        </div>
                      </div>

                      {/* Content */}
                      <div className="p-6">
                        {/* Mission */}
                        <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-2">
                          {campaign.mission.length > 50
                            ? campaign.mission.substring(0, 50) + '...'
                            : campaign.mission}
                        </p>

                        {/* Title */}
                        <h3 className="text-lg font-bold text-gray-900 mb-2 line-clamp-2 group-hover:text-blue-600 transition">
                          {campaign.title}
                        </h3>

                        {/* Beneficiaries */}
                        {campaign.beneficiary_count && (
                          <p className="text-sm text-gray-600 mb-4 flex items-center gap-2">
                            <span>👥</span>
                            <span>
                              <strong>{formatIndianNumber(campaign.beneficiary_count)}</strong> people to help
                            </span>
                          </p>
                        )}

                        {/* Progress Bar */}
                        <div className="mb-4">
                          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              className="bg-gradient-to-r from-blue-500 to-green-500 h-full transition-all duration-500"
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                        </div>

                        {/* Funding Info */}
                        <div className="grid grid-cols-2 gap-4 mb-6 pb-6 border-b border-gray-200">
                          <div>
                            <p className="text-xs text-gray-600 mb-1">Raised</p>
                            <p className="font-bold text-gray-900">
                              ₹{formatIndianNumber(campaign.amount_raised)}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-600 mb-1">Goal</p>
                            <p className="font-bold text-gray-900">
                              ₹{formatIndianNumber(campaign.budget_total)}
                            </p>
                          </div>
                        </div>

                        {/* Donor Count & CTA */}
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-gray-600">
                            <strong>{campaign.donation_count}</strong> donors
                          </p>
                          <Button
                            size="sm"
                            className="bg-blue-600 hover:bg-blue-700 text-white"
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
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* CTA Section */}
      <div className="bg-gray-50 border-t border-gray-200 py-12 mt-12">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Ready to make a difference?</h2>
          <p className="text-gray-600 mb-8 max-w-2xl mx-auto">
            Every donation matters. Choose a cause you care about and start making an impact today. Track your donations and see the real results of your support.
          </p>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 text-lg">
            Explore More Campaigns
          </Button>
        </div>
      </div>
    </div>
  );
}
