"use client";

import { useState } from "react";
import { MessageCircle, AtSign, Share2, Send, Mail } from "lucide-react";
import { api } from "@/lib/api";
import type { SocialShareOut } from "@/lib/types";

interface SocialShareButtonsProps {
  campaignId: string;
  donorName: string;
  amount: number;
}

const PLATFORMS = [
  { id: "WHATSAPP", label: "WhatsApp", Icon: MessageCircle },
  { id: "TWITTER", label: "Twitter", Icon: AtSign },
  { id: "LINKEDIN", label: "LinkedIn", Icon: Share2 },
  { id: "FACEBOOK", label: "Facebook", Icon: Send },
  { id: "EMAIL", label: "Email", Icon: Mail },
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
        {PLATFORMS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => handleShare(id)}
            disabled={loading}
            className="flex flex-col items-center gap-2 rounded-sm border-2 border-line bg-[#FFFDF7] px-3 py-3 text-sm font-medium text-navy transition-all hover:border-navy hover:bg-navy/5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Icon className="h-5 w-5 text-navy" strokeWidth={1.75} aria-hidden />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {copied && (
        <p className="text-center font-mono text-xs uppercase tracking-wide text-teal">
          Share link copied -- opening {copied.toLowerCase()}…
        </p>
      )}
    </div>
  );
}
