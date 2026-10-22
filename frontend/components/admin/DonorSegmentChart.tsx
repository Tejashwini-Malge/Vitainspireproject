import type { DonorSegment } from "@/lib/types";

interface DonorSegmentChartProps {
  segments: DonorSegment[];
}

export function DonorSegmentChart({ segments }: DonorSegmentChartProps) {
  if (segments.length === 0) {
    return <p className="text-muted">No donor data available.</p>;
  }

  const maxDonors = Math.max(...segments.map((s) => s.donor_count), 1);
  const maxTotal = Math.max(...segments.map((s) => s.total_donated), 1);

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {segments.map((segment) => {
        const donorHeight = (segment.donor_count / maxDonors) * 100;
        const totalHeight = (segment.total_donated / maxTotal) * 100;

        return (
          <div key={segment.segment_name} className="rounded-lg border-2 border-line bg-white p-6">
            <h3 className="mb-4 font-semibold text-navy">{segment.segment_name}</h3>

            {/* Mini bar chart */}
            <div className="mb-4 space-y-3">
              <div>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-muted">Active Donors</span>
                  <span className="font-medium">{segment.donor_count}</span>
                </div>
                <div className="h-2 w-full rounded bg-paper">
                  <div
                    className="h-full rounded bg-teal transition-all"
                    style={{ width: `${donorHeight}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-muted">Total Donated</span>
                  <span className="font-medium">₹{(segment.total_donated / 100000).toFixed(1)}L</span>
                </div>
                <div className="h-2 w-full rounded bg-paper">
                  <div
                    className="h-full rounded bg-green-500 transition-all"
                    style={{ width: `${totalHeight}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="space-y-2 border-t border-line pt-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted">Avg Donation</span>
                <span className="font-medium">₹{(segment.average_donation / 1000).toFixed(1)}K</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Repeat Rate</span>
                <span className="font-medium">{segment.repeat_donation_rate}%</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
