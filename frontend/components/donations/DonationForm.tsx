"use client";

import { useState } from "react";

interface DonationFormProps {
  campaignId: string;
  isProcessing: boolean;
  onSubmit: (amount: number, name: string, email: string, isRecurring: boolean, frequency?: string) => Promise<void>;
}

const PRESET_AMOUNTS = [
  { label: "₹500", value: 50000 },
  { label: "₹1,000", value: 100000 },
  { label: "₹5,000", value: 500000 },
  { label: "₹10,000", value: 1000000 },
];

export function DonationForm({ campaignId, isProcessing, onSubmit }: DonationFormProps) {
  const [selectedAmount, setSelectedAmount] = useState<number | null>(null);
  const [customAmount, setCustomAmount] = useState<string>("");
  const [donorName, setDonorName] = useState<string>("");
  const [donorEmail, setDonorEmail] = useState<string>("");
  const [isRecurring, setIsRecurring] = useState<boolean>(false);
  const [frequency, setFrequency] = useState<string>("MONTHLY");
  const [error, setError] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);

  const finalAmount = customAmount ? parseInt(customAmount) * 100 : selectedAmount;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Validation
    if (!finalAmount || finalAmount < 10000) {
      setError("Minimum donation is ₹100");
      return;
    }
    if (!donorName.trim()) {
      setError("Please enter your name");
      return;
    }
    if (!donorEmail.trim()) {
      setError("Please enter your email");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(donorEmail)) {
      setError("Please enter a valid email");
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(
        finalAmount,
        donorName,
        donorEmail,
        isRecurring,
        isRecurring ? frequency : undefined
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 rounded-lg border-2 border-line bg-white p-6">
      {/* Amount Selection */}
      <fieldset className="space-y-3">
        <legend className="font-semibold text-navy">Donation Amount</legend>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {PRESET_AMOUNTS.map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => {
                setSelectedAmount(preset.value);
                setCustomAmount("");
              }}
              className={`rounded-sm border-2 px-3 py-2 text-center font-medium transition-all ${
                selectedAmount === preset.value && !customAmount
                  ? "border-teal bg-teal/10 text-teal"
                  : "border-line text-navy hover:border-teal"
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div>
          <label className="block text-sm font-medium text-navy">Custom Amount (₹)</label>
          <input
            type="number"
            min="100"
            placeholder="Enter amount"
            value={customAmount}
            onChange={(e) => {
              setCustomAmount(e.target.value);
              setSelectedAmount(null);
            }}
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2 text-navy placeholder-muted focus:border-teal focus:outline-none"
          />
        </div>
      </fieldset>

      {/* Donor Details */}
      <fieldset className="space-y-3">
        <legend className="font-semibold text-navy">Your Details</legend>

        <div>
          <label htmlFor="donor-name" className="block text-sm font-medium text-navy">
            Full Name
          </label>
          <input
            id="donor-name"
            type="text"
            value={donorName}
            onChange={(e) => setDonorName(e.target.value)}
            placeholder="Your name"
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2 text-navy placeholder-muted focus:border-teal focus:outline-none"
            disabled={isProcessing || submitting}
          />
        </div>

        <div>
          <label htmlFor="donor-email" className="block text-sm font-medium text-navy">
            Email Address
          </label>
          <input
            id="donor-email"
            type="email"
            value={donorEmail}
            onChange={(e) => setDonorEmail(e.target.value)}
            placeholder="your@email.com"
            className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2 text-navy placeholder-muted focus:border-teal focus:outline-none"
            disabled={isProcessing || submitting}
          />
        </div>
      </fieldset>

      {/* Recurring Donation Option */}
      <fieldset className="space-y-3 rounded-sm bg-paper p-4">
        <legend className="font-semibold text-navy">Recurring Donation</legend>

        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isRecurring}
            onChange={(e) => setIsRecurring(e.target.checked)}
            disabled={isProcessing || submitting}
            className="h-5 w-5 cursor-pointer"
          />
          <span className="text-sm text-navy">Make this a monthly donation</span>
        </label>

        {isRecurring && (
          <div>
            <label htmlFor="frequency" className="block text-sm font-medium text-navy">
              Frequency
            </label>
            <select
              id="frequency"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              disabled={isProcessing || submitting}
              className="mt-1 w-full rounded-sm border-2 border-line bg-white px-3 py-2 text-navy focus:border-teal focus:outline-none"
            >
              <option value="MONTHLY">Monthly</option>
              <option value="QUARTERLY">Quarterly (Every 3 months)</option>
              <option value="YEARLY">Yearly</option>
            </select>
          </div>
        )}

        {isRecurring && (
          <p className="text-xs text-muted">
            ✓ Your donation will be automatically processed on the same day each billing period.
            You can pause or cancel anytime.
          </p>
        )}
      </fieldset>

      {/* Error Message */}
      {error && (
        <div role="alert" className="rounded-sm border-2 border-status-rejected bg-status-rejected/5 p-3">
          <p className="text-sm text-status-rejected">{error}</p>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isProcessing || submitting || !finalAmount || !donorName || !donorEmail}
        className="w-full rounded-sm bg-teal px-4 py-3 font-display font-medium text-paper disabled:opacity-60"
      >
        {isProcessing || submitting ? "Processing..." : `Donate ₹${finalAmount ? (finalAmount / 100).toLocaleString() : "0"}`}
      </button>

      <p className="text-center text-xs text-muted">
        Your donation is secure and processed by Razorpay. We never store your card details.
      </p>
    </form>
  );
}
