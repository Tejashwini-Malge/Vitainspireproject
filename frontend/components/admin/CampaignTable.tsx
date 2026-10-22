import type { CampaignPerformance } from "@/lib/types";

interface CampaignTableProps {
  campaigns: CampaignPerformance[];
}

export function CampaignTable({ campaigns }: CampaignTableProps) {
  if (campaigns.length === 0) {
    return <p className="text-muted">No campaigns yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border-2 border-line bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b border-line bg-paper">
            <th className="px-4 py-3 text-left text-sm font-semibold text-navy">Campaign</th>
            <th className="px-4 py-3 text-left text-sm font-semibold text-navy">NGO</th>
            <th className="px-4 py-3 text-right text-sm font-semibold text-navy">Views</th>
            <th className="px-4 py-3 text-right text-sm font-semibold text-navy">Donations</th>
            <th className="px-4 py-3 text-right text-sm font-semibold text-navy">Raised</th>
            <th className="px-4 py-3 text-right text-sm font-semibold text-navy">Conversion</th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map((campaign) => (
            <tr key={campaign.campaign_id} className="border-b border-line hover:bg-paper">
              <td className="px-4 py-3 text-sm text-navy">{campaign.title}</td>
              <td className="px-4 py-3 text-sm text-muted">{campaign.ngo_name}</td>
              <td className="px-4 py-3 text-right text-sm text-navy">{campaign.views.toLocaleString()}</td>
              <td className="px-4 py-3 text-right text-sm text-navy">{campaign.donation_count}</td>
              <td className="px-4 py-3 text-right text-sm font-medium text-navy">
                ₹{(campaign.amount_raised / 100000).toFixed(1)}L
              </td>
              <td className="px-4 py-3 text-right text-sm text-navy">{campaign.conversion_rate}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
