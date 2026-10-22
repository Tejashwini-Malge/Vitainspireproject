"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SocialShareOut } from "@/lib/types";

interface SocialShareButtonsProps {
  campaignId: string;
  donorName: string;
  amount: number;
}

const PLATFORMS = [
  { id: "WHATSAPP", label: "WhatsApp", icon: "💬", color: "bg-green-500" },
  { id: "TWITTER", label: "Twitter", icon: "𝕏", color: "bg-black" },
  { id: "LINKEDIN", label: "LinkedIn", icon: "in", color: "bg-blue-600" },
  { id: "FACEBOOK", label: "Facebook", icon: "f", color: "bg-blue-700" },
  { id: "EMAIL", label: "Email", icon: "✉", color: "bg-gray-500" },
];

export function SocialShareButtons({
  campaignId,
  donorName,
  amount,
}: SocialShareButtonsProps) {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const handleShare = async (platform: string) => {
    setLoading(true);
    try {
      const shareData = await api<SocialShareOut>("/social/share", {
        method: "POST",
        body: JSON.stringify({
          campaign_id: campaignId,
          platform,
          donor_name: donorName,
          donation_amount: amount,
        }),
      });

      // Open share URL
      if (platform === "EMAIL") {
        window.location.href = shareData.share_url;
      } else {
        window.open(shareData.share_url, "_blank", "width=600,height=400");
      }

      setCopied(platform);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error("Share failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {PLATFORMS.map((platform) => (
          <button
            key={platform.id}
            onClick={() => handleShare(platform.id)}
            disabled={loading}
            className={`flex flex-col items-center gap-2 rounded-sm ${platform.color} px-3 py-3 text-sm font-medium text-white transition-all hover:opacity-90 disabled:opacity-60`}
          >
            <span className="text-2xl">{platform.icon}</span>
            <span>{platform.label}</span>
          </button>
        ))}
      </div>

      {copied && (
        <p className="text-center text-sm text-teal">
          ✓ Share link copied! Opening {copied.toLowerCase()}...
        </p>
      )}
    </div>
  );
}
